from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.app.models.tables import DailyOhlcv, FundamentalsPti, IndicatorSnapshot, ScreenResult, SymbolMaster
from backend.app.services.kis_market_quote_service import KisMarketQuoteService


class MarketRealtimeService:
    """로컬 OHLCV와 screener 결과로 종목 조회/랭킹 payload를 생성한다."""

    def __init__(self, db: Session, *, quote_service: KisMarketQuoteService | None = None) -> None:
        self.db = db
        self.quote_service = quote_service or KisMarketQuoteService()

    def search_symbols(self, *, q: str | None = None, limit: int = 20) -> dict[str, object]:
        """종목명, 심볼, 섹터 기준으로 로컬 종목 master를 검색한다."""
        normalized = (q or "").strip()
        statement = select(SymbolMaster)
        if normalized:
            pattern = f"%{normalized}%"
            statement = statement.where(
                or_(
                    SymbolMaster.symbol.ilike(pattern),
                    SymbolMaster.name.ilike(pattern),
                    SymbolMaster.sector.ilike(pattern),
                    SymbolMaster.industry.ilike(pattern),
                )
            )
        rows = list(self.db.scalars(statement.order_by(SymbolMaster.symbol).limit(limit)).all())
        latest_rows = self._latest_daily_by_symbol([row.symbol for row in rows])
        latest_scores = self._latest_screen_by_symbol([row.symbol for row in rows])
        return {
            "ok": True,
            "query": normalized,
            "count": len(rows),
            "results": [
                self._symbol_search_payload(row, latest_rows.get(row.symbol), latest_scores.get(row.symbol))
                for row in rows
            ],
            "source": "local_symbol_master",
            "network_call_performed": False,
        }

    def symbol_detail(self, symbol: str) -> dict[str, object]:
        """단일 종목의 master, 최신 가격, 지표, screener, 재무 as-of 정보를 반환한다."""
        normalized = symbol.strip().upper()
        symbol_row = self.db.get(SymbolMaster, normalized)
        if symbol_row is None:
            raise ValueError("종목을 찾을 수 없습니다.")
        latest_daily = self._latest_daily(normalized)
        previous_daily = self._previous_daily(normalized, latest_daily.trade_date if latest_daily else None)
        kis_quote = self.quote_service.fetch_quote(normalized)
        latest_indicator = self._latest_indicator(normalized)
        latest_screens = self._latest_screens(normalized)
        fundamentals = self._fundamentals_asof(normalized, latest_daily.trade_date if latest_daily else None)
        quote = self._quote_with_kis_fallback(kis_quote, latest_daily, previous_daily)
        return {
            "ok": True,
            "symbol": self._symbol_payload(symbol_row),
            "quote": quote,
            "indicator": self._indicator_payload(latest_indicator),
            "fundamentals": self._fundamentals_payload(fundamentals),
            "screener": [self._screen_payload(row) for row in latest_screens],
            "source": quote.get("source") or "local_daily_ohlcv",
            "quote_provider": {
                "primary": "kis_paper_quote",
                "fallback": "local_daily_ohlcv",
                "status": kis_quote["status"],
                "reason_codes": kis_quote["reason_codes"],
            },
            "network_call_performed": bool(kis_quote.get("network_call_performed")),
            "live_order_created": False,
            "broker_order_created": False,
        }

    def chart(self, *, symbol: str, limit: int = 120) -> dict[str, object]:
        """차트 렌더링에 필요한 OHLCV와 주요 이동평균 series를 반환한다."""
        normalized = symbol.strip().upper()
        symbol_row = self.db.get(SymbolMaster, normalized)
        if symbol_row is None:
            raise ValueError("종목을 찾을 수 없습니다.")
        rows = list(
            self.db.scalars(
                select(DailyOhlcv)
                .where(DailyOhlcv.symbol == normalized)
                .order_by(DailyOhlcv.trade_date.desc())
                .limit(limit)
            ).all()
        )
        rows = list(reversed(rows))
        indicators = {
            row.trade_date: row
            for row in self.db.scalars(
                select(IndicatorSnapshot)
                .where(IndicatorSnapshot.symbol == normalized)
                .order_by(IndicatorSnapshot.trade_date.desc())
                .limit(limit)
            ).all()
        }
        bars = [self._chart_bar_payload(row, indicators.get(row.trade_date)) for row in rows]
        return {
            "ok": True,
            "symbol": normalized,
            "name": symbol_row.name,
            "limit": limit,
            "bars": bars,
            "source": "local_daily_ohlcv",
            "network_call_performed": False,
        }

    def rankings(
        self,
        *,
        metric: str = "total_score",
        limit: int = 20,
        trade_date: date | None = None,
    ) -> dict[str, object]:
        """screener 또는 local OHLCV 기반 랭킹을 반환한다."""
        normalized_metric = metric.strip().lower()
        if normalized_metric in {"total_score", "reward_risk_ratio"}:
            items, ranking_date = self._screen_rankings(metric=normalized_metric, limit=limit, trade_date=trade_date)
            source = "screen_results"
        elif normalized_metric in {"return_20d", "turnover_value", "volume"}:
            items, ranking_date = self._price_rankings(metric=normalized_metric, limit=limit, trade_date=trade_date)
            source = "daily_ohlcv"
        else:
            raise ValueError("지원하지 않는 랭킹 metric입니다.")
        return {
            "ok": True,
            "metric": normalized_metric,
            "trade_date": ranking_date,
            "count": len(items),
            "items": items,
            "source": source,
            "network_call_performed": False,
        }

    def _latest_daily_by_symbol(self, symbols: list[str]) -> dict[str, DailyOhlcv]:
        if not symbols:
            return {}
        subquery = (
            select(DailyOhlcv.symbol, func.max(DailyOhlcv.trade_date).label("latest_trade_date"))
            .where(DailyOhlcv.symbol.in_(symbols))
            .group_by(DailyOhlcv.symbol)
            .subquery()
        )
        rows = self.db.scalars(
            select(DailyOhlcv).join(
                subquery,
                (DailyOhlcv.symbol == subquery.c.symbol)
                & (DailyOhlcv.trade_date == subquery.c.latest_trade_date),
            )
        ).all()
        return {row.symbol: row for row in rows}

    def _latest_screen_by_symbol(self, symbols: list[str]) -> dict[str, ScreenResult]:
        if not symbols:
            return {}
        latest_date = self.db.scalar(select(func.max(ScreenResult.trade_date)))
        if latest_date is None:
            return {}
        rows = list(
            self.db.scalars(
                select(ScreenResult)
                .where(ScreenResult.trade_date == latest_date, ScreenResult.symbol.in_(symbols))
                .order_by(ScreenResult.symbol, ScreenResult.total_score.desc())
            ).all()
        )
        latest: dict[str, ScreenResult] = {}
        for row in rows:
            latest.setdefault(row.symbol, row)
        return latest

    def _latest_daily(self, symbol: str) -> DailyOhlcv | None:
        return self.db.scalar(
            select(DailyOhlcv).where(DailyOhlcv.symbol == symbol).order_by(DailyOhlcv.trade_date.desc()).limit(1)
        )

    def _previous_daily(self, symbol: str, latest_trade_date: date | None) -> DailyOhlcv | None:
        if latest_trade_date is None:
            return None
        return self.db.scalar(
            select(DailyOhlcv)
            .where(DailyOhlcv.symbol == symbol, DailyOhlcv.trade_date < latest_trade_date)
            .order_by(DailyOhlcv.trade_date.desc())
            .limit(1)
        )

    def _latest_indicator(self, symbol: str) -> IndicatorSnapshot | None:
        return self.db.scalar(
            select(IndicatorSnapshot)
            .where(IndicatorSnapshot.symbol == symbol)
            .order_by(IndicatorSnapshot.trade_date.desc())
            .limit(1)
        )

    def _latest_screens(self, symbol: str) -> list[ScreenResult]:
        latest_date = self.db.scalar(select(func.max(ScreenResult.trade_date)).where(ScreenResult.symbol == symbol))
        if latest_date is None:
            return []
        return list(
            self.db.scalars(
                select(ScreenResult)
                .where(ScreenResult.symbol == symbol, ScreenResult.trade_date == latest_date)
                .order_by(ScreenResult.total_score.desc(), ScreenResult.strategy_tag)
            ).all()
        )

    def _fundamentals_asof(self, symbol: str, trade_date: date | None) -> FundamentalsPti | None:
        if trade_date is None:
            return None
        return self.db.scalar(
            select(FundamentalsPti)
            .where(FundamentalsPti.symbol == symbol, FundamentalsPti.effective_date <= trade_date)
            .order_by(FundamentalsPti.effective_date.desc(), FundamentalsPti.asof_date.desc())
            .limit(1)
        )

    def _screen_rankings(
        self,
        *,
        metric: str,
        limit: int,
        trade_date: date | None,
    ) -> tuple[list[dict[str, object]], date | None]:
        ranking_date = trade_date or self.db.scalar(select(func.max(ScreenResult.trade_date)))
        if ranking_date is None:
            return [], None
        metric_column = ScreenResult.reward_risk_ratio if metric == "reward_risk_ratio" else ScreenResult.total_score
        rows = list(
            self.db.scalars(
                select(ScreenResult)
                .where(ScreenResult.trade_date == ranking_date)
                .order_by(ScreenResult.passed.desc(), metric_column.desc().nullslast(), ScreenResult.symbol)
                .limit(limit)
            ).all()
        )
        names = self._symbol_names({row.symbol for row in rows})
        return [
            {
                "rank": index,
                "symbol": row.symbol,
                "name": names.get(row.symbol, row.symbol),
                "metric_value": row.reward_risk_ratio if metric == "reward_risk_ratio" else row.total_score,
                "strategy_name": row.strategy_tag,
                "passed": row.passed,
                "grade": self._grade(row.total_score),
                "reason_summary": row.reason_summary,
            }
            for index, row in enumerate(rows, start=1)
        ], ranking_date

    def _price_rankings(
        self,
        *,
        metric: str,
        limit: int,
        trade_date: date | None,
    ) -> tuple[list[dict[str, object]], date | None]:
        ranking_date = trade_date or self.db.scalar(select(func.max(DailyOhlcv.trade_date)))
        if ranking_date is None:
            return [], None
        rows = list(
            self.db.scalars(
                select(DailyOhlcv)
                .where(DailyOhlcv.trade_date == ranking_date)
                .order_by(DailyOhlcv.symbol)
            ).all()
        )
        names = self._symbol_names({row.symbol for row in rows})
        previous_close = self._previous_close_map([row.symbol for row in rows], ranking_date)
        scored = []
        for row in rows:
            if metric == "return_20d":
                value = self._lookback_return(row.symbol, ranking_date, row.close, lookback=20)
            elif metric == "volume":
                value = float(row.volume)
            else:
                value = float(row.turnover_value or 0.0)
            prev = previous_close.get(row.symbol)
            change = None if prev is None else round(float(row.close) - prev, 4)
            change_pct = None if prev in {None, 0.0} else round((float(row.close) - prev) / prev, 6)
            scored.append(
                {
                    "symbol": row.symbol,
                    "name": names.get(row.symbol, row.symbol),
                    "metric_value": value,
                    "close": row.close,
                    "change": change,
                    "change_pct": change_pct,
                    "volume": row.volume,
                    "turnover_value": row.turnover_value,
                }
            )
        scored.sort(key=lambda item: (float(item["metric_value"] or 0.0), item["symbol"]), reverse=True)
        return [{**item, "rank": index} for index, item in enumerate(scored[:limit], start=1)], ranking_date

    def _previous_close_map(self, symbols: list[str], ranking_date: date) -> dict[str, float]:
        result: dict[str, float] = {}
        for symbol in symbols:
            row = self._previous_daily(symbol, ranking_date)
            if row is not None:
                result[symbol] = float(row.close)
        return result

    def _lookback_return(self, symbol: str, ranking_date: date, close: float, *, lookback: int) -> float:
        rows = list(
            self.db.scalars(
                select(DailyOhlcv)
                .where(DailyOhlcv.symbol == symbol, DailyOhlcv.trade_date <= ranking_date)
                .order_by(DailyOhlcv.trade_date.desc())
                .limit(lookback + 1)
            ).all()
        )
        if len(rows) <= lookback or rows[-1].close == 0:
            return 0.0
        return round((float(close) - float(rows[-1].close)) / float(rows[-1].close), 6)

    def _symbol_names(self, symbols: set[str]) -> dict[str, str]:
        if not symbols:
            return {}
        rows = self.db.scalars(select(SymbolMaster).where(SymbolMaster.symbol.in_(symbols))).all()
        return {row.symbol: row.name for row in rows}

    @staticmethod
    def _symbol_payload(row: SymbolMaster) -> dict[str, object]:
        return {
            "symbol": row.symbol,
            "name": row.name,
            "asset_type": row.asset_type,
            "currency": row.currency,
            "market": row.market,
            "exchange": row.exchange,
            "sector": row.sector,
            "industry": row.industry,
            "is_active": row.is_active,
            "list_date": row.list_date,
            "delist_date": row.delist_date,
        }

    def _symbol_search_payload(
        self,
        symbol_row: SymbolMaster,
        latest_daily: DailyOhlcv | None,
        latest_screen: ScreenResult | None,
    ) -> dict[str, object]:
        return {
            **self._symbol_payload(symbol_row),
            "latest_trade_date": latest_daily.trade_date if latest_daily else None,
            "latest_close": latest_daily.close if latest_daily else None,
            "latest_volume": latest_daily.volume if latest_daily else None,
            "latest_score": latest_screen.total_score if latest_screen else None,
            "latest_grade": self._grade(latest_screen.total_score) if latest_screen else None,
            "latest_passed": latest_screen.passed if latest_screen else None,
        }

    @staticmethod
    def _quote_payload(latest: DailyOhlcv | None, previous: DailyOhlcv | None) -> dict[str, object]:
        if latest is None:
            return {"available": False, "source": "local_daily_ohlcv"}
        previous_close = float(previous.close) if previous is not None else None
        change = None if previous_close is None else round(float(latest.close) - previous_close, 4)
        change_pct = None if previous_close in {None, 0.0} else round((float(latest.close) - previous_close) / previous_close, 6)
        return {
            "available": True,
            "trade_date": latest.trade_date,
            "current_price": latest.close,
            "open": latest.open,
            "high": latest.high,
            "low": latest.low,
            "close": latest.close,
            "previous_close": previous_close,
            "change": change,
            "change_pct": change_pct,
            "volume": latest.volume,
            "turnover_value": latest.turnover_value,
            "venue": latest.venue,
            "source": "local_daily_ohlcv",
        }

    @classmethod
    def _quote_with_kis_fallback(
        cls,
        kis_quote: dict[str, Any],
        latest: DailyOhlcv | None,
        previous: DailyOhlcv | None,
    ) -> dict[str, object]:
        if kis_quote.get("ok") and isinstance(kis_quote.get("quote"), dict):
            quote = dict(kis_quote["quote"])
            fallback = cls._quote_payload(latest, previous)
            for key in ("previous_close", "venue"):
                quote.setdefault(key, fallback.get(key))
            quote["fallback_used"] = False
            quote["fallback_reason_codes"] = []
            return quote
        quote = cls._quote_payload(latest, previous)
        quote["fallback_used"] = True
        quote["fallback_reason_codes"] = list(kis_quote.get("reason_codes") or [])
        return quote

    @staticmethod
    def _indicator_payload(row: IndicatorSnapshot | None) -> dict[str, object] | None:
        if row is None:
            return None
        return {
            "trade_date": row.trade_date,
            "close": row.close,
            "sma20": row.sma20,
            "sma50": row.sma50,
            "sma150": row.sma150,
            "sma200": row.sma200,
            "relative_strength_score": row.relative_strength_score,
            "atr20_pct": row.atr20_pct,
            "volume_ratio_50": row.volume_ratio_50,
            "distance_from_52w_high": row.distance_from_52w_high,
        }

    @staticmethod
    def _fundamentals_payload(row: FundamentalsPti | None) -> dict[str, object] | None:
        if row is None:
            return None
        return {
            "asof_date": row.asof_date,
            "effective_date": row.effective_date,
            "revenue": row.revenue,
            "eps": row.eps,
            "op_margin": row.op_margin,
            "roe": row.roe,
            "gross_profitability": row.gross_profitability,
            "quarterly_eps_growth": row.quarterly_eps_growth,
            "sales_growth": row.sales_growth,
        }

    @staticmethod
    def _screen_payload(row: ScreenResult) -> dict[str, object]:
        return {
            "trade_date": row.trade_date,
            "strategy_name": row.strategy_tag,
            "strategy_tag": row.strategy_tag,
            "passed": row.passed,
            "grade": MarketRealtimeService._grade(row.total_score),
            "total_score": row.total_score,
            "entry_price": row.entry_price,
            "stop_price": row.stop_price,
            "target_price": row.target_price,
            "reward_risk_ratio": row.reward_risk_ratio,
            "reason_summary": row.reason_summary,
            "triggered_conditions": MarketRealtimeService._triggered_conditions(row),
            "risk_metadata": MarketRealtimeService._json_object(row.metadata_json).get("risk_metadata", {}),
        }

    @staticmethod
    def _chart_bar_payload(row: DailyOhlcv, indicator: IndicatorSnapshot | None) -> dict[str, object]:
        return {
            "trade_date": row.trade_date,
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "adj_close": row.adj_close,
            "volume": row.volume,
            "turnover_value": row.turnover_value,
            "sma20": indicator.sma20 if indicator else None,
            "sma50": indicator.sma50 if indicator else None,
            "relative_strength_score": indicator.relative_strength_score if indicator else None,
        }

    @staticmethod
    def _triggered_conditions(row: ScreenResult) -> list[str]:
        metadata = MarketRealtimeService._json_object(row.metadata_json)
        triggered = metadata.get("triggered_conditions")
        if isinstance(triggered, list):
            return [str(item) for item in triggered]
        pass_flags = MarketRealtimeService._json_object(row.pass_flags)
        return [str(key) for key, value in pass_flags.items() if value]

    @staticmethod
    def _json_object(raw: str | None) -> dict[str, Any]:
        try:
            parsed = json.loads(raw or "{}")
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _json_list(raw: str | None) -> list[Any]:
        try:
            parsed = json.loads(raw or "[]")
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 0.8:
            return "A"
        if score >= 0.65:
            return "B"
        if score >= 0.5:
            return "C"
        return "D"
