from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_config
from backend.app.models.tables import Position, ScreenResult, SymbolMaster


DEFAULT_MAX_DAILY_LOSS_FRACTION = 0.03
DEFAULT_MAX_SECTOR_EXPOSURE_FRACTION = 0.4
DEFAULT_MAX_STRATEGY_EXPOSURE_FRACTION = 0.5
DEFAULT_GAP_RISK_FRACTION = 0.08


@dataclass(frozen=True)
class ExposureItem:
    symbol: str
    sector: str
    strategy_tag: str
    notional: float
    source: str


@dataclass(frozen=True)
class PositionSummary:
    source: str
    count: int
    notional: float
    open_risk: float
    gap_notional: float
    exposure_items: list[ExposureItem]
    missing_gap_symbols: list[str]


class PortfolioService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def risk_summary(self) -> dict[str, object]:
        """현재 포지션과 최신 통과 후보의 preview-only 리스크 요약을 반환한다."""
        positions = self._load_current_positions()
        latest_date, proposed = self._load_latest_proposed_positions()
        sectors = self._symbol_sectors({row.symbol for row in positions} | {row.symbol for row in proposed})
        limits = self._risk_limits()

        current_summary = self._current_position_summary(positions, sectors)
        proposed_summary = self._proposed_position_summary(proposed, sectors)
        exposure_summary = self._exposure_summary(
            current_summary,
            proposed_summary,
            account_equity=float(limits["account_equity"]),
        )
        daily_loss_budget = self._daily_loss_budget(current_summary, proposed_summary, limits)
        gap_risk_estimate = self._gap_risk_estimate(current_summary, proposed_summary, limits)
        concentration_warnings = self._concentration_warnings(
            current_summary,
            proposed_summary,
            exposure_summary,
            limits,
        )
        warnings = self._warnings(
            latest_date=latest_date,
            current_summary=current_summary,
            proposed_summary=proposed_summary,
            gap_risk_estimate=gap_risk_estimate,
            concentration_warnings=concentration_warnings,
        )

        account_equity = float(limits["account_equity"])
        risk_per_trade = float(limits["risk_per_trade"])
        max_daily_loss = float(daily_loss_budget["max_loss_amount"])
        available_risk_budget = max(risk_per_trade * max(1, proposed_summary.count) - proposed_summary.notional * 0.01, 0)
        return {
            "account_equity": account_equity,
            "risk_per_trade": risk_per_trade,
            "max_daily_loss": max_daily_loss,
            "open_positions_count": current_summary.count,
            "total_position_notional": current_summary.notional,
            "available_risk_budget": round(available_risk_budget, 2),
            "warnings": warnings,
            "latest_signal_date": latest_date,
            "proposed_positions": proposed_summary.count,
            "proposed_notional": proposed_summary.notional,
            "broker_mode": "mock_preview_only",
            "open_positions": current_summary.count,
            "gross_exposure": current_summary.notional,
            "max_open_positions": int(limits["max_open_positions"]),
            "gross_exposure_pct": self._ratio(current_summary.notional, account_equity),
            "proposed_gross_exposure": proposed_summary.notional,
            "proposed_gross_exposure_pct": self._ratio(proposed_summary.notional, account_equity),
            "combined_gross_exposure": round(current_summary.notional + proposed_summary.notional, 2),
            "combined_gross_exposure_pct": self._ratio(
                current_summary.notional + proposed_summary.notional,
                account_equity,
            ),
            "sector_exposure": exposure_summary["sector_exposure"],
            "symbol_exposure": exposure_summary["symbol_exposure"],
            "strategy_exposure": exposure_summary["strategy_exposure"],
            "daily_loss_budget": daily_loss_budget,
            "gap_risk_estimate": gap_risk_estimate,
            "concentration_warnings": concentration_warnings,
        }

    def _load_current_positions(self) -> list[Position]:
        return list(self.db.scalars(select(Position).order_by(Position.symbol)).all())

    def _load_latest_proposed_positions(self) -> tuple[object | None, list[ScreenResult]]:
        latest_date = self.db.scalar(select(ScreenResult.trade_date).order_by(ScreenResult.trade_date.desc()).limit(1))
        if latest_date is None:
            return latest_date, []
        rows = list(
            self.db.scalars(
                select(ScreenResult)
                .where(ScreenResult.trade_date == latest_date, ScreenResult.passed.is_(True))
                .order_by(ScreenResult.total_score.desc(), ScreenResult.symbol)
            ).all()
        )
        return latest_date, rows

    def _symbol_sectors(self, symbols: set[str]) -> dict[str, str]:
        if not symbols:
            return {}
        rows = self.db.scalars(select(SymbolMaster).where(SymbolMaster.symbol.in_(symbols))).all()
        return {row.symbol: row.sector or "unknown" for row in rows}

    def _current_position_summary(self, positions: list[Position], sectors: dict[str, str]) -> PositionSummary:
        items: list[ExposureItem] = []
        open_risk = 0.0
        gap_notional = 0.0
        missing_gap_symbols: set[str] = set()
        for position in positions:
            symbol = str(position.symbol)
            notional = self._position_notional(position)
            open_risk += self._position_open_risk(position)
            if notional > 0:
                gap_notional += notional
            else:
                missing_gap_symbols.add(symbol)
            items.append(
                ExposureItem(
                    symbol=symbol,
                    sector=sectors.get(symbol, "unknown"),
                    strategy_tag=str(position.strategy_tag or "unknown"),
                    notional=notional,
                    source="position",
                )
            )
        return PositionSummary(
            source="positions",
            count=len(positions),
            notional=round(sum(item.notional for item in items), 2),
            open_risk=round(open_risk, 2),
            gap_notional=round(gap_notional, 2),
            exposure_items=items,
            missing_gap_symbols=sorted(missing_gap_symbols),
        )

    def _proposed_position_summary(self, rows: list[ScreenResult], sectors: dict[str, str]) -> PositionSummary:
        items: list[ExposureItem] = []
        open_risk = 0.0
        gap_notional = 0.0
        missing_gap_symbols: set[str] = set()
        for row in rows:
            symbol = str(row.symbol)
            notional = self._screen_result_notional(row)
            open_risk += self._screen_result_open_risk(row)
            if notional > 0:
                gap_notional += notional
            else:
                missing_gap_symbols.add(symbol)
            items.append(
                ExposureItem(
                    symbol=symbol,
                    sector=sectors.get(symbol, "unknown"),
                    strategy_tag=str(row.strategy_tag or "unknown"),
                    notional=notional,
                    source="screen_result",
                )
            )
        return PositionSummary(
            source="screen_results",
            count=len(rows),
            notional=round(sum(item.notional for item in items), 2),
            open_risk=round(open_risk, 2),
            gap_notional=round(gap_notional, 2),
            exposure_items=items,
            missing_gap_symbols=sorted(missing_gap_symbols),
        )

    def _exposure_summary(
        self,
        current_summary: PositionSummary,
        proposed_summary: PositionSummary,
        *,
        account_equity: float,
    ) -> dict[str, dict[str, dict[str, object]]]:
        current_items = current_summary.exposure_items
        proposed_items = proposed_summary.exposure_items
        combined_items = [*current_items, *proposed_items]
        return {
            "sector_exposure": {
                "current": self._sector_buckets(current_items, account_equity),
                "proposed": self._sector_buckets(proposed_items, account_equity),
                "combined": self._sector_buckets(combined_items, account_equity),
            },
            "symbol_exposure": {
                "current": self._symbol_buckets(current_items, account_equity),
                "proposed": self._symbol_buckets(proposed_items, account_equity),
                "combined": self._symbol_buckets(combined_items, account_equity),
            },
            "strategy_exposure": {
                "current": self._strategy_buckets(current_items, account_equity),
                "proposed": self._strategy_buckets(proposed_items, account_equity),
                "combined": self._strategy_buckets(combined_items, account_equity),
            },
        }

    def _daily_loss_budget(
        self,
        current_summary: PositionSummary,
        proposed_summary: PositionSummary,
        limits: dict[str, float | int],
    ) -> dict[str, object]:
        max_loss = round(float(limits["account_equity"]) * float(limits["max_daily_loss_fraction"]), 2)
        combined_open_risk = round(current_summary.open_risk + proposed_summary.open_risk, 2)
        return {
            "status": "exceeded" if combined_open_risk > max_loss else "available",
            "max_loss_amount": max_loss,
            "max_loss_fraction": float(limits["max_daily_loss_fraction"]),
            "risk_per_trade": round(float(limits["risk_per_trade"]), 2),
            "current_open_risk": current_summary.open_risk,
            "proposed_open_risk": proposed_summary.open_risk,
            "combined_open_risk": combined_open_risk,
            "remaining_after_current_open_risk": round(max(max_loss - current_summary.open_risk, 0.0), 2),
            "remaining_after_combined_open_risk": round(max(max_loss - combined_open_risk, 0.0), 2),
            "basis": "risk_config.portfolio.equity and max_daily_loss_fraction",
        }

    def _gap_risk_estimate(
        self,
        current_summary: PositionSummary,
        proposed_summary: PositionSummary,
        limits: dict[str, float | int],
    ) -> dict[str, object]:
        gap_fraction = float(limits["gap_risk_fraction"])
        current_amount = round(current_summary.gap_notional * gap_fraction, 2)
        proposed_amount = round(proposed_summary.gap_notional * gap_fraction, 2)
        missing_symbols = sorted(set(current_summary.missing_gap_symbols) | set(proposed_summary.missing_gap_symbols))
        if current_summary.gap_notional <= 0 and proposed_summary.gap_notional <= 0:
            return {
                "status": "not_available",
                "amount": None,
                "current_amount": None,
                "proposed_amount": None,
                "gap_fraction": gap_fraction,
                "missing_symbols": missing_symbols,
                "basis": "notional data is missing or no open/proposed positions exist",
            }
        return {
            "status": "estimated_from_synthetic_notional",
            "amount": round(current_amount + proposed_amount, 2),
            "current_amount": current_amount,
            "proposed_amount": proposed_amount,
            "gap_fraction": gap_fraction,
            "missing_symbols": missing_symbols,
            "basis": "configured adverse gap fraction applied to positions and latest passed screen_results",
        }

    def _concentration_warnings(
        self,
        current_summary: PositionSummary,
        proposed_summary: PositionSummary,
        exposure_summary: dict[str, dict[str, dict[str, object]]],
        limits: dict[str, float | int],
    ) -> list[str]:
        warnings: list[str] = []
        max_open_positions = int(limits["max_open_positions"])
        combined_count = current_summary.count + proposed_summary.count
        if max_open_positions > 0 and current_summary.count > max_open_positions:
            warnings.append(
                f"current open positions {current_summary.count} exceeds max_open_positions {max_open_positions}."
            )
        if max_open_positions > 0 and combined_count > max_open_positions:
            warnings.append(
                f"combined current/proposed positions {combined_count} exceeds max_open_positions {max_open_positions}."
            )

        warnings.extend(
            self._bucket_limit_warnings(
                "symbol",
                exposure_summary["symbol_exposure"]["combined"],
                float(limits["max_symbol_exposure_fraction"]),
            )
        )
        warnings.extend(
            self._bucket_limit_warnings(
                "sector",
                exposure_summary["sector_exposure"]["combined"],
                float(limits["max_sector_exposure_fraction"]),
            )
        )
        warnings.extend(
            self._bucket_limit_warnings(
                "strategy",
                exposure_summary["strategy_exposure"]["combined"],
                float(limits["max_strategy_exposure_fraction"]),
            )
        )
        return warnings

    def _warnings(
        self,
        *,
        latest_date: object | None,
        current_summary: PositionSummary,
        proposed_summary: PositionSummary,
        gap_risk_estimate: dict[str, object],
        concentration_warnings: list[str],
    ) -> list[str]:
        warnings = [
            "positions와 latest passed screen_results 기반 synthetic/preview risk summary입니다.",
            "실제 trade ledger, broker 체결, paper position mutation은 아직 연결되지 않았습니다.",
        ]
        if current_summary.count == 0:
            warnings.append("open positions가 없어 현재 노출은 0으로 계산됩니다.")
        if latest_date is None:
            warnings.append("screen_results가 없어 제안 포지션 노출은 0으로 계산됩니다.")
        elif proposed_summary.count > 0:
            warnings.append("proposed_positions는 주문 후보가 아니라 최신 통과 screen_results 후보입니다.")
        if gap_risk_estimate["status"] == "not_available":
            warnings.append("gap_risk_estimate는 현재 데이터 한계로 not_available 처리됐습니다.")
        return [*warnings, *concentration_warnings]

    def _risk_limits(self) -> dict[str, float | int]:
        risk_config = get_config("risk")
        backtest_config = get_config("backtest")
        portfolio_config = risk_config.get("portfolio", {})
        backtest_portfolio = backtest_config.get("portfolio", {})
        account_equity = float(portfolio_config["equity"])
        risk_fraction = float(portfolio_config["risk_fraction"])
        max_position_fraction = float(portfolio_config.get("max_position_fraction", 0.2))
        return {
            "account_equity": account_equity,
            "risk_per_trade": account_equity * risk_fraction,
            "max_daily_loss_fraction": float(
                portfolio_config.get("max_daily_loss_fraction", DEFAULT_MAX_DAILY_LOSS_FRACTION)
            ),
            "max_open_positions": int(portfolio_config.get("max_open_positions", backtest_portfolio.get("max_positions", 0))),
            "max_symbol_exposure_fraction": float(
                portfolio_config.get("max_symbol_exposure_fraction", max_position_fraction)
            ),
            "max_sector_exposure_fraction": float(
                portfolio_config.get("max_sector_exposure_fraction", DEFAULT_MAX_SECTOR_EXPOSURE_FRACTION)
            ),
            "max_strategy_exposure_fraction": float(
                portfolio_config.get("max_strategy_exposure_fraction", DEFAULT_MAX_STRATEGY_EXPOSURE_FRACTION)
            ),
            "gap_risk_fraction": float(
                portfolio_config.get(
                    "gap_risk_fraction",
                    risk_config.get("risk", {}).get("hard_stop_pct", DEFAULT_GAP_RISK_FRACTION),
                )
            ),
        }

    def _sector_buckets(self, items: list[ExposureItem], account_equity: float) -> dict[str, dict[str, object]]:
        return self._bucket_exposure(items, account_equity, bucket_name="sector")

    def _symbol_buckets(self, items: list[ExposureItem], account_equity: float) -> dict[str, dict[str, object]]:
        return self._bucket_exposure(items, account_equity, bucket_name="symbol")

    def _strategy_buckets(self, items: list[ExposureItem], account_equity: float) -> dict[str, dict[str, object]]:
        return self._bucket_exposure(items, account_equity, bucket_name="strategy")

    def _bucket_exposure(
        self,
        items: list[ExposureItem],
        account_equity: float,
        *,
        bucket_name: str,
    ) -> dict[str, dict[str, object]]:
        grouped: dict[str, dict[str, object]] = defaultdict(lambda: {"notional": 0.0, "count": 0, "symbols": set()})
        for item in items:
            key = self._bucket_key(item, bucket_name)
            grouped[key]["notional"] = float(grouped[key]["notional"]) + item.notional
            grouped[key]["count"] = int(grouped[key]["count"]) + 1
            symbols = grouped[key]["symbols"]
            if isinstance(symbols, set):
                symbols.add(item.symbol)
        return {
            key: {
                "notional": round(float(value["notional"]), 2),
                "pct_of_equity": self._ratio(float(value["notional"]), account_equity),
                "count": int(value["count"]),
                "symbols": sorted(value["symbols"]) if isinstance(value["symbols"], set) else [],
            }
            for key, value in sorted(grouped.items(), key=lambda pair: (-float(pair[1]["notional"]), pair[0]))
        }

    @staticmethod
    def _bucket_key(item: ExposureItem, bucket_name: str) -> str:
        if bucket_name == "sector":
            return item.sector or "unknown"
        if bucket_name == "strategy":
            return item.strategy_tag or "unknown"
        return item.symbol or "unknown"

    @staticmethod
    def _bucket_limit_warnings(
        bucket_name: str,
        buckets: dict[str, dict[str, object]],
        limit_fraction: float,
    ) -> list[str]:
        warnings: list[str] = []
        for key, bucket in buckets.items():
            exposure_fraction = float(bucket["pct_of_equity"])
            if exposure_fraction > limit_fraction:
                warnings.append(
                    f"{bucket_name} concentration warning: {key} exposure {exposure_fraction:.2%} "
                    f"exceeds limit {limit_fraction:.2%}."
                )
        return warnings

    @staticmethod
    def _position_notional(position: Position) -> float:
        return round(abs(float(position.avg_price or 0) * float(position.qty or 0)), 2)

    @staticmethod
    def _position_open_risk(position: Position) -> float:
        qty = abs(float(position.qty or 0))
        return round(max(float(position.avg_price or 0) - float(position.stop_price or 0), 0.0) * qty, 2)

    @staticmethod
    def _screen_result_notional(row: ScreenResult) -> float:
        if float(row.position_notional or 0) > 0:
            return round(float(row.position_notional or 0), 2)
        if row.entry_price is None or not row.position_size:
            return 0.0
        return round(abs(float(row.entry_price) * float(row.position_size)), 2)

    @staticmethod
    def _screen_result_open_risk(row: ScreenResult) -> float:
        position_size = abs(float(row.position_size or 0))
        if row.risk_per_share is not None and position_size > 0:
            return round(max(float(row.risk_per_share), 0.0) * position_size, 2)
        if row.entry_price is None or row.stop_price is None or position_size <= 0:
            return 0.0
        return round(max(float(row.entry_price) - float(row.stop_price), 0.0) * position_size, 2)

    @staticmethod
    def _ratio(numerator: float, denominator: float) -> float:
        if denominator <= 0:
            return 0.0
        return round(float(numerator) / float(denominator), 6)
