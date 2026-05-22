from __future__ import annotations

import json
from datetime import date, datetime
from uuid import uuid4

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_config
from backend.app.models.tables import BacktestRun, IndicatorSnapshot
from backend.app.repositories.backtest_repository import BacktestRepository
from backend.app.repositories.market_repository import MarketRepository
from backend.app.services.risk_service import RiskService
from backend.app.services.scoring_service import ScoringService
from backend.app.strategies.canslim_lite import CanslimLiteStrategy
from backend.app.strategies.trend_breakout import TrendBreakoutStrategy
from backend.app.strategies.vcp_breakout import VcpBreakoutStrategy
from backend.app.utils.hashing import stable_hash


class BacktestService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = MarketRepository(db)
        self.backtest_repo = BacktestRepository(db)
        self.risk_service = RiskService()
        self.scoring_service = ScoringService()
        self.strategy_config = get_config("strategies")
        self.backtest_config = get_config("backtest")
        self.strategies = {
            "trend_breakout": TrendBreakoutStrategy(self.strategy_config["trend_breakout"]),
            "vcp_breakout": VcpBreakoutStrategy(self.strategy_config["vcp_breakout"]),
            "canslim_lite": CanslimLiteStrategy(self.strategy_config["canslim_lite"]),
        }

    def run(
        self,
        strategy_name: str,
        start_date: date | None = None,
        end_date: date | None = None,
        initial_equity: float | None = None,
    ) -> dict[str, object]:
        """종가 신호 후 다음 거래일 시가 체결 가정으로 기본 백테스트를 수행한다."""
        if strategy_name not in self.strategies:
            raise ValueError(f"지원하지 않는 전략입니다: {strategy_name}")
        equity = float(initial_equity or get_config("risk")["portfolio"]["equity"])
        indicators = self._load_indicators(start_date, end_date)
        if not indicators:
            raise ValueError("indicator_snapshot 데이터가 없습니다.")
        daily = self.repo.daily_df(start_date, end_date)
        price_by_symbol = {
            symbol: group.sort_values("trade_date").reset_index(drop=True) for symbol, group in daily.groupby("symbol")
        }
        dates = sorted({row.trade_date for row in indicators})
        rows_by_date: dict[date, list[IndicatorSnapshot]] = {}
        for row in indicators:
            rows_by_date.setdefault(row.trade_date, []).append(row)

        trades: list[dict[str, object]] = []
        liquidity_stats = {"partial_fill_count": 0, "no_fill_count": 0, "total_unfilled_qty": 0}
        realism_stats = {"adjusted_price_trade_count": 0, "forced_exit_count": 0, "delisted_exit_count": 0, "missing_data_exit_count": 0}
        equity_curve = [{"date": dates[0], "equity": equity}]
        exposure_days = 0
        total_days = max((dates[-1] - dates[0]).days, 1)

        for signal_date in dates:
            candidates = []
            market_regime = self._market_regime_on(signal_date)
            for indicator in rows_by_date.get(signal_date, []):
                fundamentals = self.repo.fundamentals_asof(indicator.symbol, signal_date)
                strategy_result = self.strategies[strategy_name].evaluate(indicator, fundamentals, market_regime)
                risk = self.risk_service.calculate(indicator, equity)
                liquidity_ok = indicator.turnover_value >= float(self.strategy_config["common"]["min_turnover_value"])
                rr_ok = risk.reward_risk_ratio >= float(self.strategy_config["common"]["target_reward_risk"])
                if strategy_result.passed and liquidity_ok and rr_ok and risk.position_size > 0:
                    candidates.append((self.scoring_service.score(indicator, fundamentals, risk.rr_score), indicator, risk))
            if not candidates:
                continue
            _, indicator, risk = sorted(candidates, key=lambda item: item[0], reverse=True)[0]
            trade = self._simulate_trade(indicator.symbol, signal_date, risk, price_by_symbol, liquidity_stats, realism_stats)
            if trade is None:
                continue
            equity += float(trade["pnl"])
            exposure_days += int(trade["holding_days"])
            equity_curve.append({"date": trade["exit_date"], "equity": equity})
            trades.append(trade)

        metrics = self._metrics(
            trades,
            equity_curve,
            equity,
            initial_equity or get_config("risk")["portfolio"]["equity"],
            exposure_days,
            total_days,
            liquidity_stats,
            realism_stats,
        )
        run_id = f"bt-{uuid4().hex[:12]}"
        config_hash = stable_hash({"strategy": strategy_name, "backtest": self.backtest_config, "risk": get_config("risk")})
        self.backtest_repo.save(
            BacktestRun(
                run_id=run_id,
                strategy_name=strategy_name,
                config_hash=config_hash,
                start_date=start_date,
                end_date=end_date,
                metrics_json=json.dumps(metrics, ensure_ascii=False, default=str),
            )
        )
        return {"run_id": run_id, "strategy_name": strategy_name, "metrics": metrics, "trades": trades[:20]}

    def list_runs(self, limit: int = 20) -> list[dict[str, object]]:
        """최근 백테스트 run 목록을 반환한다."""
        runs = list(self.db.scalars(select(BacktestRun).order_by(BacktestRun.created_at.desc()).limit(limit)).all())
        return [self._serialize_run(run) for run in runs]

    def get_run(self, run_id: str) -> dict[str, object]:
        """단일 백테스트 run 상세를 반환한다."""
        run = self.db.get(BacktestRun, run_id)
        if run is None:
            raise ValueError("백테스트 run을 찾을 수 없습니다.")
        return self._serialize_run(run)

    @staticmethod
    def _serialize_run(run: BacktestRun) -> dict[str, object]:
        metrics = json.loads(run.metrics_json)
        return {
            "run_id": run.run_id,
            "strategy_name": run.strategy_name,
            "config_hash": run.config_hash,
            "start_date": run.start_date,
            "end_date": run.end_date,
            "metrics": metrics,
            "created_at": run.created_at,
        }

    def _load_indicators(self, start_date: date | None, end_date: date | None) -> list[IndicatorSnapshot]:
        stmt = select(IndicatorSnapshot)
        if start_date:
            stmt = stmt.where(IndicatorSnapshot.trade_date >= start_date)
        if end_date:
            stmt = stmt.where(IndicatorSnapshot.trade_date <= end_date)
        return list(self.db.scalars(stmt.order_by(IndicatorSnapshot.trade_date, IndicatorSnapshot.symbol)).all())

    def _simulate_trade(
        self,
        symbol: str,
        signal_date: date,
        risk,
        price_by_symbol: dict[str, pd.DataFrame],
        liquidity_stats: dict[str, int] | None = None,
        realism_stats: dict[str, int] | None = None,
    ) -> dict[str, object] | None:
        prices = price_by_symbol.get(symbol)
        if prices is None or prices.empty:
            return None
        future = prices[prices["trade_date"] > signal_date].reset_index(drop=True)
        if future.empty:
            return None
        entry_bar = future.iloc[0]
        execution_config = self.backtest_config["execution"]
        commission_bps = float(execution_config["commission_bps"])
        slippage_bps = float(execution_config["slippage_bps"])
        bps = (commission_bps + slippage_bps) / 10000
        same_bar_stop_first = bool(execution_config.get("same_bar_stop_first", True))
        use_adjusted_price = bool(execution_config.get("use_adjusted_price", False))
        entry_price_view = self._bar_price_view(entry_bar, use_adjusted_price)
        raw_entry_price = float(entry_price_view["open"])
        entry_price = raw_entry_price * (1 + bps)
        stop_price = float(risk.stop_price) * float(entry_price_view["adjustment_factor"])
        target_price = entry_price + (entry_price - stop_price) * float(self.strategy_config["common"]["target_reward_risk"])
        planned_qty = int(risk.position_size)
        liquidity_detail = self._liquidity_detail(entry_bar, raw_entry_price, planned_qty, execution_config)
        filled_qty = int(liquidity_detail["filled_qty"])
        unfilled_qty = int(liquidity_detail["unfilled_qty"])
        if filled_qty <= 0:
            self._record_no_fill(liquidity_stats, planned_qty)
            return None
        max_holding_days = int(execution_config["max_holding_days"])

        exit_decision: dict[str, object] | None = None
        exit_bar: pd.Series | None = None
        exit_bar_index = 0
        exit_price_view: dict[str, object] | None = None
        for index, bar in future.iloc[:max_holding_days].iterrows():
            current_price_view = self._bar_price_view(bar, use_adjusted_price)
            exit_decision = self._exit_decision(
                bar=current_price_view,
                bar_index=int(index),
                max_holding_days=max_holding_days,
                stop_price=stop_price,
                target_price=target_price,
                same_bar_stop_first=same_bar_stop_first,
            )
            if exit_decision is not None:
                exit_bar = bar
                exit_bar_index = int(index)
                exit_price_view = current_price_view
                break

        if exit_decision is None:
            forced_exit = self._forced_exit(
                symbol=symbol,
                prices=prices,
                future=future,
                max_holding_days=max_holding_days,
                execution_config=execution_config,
                use_adjusted_price=use_adjusted_price,
            )
            if forced_exit is None:
                return None
            exit_bar = forced_exit["bar"]
            exit_bar_index = int(forced_exit["bar_index"])
            exit_price_view = forced_exit["price_view"]
            exit_decision = forced_exit["exit_decision"]

        raw_exit_price = float(exit_decision["raw_exit_price"])
        exit_price = raw_exit_price * (1 - bps)
        pnl = (exit_price - entry_price) * filled_qty
        estimated_cost = ((raw_entry_price * bps) + (raw_exit_price * bps)) * filled_qty
        if unfilled_qty > 0:
            self._record_partial_fill(liquidity_stats, unfilled_qty)
        self._record_realism_stats(realism_stats, use_adjusted_price, exit_decision)
        assert exit_bar is not None
        assert exit_price_view is not None
        return {
            "symbol": symbol,
            "signal_date": signal_date,
            "entry_date": entry_bar["trade_date"],
            "raw_entry_price": round(raw_entry_price, 4),
            "entry_price": round(entry_price, 4),
            "exit_date": exit_bar["trade_date"],
            "raw_exit_price": round(raw_exit_price, 4),
            "exit_price": round(exit_price, 4),
            "exit_reason": exit_decision["exit_reason"],
            "qty": filled_qty,
            "pnl": round(pnl, 2),
            "estimated_cost": round(estimated_cost, 2),
            "cost_bps": round(bps * 10000, 4),
            "return_pct": round((exit_price / entry_price) - 1, 6),
            "holding_days": exit_bar_index + 1,
            "execution_detail": {
                "entry_assumption": "next_open",
                "exit_assumption": exit_decision["exit_assumption"],
                "same_bar_stop_first": same_bar_stop_first,
                "stop_touched": exit_decision["stop_touched"],
                "target_touched": exit_decision["target_touched"],
                "same_bar_both_touched": exit_decision["same_bar_both_touched"],
                "gap_stop": exit_decision["gap_stop"],
                "gap_target": exit_decision["gap_target"],
                "stop_price": round(stop_price, 4),
                "target_price": round(target_price, 4),
                "commission_bps": commission_bps,
                "slippage_bps": slippage_bps,
                "forced_exit": bool(exit_decision.get("forced_exit", False)),
                "delisted_exit": bool(exit_decision.get("delisted_exit", False)),
                "missing_data_exit": bool(exit_decision.get("missing_data_exit", False)),
                "delisted_handling_policy": str(execution_config.get("delisted_handling_policy", "ignore")),
                "missing_data_policy": str(execution_config.get("missing_data_policy", "ignore")),
            },
            "liquidity_detail": liquidity_detail,
            "price_detail": {
                "use_adjusted_price": use_adjusted_price,
                "entry_price_basis": entry_price_view["price_basis"],
                "exit_price_basis": exit_price_view["price_basis"],
                "entry_adjustment_factor": entry_price_view["adjustment_factor"],
                "exit_adjustment_factor": exit_price_view["adjustment_factor"],
                "entry_raw_close": entry_price_view["source_close"],
                "entry_adj_close": entry_price_view["source_adj_close"],
                "exit_raw_close": exit_price_view["source_close"],
                "exit_adj_close": exit_price_view["source_adj_close"],
            },
        }

    def _forced_exit(
        self,
        symbol: str,
        prices: pd.DataFrame,
        future: pd.DataFrame,
        max_holding_days: int,
        execution_config: dict[str, object],
        use_adjusted_price: bool,
    ) -> dict[str, object] | None:
        holding_window = future.iloc[:max_holding_days]
        if holding_window.empty or len(holding_window) >= max_holding_days:
            return None
        last_bar = holding_window.iloc[-1]
        last_date = last_bar["trade_date"]
        is_delisted = self._is_delisted_at_last_bar(symbol, prices, last_bar)
        if is_delisted:
            policy = str(execution_config.get("delisted_handling_policy", "ignore"))
            if policy != "last_available_close":
                return None
            exit_reason = "delisted"
            exit_assumption = "delisted_last_available_close_exit"
        else:
            policy = str(execution_config.get("missing_data_policy", "ignore"))
            if policy != "last_available_close":
                return None
            exit_reason = "missing_data"
            exit_assumption = "missing_data_last_available_close_exit"

        price_view = self._bar_price_view(last_bar, use_adjusted_price)
        return {
            "bar": last_bar,
            "bar_index": int(holding_window.index[-1]),
            "price_view": price_view,
            "exit_decision": {
                "exit_reason": exit_reason,
                "raw_exit_price": float(price_view["close"]),
                "exit_assumption": exit_assumption,
                "stop_touched": False,
                "target_touched": False,
                "same_bar_both_touched": False,
                "gap_stop": False,
                "gap_target": False,
                "forced_exit": True,
                "delisted_exit": is_delisted,
                "missing_data_exit": not is_delisted,
                "last_available_date": last_date,
            },
        }

    def _is_delisted_at_last_bar(self, symbol: str, prices: pd.DataFrame, last_bar: pd.Series) -> bool:
        row_flag = self._truthy_flag(last_bar.get("delisted", False)) or self._truthy_flag(last_bar.get("is_delisted", False))
        if row_flag:
            return True
        delist_date = self._delist_date(symbol, prices)
        last_trade_date = self._optional_date(last_bar["trade_date"])
        return delist_date is not None and last_trade_date is not None and delist_date <= last_trade_date

    def _delist_date(self, symbol: str, prices: pd.DataFrame) -> date | None:
        if "delist_date" in prices.columns:
            delist_dates = prices["delist_date"].dropna()
            if not delist_dates.empty:
                return self._optional_date(delist_dates.iloc[-1])
        symbol_row = self.repo.get_symbol(symbol)
        return symbol_row.delist_date if symbol_row is not None else None

    @classmethod
    def _bar_price_view(cls, bar: pd.Series, use_adjusted_price: bool) -> dict[str, object]:
        close = float(bar["close"])
        adj_close = cls._optional_positive_float(bar.get("adj_close"))
        factor = adj_close / close if use_adjusted_price and close > 0 and adj_close is not None else 1.0
        return {
            "open": float(bar["open"]) * factor,
            "high": float(bar["high"]) * factor,
            "low": float(bar["low"]) * factor,
            "close": close * factor,
            "adjustment_factor": round(factor, 8),
            "price_basis": "adjusted_ohlc_from_adj_close" if use_adjusted_price and factor != 1.0 else "raw_ohlc",
            "source_close": close,
            "source_adj_close": adj_close,
        }

    @staticmethod
    def _truthy_flag(value: object) -> bool:
        if pd.isna(value):
            return False
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y"}
        return bool(value)

    @staticmethod
    def _optional_date(value: object) -> date | None:
        if value is None or pd.isna(value):
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.date()

    @classmethod
    def _liquidity_detail(
        cls,
        entry_bar: pd.Series,
        raw_entry_price: float,
        planned_qty: int,
        execution_config: dict[str, object],
    ) -> dict[str, object]:
        max_participation_rate = float(execution_config.get("max_participation_rate", 1.0))
        min_fill_ratio = float(execution_config.get("min_fill_ratio", 0.0))
        allow_partial_fill = bool(execution_config.get("allow_partial_fill", True))
        requested_notional = planned_qty * raw_entry_price
        turnover_value = cls._positive_float(entry_bar.get("turnover_value", 0))
        volume = cls._positive_float(entry_bar.get("volume", 0))

        if turnover_value > 0:
            liquidity_notional = turnover_value
            liquidity_basis = "turnover_value"
        elif volume > 0:
            liquidity_notional = volume * raw_entry_price
            liquidity_basis = "volume_x_entry_price"
        else:
            liquidity_notional = 0.0
            liquidity_basis = "missing_liquidity"

        cap_notional = liquidity_notional * max_participation_rate
        fill_ratio = min(1.0, cap_notional / requested_notional) if requested_notional > 0 else 0.0
        filled_qty = planned_qty if fill_ratio >= 1.0 else int(planned_qty * fill_ratio)
        if not allow_partial_fill and fill_ratio < 1.0:
            filled_qty = 0
        if planned_qty <= 0 or filled_qty <= 0 or (filled_qty / planned_qty) < min_fill_ratio:
            filled_qty = 0
        unfilled_qty = max(planned_qty - filled_qty, 0)

        return {
            "planned_qty": planned_qty,
            "filled_qty": filled_qty,
            "unfilled_qty": unfilled_qty,
            "requested_notional": round(requested_notional, 2),
            "liquidity_notional": round(liquidity_notional, 2),
            "cap_notional": round(cap_notional, 2),
            "fill_ratio": round(fill_ratio, 6),
            "max_participation_rate": max_participation_rate,
            "min_fill_ratio": min_fill_ratio,
            "allow_partial_fill": allow_partial_fill,
            "liquidity_basis": liquidity_basis,
            "position_size_cap_applied": filled_qty < planned_qty,
        }

    @staticmethod
    def _positive_float(value: object) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.0
        if pd.isna(numeric) or numeric <= 0:
            return 0.0
        return numeric

    @staticmethod
    def _optional_positive_float(value: object) -> float | None:
        numeric = BacktestService._positive_float(value)
        return numeric if numeric > 0 else None

    @staticmethod
    def _record_no_fill(liquidity_stats: dict[str, int] | None, planned_qty: int) -> None:
        if liquidity_stats is None:
            return
        liquidity_stats["no_fill_count"] = int(liquidity_stats.get("no_fill_count", 0)) + 1
        liquidity_stats["total_unfilled_qty"] = int(liquidity_stats.get("total_unfilled_qty", 0)) + max(planned_qty, 0)

    @staticmethod
    def _record_partial_fill(liquidity_stats: dict[str, int] | None, unfilled_qty: int) -> None:
        if liquidity_stats is None:
            return
        liquidity_stats["partial_fill_count"] = int(liquidity_stats.get("partial_fill_count", 0)) + 1
        liquidity_stats["total_unfilled_qty"] = int(liquidity_stats.get("total_unfilled_qty", 0)) + max(unfilled_qty, 0)

    @staticmethod
    def _record_realism_stats(
        realism_stats: dict[str, int] | None,
        use_adjusted_price: bool,
        exit_decision: dict[str, object],
    ) -> None:
        if realism_stats is None:
            return
        if use_adjusted_price:
            realism_stats["adjusted_price_trade_count"] = int(realism_stats.get("adjusted_price_trade_count", 0)) + 1
        if bool(exit_decision.get("forced_exit", False)):
            realism_stats["forced_exit_count"] = int(realism_stats.get("forced_exit_count", 0)) + 1
        if bool(exit_decision.get("delisted_exit", False)):
            realism_stats["delisted_exit_count"] = int(realism_stats.get("delisted_exit_count", 0)) + 1
        if bool(exit_decision.get("missing_data_exit", False)):
            realism_stats["missing_data_exit_count"] = int(realism_stats.get("missing_data_exit_count", 0)) + 1

    @staticmethod
    def _exit_decision(
        bar: dict[str, object],
        bar_index: int,
        max_holding_days: int,
        stop_price: float,
        target_price: float,
        same_bar_stop_first: bool,
    ) -> dict[str, object] | None:
        open_price = float(bar["open"])
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])
        stop_touched = low <= stop_price
        target_touched = high >= target_price
        gap_stop = open_price <= stop_price
        gap_target = open_price >= target_price
        same_bar_both_touched = stop_touched and target_touched

        if bar_index == 0 and gap_stop:
            return {
                "exit_reason": "stop",
                "raw_exit_price": open_price,
                "exit_assumption": "entry_gap_below_stop_open_exit",
                "stop_touched": True,
                "target_touched": target_touched,
                "same_bar_both_touched": same_bar_both_touched,
                "gap_stop": True,
                "gap_target": gap_target,
            }

        if same_bar_both_touched:
            if same_bar_stop_first:
                return {
                    "exit_reason": "stop",
                    "raw_exit_price": min(open_price, stop_price),
                    "exit_assumption": "same_bar_stop_first_stop_exit",
                    "stop_touched": True,
                    "target_touched": True,
                    "same_bar_both_touched": True,
                    "gap_stop": gap_stop,
                    "gap_target": gap_target,
                }
            return {
                "exit_reason": "target",
                "raw_exit_price": max(open_price, target_price),
                "exit_assumption": "same_bar_target_first_target_exit",
                "stop_touched": True,
                "target_touched": True,
                "same_bar_both_touched": True,
                "gap_stop": gap_stop,
                "gap_target": gap_target,
            }

        if stop_touched:
            return {
                "exit_reason": "stop",
                "raw_exit_price": min(open_price, stop_price),
                "exit_assumption": "gap_down_stop_open_exit" if gap_stop else "intraday_stop_exit",
                "stop_touched": True,
                "target_touched": False,
                "same_bar_both_touched": False,
                "gap_stop": gap_stop,
                "gap_target": gap_target,
            }

        if target_touched:
            return {
                "exit_reason": "target",
                "raw_exit_price": max(open_price, target_price),
                "exit_assumption": "gap_up_target_open_exit" if gap_target else "intraday_target_exit",
                "stop_touched": False,
                "target_touched": True,
                "same_bar_both_touched": False,
                "gap_stop": gap_stop,
                "gap_target": gap_target,
            }

        if bar_index == max_holding_days - 1:
            return {
                "exit_reason": "max_holding",
                "raw_exit_price": close,
                "exit_assumption": "max_holding_close_exit",
                "stop_touched": False,
                "target_touched": False,
                "same_bar_both_touched": False,
                "gap_stop": False,
                "gap_target": False,
            }

        return None

    def _market_regime_on(self, signal_date: date) -> str:
        df = self.repo.index_df()
        df = df[df["trade_date"] <= signal_date].sort_values("trade_date")
        if len(df) < 200:
            return "neutral"
        df["sma50"] = df["close"].rolling(50, min_periods=50).mean()
        df["sma200"] = df["close"].rolling(200, min_periods=200).mean()
        weekly = df.set_index(pd.to_datetime(df["trade_date"])).resample("W-FRI").agg({"close": "last"}).dropna()
        weekly["weekly_sma30"] = weekly["close"].rolling(30, min_periods=30).mean()
        weekly["weekly_sma30_slope"] = weekly["weekly_sma30"] - weekly["weekly_sma30"].shift(4)
        latest = df.iloc[-1]
        weekly_latest = weekly.iloc[-1]
        bull = (
            latest["close"] > latest["sma200"]
            and latest["sma50"] > latest["sma200"]
            and pd.notna(weekly_latest["weekly_sma30"])
            and pd.notna(weekly_latest["weekly_sma30_slope"])
            and weekly_latest["close"] > weekly_latest["weekly_sma30"]
            and weekly_latest["weekly_sma30_slope"] > 0
        )
        bear = latest["close"] < latest["sma200"] and latest["sma50"] < latest["sma200"]
        return "bull" if bull else ("bear" if bear else "neutral")

    @staticmethod
    def _metrics(
        trades: list[dict[str, object]],
        equity_curve: list[dict[str, object]],
        final_equity: float,
        initial_equity: float,
        exposure_days: int,
        total_days: int,
        liquidity_stats: dict[str, int] | None = None,
        realism_stats: dict[str, int] | None = None,
    ) -> dict[str, object]:
        pnls = [float(trade["pnl"]) for trade in trades]
        wins = [pnl for pnl in pnls if pnl > 0]
        losses = [pnl for pnl in pnls if pnl < 0]
        total_return = final_equity / initial_equity - 1
        years = max(total_days / 365.25, 1 / 365.25)
        cagr = (final_equity / initial_equity) ** (1 / years) - 1 if final_equity > 0 else -1
        equity_values = [float(row["equity"]) for row in equity_curve]
        peaks = pd.Series(equity_values).cummax()
        drawdowns = pd.Series(equity_values) / peaks - 1
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        total_estimated_cost = sum(float(trade.get("estimated_cost", 0)) for trade in trades)
        return {
            "trade_count": len(trades),
            "trades": len(trades),
            "win_rate": round(len(wins) / len(trades), 4) if trades else 0.0,
            "total_return": round(total_return, 6),
            "cagr": round(float(cagr), 6),
            "max_drawdown": round(float(drawdowns.min()), 6) if len(drawdowns) else 0.0,
            "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else (None if gross_profit == 0 else 999.0),
            "expectancy": round(sum(pnls) / len(pnls), 4) if pnls else 0.0,
            "avg_win": round(sum(wins) / len(wins), 4) if wins else 0.0,
            "avg_loss": round(sum(losses) / len(losses), 4) if losses else 0.0,
            "average_holding_days": round(sum(int(trade["holding_days"]) for trade in trades) / len(trades), 4) if trades else 0.0,
            "exposure": round(exposure_days / total_days, 6),
            "total_estimated_cost": round(total_estimated_cost, 2),
            "cost_bps": 7.0,
            "partial_fill_count": int((liquidity_stats or {}).get("partial_fill_count", 0)),
            "no_fill_count": int((liquidity_stats or {}).get("no_fill_count", 0)),
            "total_unfilled_qty": int((liquidity_stats or {}).get("total_unfilled_qty", 0)),
            "adjusted_price_trade_count": int((realism_stats or {}).get("adjusted_price_trade_count", 0)),
            "forced_exit_count": int((realism_stats or {}).get("forced_exit_count", 0)),
            "delisted_exit_count": int((realism_stats or {}).get("delisted_exit_count", 0)),
            "missing_data_exit_count": int((realism_stats or {}).get("missing_data_exit_count", 0)),
        }
