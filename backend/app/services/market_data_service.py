from __future__ import annotations

from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.app.core.config import get_config
from backend.app.models.tables import (
    BacktestRun,
    BacktestTradeLedger,
    DailyOhlcv,
    EarningsEvent,
    ExternalSymbolMapping,
    FundamentalsPti,
    IndexOhlcv,
    IndicatorSnapshot,
    Order,
    Report,
    ScreenResult,
    SectorOhlcv,
    SymbolMaster,
)
from backend.app.repositories.market_repository import MarketRepository
from backend.app.services.market_data_import_service import MarketDataImportService


class MarketDataService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = MarketRepository(db)

    def seed_sample_data(self) -> dict[str, int]:
        """한국장 deterministic 샘플 데이터를 생성한다."""
        self.repo.clear_market_data()
        app_config = get_config("app")
        days = int(app_config["sample"]["business_days"])
        end_date = pd.Timestamp("2026-05-20")
        dates = pd.bdate_range(end=end_date, periods=days)

        profiles = self._sample_profiles()
        self.db.add_all(
            [
                SymbolMaster(
                    symbol=symbol,
                    name=profile["name"],
                    market="KR",
                    exchange="KRX",
                    sector=profile["sector"],
                    industry=profile["industry"],
                    is_active=True,
                    list_date=date(2015, 1, 2),
                )
                for symbol, profile in profiles.items()
            ]
        )
        self.db.execute(
            delete(ExternalSymbolMapping).where(
                ExternalSymbolMapping.source_id.in_(["external_yfinance", "kis_market_data", "kis_openapi"])
            )
        )
        self.db.add_all(
            [
                ExternalSymbolMapping(
                    source_id="external_yfinance",
                    external_symbol=f"{symbol}.KS",
                    symbol=symbol,
                    market="KR",
                    venue="KRX",
                )
                for symbol in profiles
            ]
        )
        self.db.add_all(
            [
                ExternalSymbolMapping(
                    source_id="kis_market_data",
                    external_symbol=symbol,
                    symbol=symbol,
                    market="KR",
                    venue="KRX",
                )
                for symbol in profiles
            ]
        )
        self.db.add_all(
            [
                ExternalSymbolMapping(
                    source_id="external_yfinance",
                    external_symbol="005930.KS",
                    symbol="005930",
                    market="KR",
                    venue="KRX",
                ),
                ExternalSymbolMapping(
                    source_id="kis_market_data",
                    external_symbol="005930",
                    symbol="005930",
                    market="KR",
                    venue="KRX",
                ),
            ]
        )

        daily_rows: list[DailyOhlcv] = []
        for symbol, profile in profiles.items():
            df = self._build_symbol_frame(symbol, profile, dates)
            daily_rows.extend(
                DailyOhlcv(
                    trade_date=row.trade_date.date(),
                    symbol=symbol,
                    open=float(row.open),
                    high=float(row.high),
                    low=float(row.low),
                    close=float(row.close),
                    adj_close=float(row.close),
                    volume=int(row.volume),
                    turnover_value=float(row.close * row.volume),
                    venue="KRX",
                )
                for row in df.itertuples(index=False)
            )
        self.db.add_all(daily_rows)

        index_rows = self._build_index_rows(dates)
        self.db.add_all(index_rows)
        sector_rows = self._build_sector_rows(dates)
        self.db.add_all(sector_rows)
        fundamental_rows = self._build_fundamental_rows(profiles, dates[-1].date())
        self.db.add_all(fundamental_rows)
        earnings_event_rows = self._build_earnings_event_rows(profiles, dates[-1].date())
        self.db.add_all(earnings_event_rows)
        self.db.commit()

        return {
            "symbols": len(profiles),
            "daily_rows": len(daily_rows),
            "index_rows": len(index_rows),
            "sector_rows": len(sector_rows),
            "fundamental_rows": len(fundamental_rows),
            "earnings_event_rows": len(earnings_event_rows),
        }

    def import_daily_ohlcv_csv(self, content: bytes) -> dict[str, int]:
        """CSV를 daily_ohlcv에 검증 후 upsert한다."""
        return MarketDataImportService(self.db).legacy_direct_import_csv(content)

    def status(self) -> dict[str, object]:
        """MVP 데이터 파이프라인의 현재 row count와 최신 기준일을 반환한다."""
        count_map = {
            "symbol_count": SymbolMaster,
            "daily_ohlcv_count": DailyOhlcv,
            "index_ohlcv_count": IndexOhlcv,
            "sector_ohlcv_count": SectorOhlcv,
            "fundamentals_count": FundamentalsPti,
            "earnings_events_count": EarningsEvent,
            "indicator_snapshot_count": IndicatorSnapshot,
            "screen_results_count": ScreenResult,
            "reports_count": Report,
            "backtest_runs_count": BacktestRun,
            "backtest_trade_ledger_count": BacktestTradeLedger,
            "orders_count": Order,
        }
        result: dict[str, object] = {
            name: int(self.db.scalar(select(func.count()).select_from(table)) or 0) for name, table in count_map.items()
        }
        result["latest_trade_date"] = self.db.scalar(select(func.max(DailyOhlcv.trade_date)))
        result["latest_indicator_date"] = self.db.scalar(select(func.max(IndicatorSnapshot.trade_date)))
        result["latest_screen_date"] = self.db.scalar(select(func.max(ScreenResult.trade_date)))
        return result

    @staticmethod
    def _sample_profiles() -> dict[str, dict[str, object]]:
        return {
            "KR001": {"name": "상승추세전자", "sector": "Technology", "industry": "Semiconductor", "drift": 1.25, "volume": 900000, "tag": "trend"},
            "KR002": {"name": "상승추세소재", "sector": "Materials", "industry": "Chemicals", "drift": 1.05, "volume": 700000, "tag": "trend"},
            "KR003": {"name": "하락추세유통", "sector": "Consumer", "industry": "Retail", "drift": -0.65, "volume": 650000, "tag": "down"},
            "KR004": {"name": "하락추세게임", "sector": "Internet", "industry": "Game", "drift": -0.45, "volume": 620000, "tag": "down"},
            "KR005": {"name": "횡보금융", "sector": "Financials", "industry": "Bank", "drift": 0.05, "volume": 800000, "tag": "sideways"},
            "KR006": {"name": "횡보통신", "sector": "Telecom", "industry": "Carrier", "drift": 0.02, "volume": 750000, "tag": "sideways"},
            "KR007": {"name": "VCP유사바이오", "sector": "Healthcare", "industry": "Bio", "drift": 1.35, "volume": 850000, "tag": "vcp"},
            "KR008": {"name": "거래량돌파기계", "sector": "Industrials", "industry": "Machinery", "drift": 0.95, "volume": 980000, "tag": "volume_breakout"},
            "KR009": {"name": "캔슬림통과부품", "sector": "Technology", "industry": "Parts", "drift": 1.55, "volume": 1100000, "tag": "canslim_pass"},
            "KR010": {"name": "캔슬림탈락화장품", "sector": "Consumer", "industry": "Cosmetics", "drift": 1.00, "volume": 760000, "tag": "canslim_fail"},
            "KR011": {"name": "저유동성의료", "sector": "Healthcare", "industry": "Devices", "drift": 1.20, "volume": 12000, "tag": "low_liquidity"},
            "KR012": {"name": "RS상위엔터", "sector": "Media", "industry": "Entertainment", "drift": 1.45, "volume": 900000, "tag": "rs_high"},
            "KR013": {"name": "RS하위철강", "sector": "Materials", "industry": "Steel", "drift": -0.25, "volume": 700000, "tag": "rs_low"},
            "KR014": {"name": "중립자동차", "sector": "Industrials", "industry": "Auto", "drift": 0.45, "volume": 820000, "tag": "mixed"},
            "KR015": {"name": "섹터강세로봇", "sector": "Technology", "industry": "Robot", "drift": 1.15, "volume": 930000, "tag": "sector_leader"},
        }

    @staticmethod
    def _build_symbol_frame(symbol: str, profile: dict[str, object], dates: pd.DatetimeIndex) -> pd.DataFrame:
        n = len(dates)
        x = np.arange(n)
        drift = float(profile["drift"])
        base = 8000 + (int(symbol[-3:]) * 550)
        trend = 1 + drift * (x / n) * 0.55
        cycle = 1 + 0.025 * np.sin(x / 9.0 + int(symbol[-1]))
        close = base * trend * cycle

        tag = str(profile["tag"])
        if tag == "vcp":
            close[-70:-40] *= 1 + 0.06 * np.sin(np.arange(30) / 2.5)
            close[-40:-1] = np.linspace(close[-40], close[-40] * 1.03, 39) * (1 + 0.008 * np.sin(np.arange(39) / 1.7))
        if tag in {"volume_breakout", "canslim_pass", "vcp", "trend", "rs_high", "sector_leader"}:
            previous_high = float(np.max(close[-30:-1]))
            close[-1] = previous_high * (1.035 if tag in {"vcp", "canslim_pass"} else 1.02)
        if tag == "low_liquidity":
            close[-1] = float(np.max(close[-30:-1]) * 1.03)

        open_ = np.r_[close[0] * 0.995, close[:-1] * (1 + 0.002 * np.sin(x[:-1]))]
        spread = 0.018 + 0.004 * np.cos(x / 13.0)
        high = np.maximum(open_, close) * (1 + spread)
        low = np.minimum(open_, close) * (1 - spread)
        volume_base = int(profile["volume"])
        volume = (volume_base * (1 + 0.12 * np.sin(x / 11.0 + int(symbol[-1])))).astype(int)
        if tag == "vcp":
            volume[-50:-1] = (volume[-50:-1] * 0.55).astype(int)
        if tag in {"volume_breakout", "canslim_pass", "vcp", "trend", "rs_high", "sector_leader", "low_liquidity"}:
            volume[-1] = int(volume_base * (2.1 if tag != "low_liquidity" else 1.8))

        return pd.DataFrame(
            {
                "trade_date": dates,
                "open": np.round(open_, 2),
                "high": np.round(high, 2),
                "low": np.round(low, 2),
                "close": np.round(close, 2),
                "volume": volume,
            }
        )

    @staticmethod
    def _build_index_rows(dates: pd.DatetimeIndex) -> list[IndexOhlcv]:
        x = np.arange(len(dates))
        close = 2500 * (1 + 0.32 * (x / len(dates))) * (1 + 0.01 * np.sin(x / 12))
        open_ = np.r_[close[0] * 0.998, close[:-1]]
        high = np.maximum(open_, close) * 1.006
        low = np.minimum(open_, close) * 0.994
        return [
            IndexOhlcv(
                trade_date=dt.date(),
                symbol="KOSPI_SAMPLE",
                open=float(round(open_[i], 2)),
                high=float(round(high[i], 2)),
                low=float(round(low[i], 2)),
                close=float(round(close[i], 2)),
                volume=int(500000000 + 10000000 * np.sin(i / 15)),
            )
            for i, dt in enumerate(dates)
        ]

    @staticmethod
    def _build_sector_rows(dates: pd.DatetimeIndex) -> list[SectorOhlcv]:
        sectors = {
            "Technology": 0.42,
            "Healthcare": 0.30,
            "Industrials": 0.24,
            "Materials": 0.12,
            "Consumer": -0.03,
            "Financials": 0.04,
            "Telecom": 0.02,
            "Internet": -0.08,
            "Media": 0.36,
        }
        rows: list[SectorOhlcv] = []
        x = np.arange(len(dates))
        for sector, drift in sectors.items():
            close = 1000 * (1 + drift * (x / len(dates))) * (1 + 0.01 * np.sin(x / 10 + len(sector)))
            open_ = np.r_[close[0], close[:-1]]
            high = np.maximum(open_, close) * 1.008
            low = np.minimum(open_, close) * 0.992
            rows.extend(
                SectorOhlcv(
                    trade_date=dt.date(),
                    sector=sector,
                    open=float(round(open_[i], 2)),
                    high=float(round(high[i], 2)),
                    low=float(round(low[i], 2)),
                    close=float(round(close[i], 2)),
                    volume=int(10000000),
                )
                for i, dt in enumerate(dates)
            )
        return rows

    @staticmethod
    def _build_earnings_event_rows(profiles: dict[str, dict[str, object]], latest_date: date) -> list[EarningsEvent]:
        event_date = latest_date - timedelta(days=30)
        return [
            EarningsEvent(
                symbol=symbol,
                earnings_date=event_date,
                release_ts=datetime(event_date.year, event_date.month, event_date.day, 15, 30),
                session="after_close",
            )
            for symbol in profiles
        ]

    @staticmethod
    def _build_fundamental_rows(profiles: dict[str, dict[str, object]], latest_date: date) -> list[FundamentalsPti]:
        rows: list[FundamentalsPti] = []
        for i, (symbol, profile) in enumerate(profiles.items(), start=1):
            tag = str(profile["tag"])
            eps_growth = 0.32 if tag == "canslim_pass" else (0.12 if tag == "canslim_fail" else 0.18)
            sales_growth = 0.26 if tag == "canslim_pass" else (0.09 if tag == "canslim_fail" else 0.14)
            if tag in {"trend", "vcp", "rs_high", "sector_leader"}:
                eps_growth = max(eps_growth, 0.22)
                sales_growth = max(sales_growth, 0.18)
            rows.append(
                FundamentalsPti(
                    asof_date=date(2026, 3, 31),
                    effective_date=date(2026, 4, 15),
                    symbol=symbol,
                    revenue=100000000000 + i * 3000000000,
                    eps=800 + i * 30,
                    op_margin=0.12,
                    roe=0.16,
                    gross_profitability=0.35,
                    quarterly_eps_growth=eps_growth,
                    sales_growth=sales_growth,
                )
            )
            rows.append(
                FundamentalsPti(
                    asof_date=date(2026, 6, 30),
                    effective_date=date(2026, 7, 15),
                    symbol=symbol,
                    revenue=120000000000 + i * 3000000000,
                    eps=950 + i * 30,
                    op_margin=0.13,
                    roe=0.17,
                    gross_profitability=0.36,
                    quarterly_eps_growth=0.60,
                    sales_growth=0.50,
                )
            )
        return rows
