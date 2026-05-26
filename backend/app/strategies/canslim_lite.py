from __future__ import annotations

from datetime import date, datetime
from typing import Any

from backend.app.models.tables import FundamentalsPti, IndicatorSnapshot
from backend.app.strategies.base import BaseStrategy, StrategyResult


class CanslimLiteStrategy(BaseStrategy):
    name = "canslim_lite"
    KNOWN_EARNINGS_SESSIONS = {
        "before_open",
        "pre_market",
        "regular",
        "during_market",
        "after_close",
        "after_market",
    }

    def evaluate(
        self,
        indicator: IndicatorSnapshot,
        fundamentals: FundamentalsPti | None,
        market_regime: str,
    ) -> StrategyResult:
        """CANSLIM Lite 조건을 보수적으로 평가하고 PTI 검증 상태를 기록한다."""
        fundamentals_available = fundamentals is not None
        fundamentals_effective_date_available = (
            fundamentals_available and getattr(fundamentals, "effective_date", None) is not None
        )
        earnings_context = self._earnings_context(indicator)
        flags = {
            "fundamentals_available_asof": fundamentals_available,
            "earnings_blackout_clear": bool(earnings_context["blackout_clear"]),
            "quarterly_eps_growth_min": self._gte(
                getattr(fundamentals, "quarterly_eps_growth", None),
                self.config["quarterly_eps_growth_min"],
            ),
            "sales_growth_min": self._gte(
                getattr(fundamentals, "sales_growth", None),
                self.config["sales_growth_min"],
            ),
            "rs_percentile_min": self._gte(indicator.rs_percentile, self.config["rs_percentile_min"]),
            "breakout": bool(indicator.breakout),
            "market_regime_bull": market_regime == self.config["required_market_regime"],
        }
        if bool(self.config.get("require_recent_new_high", False)):
            flags["recent_new_high"] = self._recent_new_high(indicator)
        if bool(self.config.get("require_institutional_proxy", False)):
            flags["institutional_proxy"] = self._institutional_proxy(indicator)
        if bool(self.config.get("technical_trend_filter_enabled", False)):
            flags.update(
                {
                    "close_gt_sma50": self._gt(indicator.close, indicator.sma50),
                    "sma50_gt_sma150": self._gt(indicator.sma50, indicator.sma150),
                    "sma150_gt_sma200": self._gt(indicator.sma150, indicator.sma200),
                    "sma200_slope_positive": self._gt(indicator.sma200_slope, 0),
                }
            )
        if bool(self.config.get("volume_confirmation_enabled", False)):
            flags["volume_surge"] = self._volume_surge_confirmed(indicator)
        optional_conditions = []
        if bool(self.config.get("earnings_quality_enabled", False)):
            flags["roe_min"] = self._gte(getattr(fundamentals, "roe", None), self.config["min_roe"])
            optional_conditions.append("roe_min")
        if bool(self.config.get("sector_rs_filter_enabled", False)):
            flags["sector_rs_score_min"] = self._gte(
                getattr(indicator, "sector_rs_score", None),
                self.config["sector_rs_score_min"],
            )
            optional_conditions.append("sector_rs_score_min")
        self._apply_optional_hardening_flags(
            flags,
            optional_conditions,
            indicator,
            fundamentals,
            market_regime,
            include_near_high=True,
            include_fundamental_quality=True,
            include_earnings_quality=True,
        )
        failed = self._failed(flags)
        passed = self._all_flags(flags)
        summary = self._summary(self.name, passed, failed)
        risk_metadata = self._risk_metadata(indicator, entry_chase_reference=indicator.high_52w)
        metadata = self._metadata(
            flags,
            failed,
            summary,
            data_quality_flags={
                "fundamentals_available": fundamentals_available,
                "fundamentals_available_asof": fundamentals_available,
                "fundamentals_effective_date_available": fundamentals_effective_date_available,
                "quarterly_eps_growth_available": (
                    fundamentals_available and getattr(fundamentals, "quarterly_eps_growth", None) is not None
                ),
                "earnings_event_available": bool(earnings_context["event_available"]),
                "earnings_date_available": bool(earnings_context["earnings_date_available"]),
                "earnings_release_ts_available": bool(earnings_context["release_ts_available"]),
                "earnings_session_available": bool(earnings_context["session_available"]),
                "earnings_session_recognized": bool(earnings_context["session_recognized"]),
                "earnings_timing_available": bool(earnings_context["timing_available"]),
                "earnings_blackout_evaluated": bool(earnings_context["evaluated"]),
                "sales_growth_available": (
                    fundamentals_available and getattr(fundamentals, "sales_growth", None) is not None
                ),
                "roe_available": fundamentals_available and getattr(fundamentals, "roe", None) is not None,
                "rs_percentile_available": indicator.rs_percentile is not None,
                "breakout_available": getattr(indicator, "breakout", None) is not None,
                "close_available": indicator.close is not None,
                "sma50_available": indicator.sma50 is not None,
                "sma150_available": indicator.sma150 is not None,
                "sma200_available": indicator.sma200 is not None,
                "sma200_slope_available": indicator.sma200_slope is not None,
                "volume_available": indicator.volume is not None,
                "volume_ma50_available": indicator.volume_ma50 is not None,
                "recent_new_high_available": self._recent_new_high_available(indicator),
                "institutional_proxy_available": self._institutional_proxy_available(indicator),
                "technical_trend_available": self._technical_trend_available(indicator),
                "pti_validation_not_available_in_current_mvp": True,
                **self._hardening_data_quality_flags(indicator, fundamentals, market_regime, risk_metadata),
            },
            optional_conditions=optional_conditions,
            risk_metadata=risk_metadata,
        )
        metadata.update(
            {
                "fundamentals_available_asof": fundamentals_available,
                "fundamentals_effective_date_available": fundamentals_effective_date_available,
                "pti_validation_status": "pti_validation_not_available_in_current_mvp",
                "earnings_blackout_status": earnings_context["status"],
                "earnings_blackout_days": earnings_context["blackout_days"],
                "earnings_event": earnings_context["event"],
                "recent_new_high": self._recent_new_high(indicator),
                "institutional_proxy": self._institutional_proxy(indicator),
            }
        )
        return StrategyResult(
            strategy_tag=self.name,
            passed=passed,
            pass_flags=flags,
            failed_conditions=failed,
            reason_summary=summary,
            metadata=metadata,
        )

    def _volume_surge_confirmed(self, indicator: IndicatorSnapshot) -> bool:
        volume_ma50 = self._as_float(getattr(indicator, "volume_ma50", None))
        volume = self._as_float(getattr(indicator, "volume", None))
        return (
            volume is not None
            and volume_ma50 is not None
            and volume_ma50 > 0
            and volume >= volume_ma50 * float(self.config["volume_surge_multiple"])
        )

    def _earnings_context(self, indicator: IndicatorSnapshot) -> dict[str, Any]:
        event = getattr(indicator, "earnings_event", None)
        trade_date = self._as_date(getattr(indicator, "trade_date", None))
        event_date = self._as_date(getattr(event, "earnings_date", None)) if event is not None else None
        release_ts = getattr(event, "release_ts", None) if event is not None else None
        session = getattr(event, "session", None) if event is not None else None
        release_dt = release_ts if isinstance(release_ts, datetime) else None
        normalized_session = str(session or "").strip().lower()
        session_available = bool(normalized_session)
        session_recognized = normalized_session in self.KNOWN_EARNINGS_SESSIONS
        release_date = release_dt.date() if release_dt is not None else event_date
        blackout_days = max(int(self.config.get("earnings_blackout_days", 0)), 0)
        event_payload = {
            "symbol": getattr(event, "symbol", getattr(indicator, "symbol", None)) if event is not None else getattr(indicator, "symbol", None),
            "earnings_date": event_date.isoformat() if event_date is not None else None,
            "release_ts": release_dt.isoformat() if release_dt is not None else None,
            "release_date": release_date.isoformat() if release_date is not None else None,
            "session": normalized_session or None,
            "session_recognized": session_recognized,
            "days_to_earnings": None,
            "days_to_release": None,
            "in_blackout_window": None,
            "blackout_window_start": None,
            "blackout_window_end": None,
        }
        if trade_date is None or event_date is None:
            return {
                "event_available": event is not None,
                "earnings_date_available": event_date is not None,
                "release_ts_available": release_dt is not None,
                "session_available": session_available,
                "session_recognized": session_recognized,
                "timing_available": False,
                "evaluated": False,
                "blackout_clear": False,
                "blackout_days": blackout_days,
                "status": "earnings_event_missing_fail_closed",
                "event": event_payload,
            }

        days_to_earnings = (event_date - trade_date).days
        days_to_release = (release_date - trade_date).days if release_date is not None else days_to_earnings
        in_blackout = abs(days_to_release) <= blackout_days
        event_payload.update(
            {
                "days_to_earnings": days_to_earnings,
                "days_to_release": days_to_release,
                "in_blackout_window": in_blackout,
                "blackout_window_start": (release_date - date.resolution * blackout_days).isoformat()
                if release_date is not None
                else None,
                "blackout_window_end": (release_date + date.resolution * blackout_days).isoformat()
                if release_date is not None
                else None,
            }
        )
        if release_dt is None:
            return {
                "event_available": True,
                "earnings_date_available": True,
                "release_ts_available": False,
                "session_available": session_available,
                "session_recognized": session_recognized,
                "timing_available": False,
                "evaluated": False,
                "blackout_clear": False,
                "blackout_days": blackout_days,
                "status": "earnings_release_ts_unavailable_fail_closed",
                "event": event_payload,
            }
        if not session_available or not session_recognized:
            return {
                "event_available": True,
                "earnings_date_available": True,
                "release_ts_available": True,
                "session_available": session_available,
                "session_recognized": session_recognized,
                "timing_available": False,
                "evaluated": False,
                "blackout_clear": False,
                "blackout_days": blackout_days,
                "status": "earnings_session_unavailable_fail_closed",
                "event": event_payload,
            }
        return {
            "event_available": True,
            "earnings_date_available": True,
            "release_ts_available": True,
            "session_available": True,
            "session_recognized": True,
            "timing_available": True,
            "evaluated": True,
            "blackout_clear": not in_blackout,
            "blackout_days": blackout_days,
            "status": "clear" if not in_blackout else "earnings_blackout_fail_closed",
            "event": event_payload,
        }

    def _recent_new_high(self, indicator: IndicatorSnapshot) -> bool:
        distance = self._as_float(getattr(indicator, "distance_from_52w_high", None))
        if distance is not None:
            return distance >= -0.03
        close = self._as_float(getattr(indicator, "close", None))
        high_52w = self._as_float(getattr(indicator, "high_52w", None))
        return close is not None and high_52w is not None and high_52w > 0 and close >= high_52w * 0.97

    @staticmethod
    def _recent_new_high_available(indicator: IndicatorSnapshot) -> bool:
        return (
            getattr(indicator, "distance_from_52w_high", None) is not None
            or (getattr(indicator, "close", None) is not None and getattr(indicator, "high_52w", None) is not None)
        )

    def _institutional_proxy(self, indicator: IndicatorSnapshot) -> bool:
        volume_ratio = self._as_float(getattr(indicator, "volume_ratio_50", None))
        turnover = self._as_float(getattr(indicator, "turnover_value", None))
        sector_rs_score = self._as_float(getattr(indicator, "sector_rs_score", None))
        return (
            volume_ratio is not None
            and volume_ratio >= 1.0
            and turnover is not None
            and turnover > 0
            and (sector_rs_score is None or sector_rs_score >= 0.50)
        )

    @staticmethod
    def _institutional_proxy_available(indicator: IndicatorSnapshot) -> bool:
        return (
            getattr(indicator, "volume_ratio_50", None) is not None
            and getattr(indicator, "turnover_value", None) is not None
        )

    @staticmethod
    def _as_date(value: object) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return None

    @staticmethod
    def _technical_trend_available(indicator: IndicatorSnapshot) -> bool:
        return all(
            getattr(indicator, field_name, None) is not None
            for field_name in ("close", "sma50", "sma150", "sma200", "sma200_slope")
        )
