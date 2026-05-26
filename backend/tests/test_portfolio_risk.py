from __future__ import annotations

from datetime import date, datetime

import pytest

from backend.app.models.tables import Position, ScreenResult, SymbolMaster
from backend.app.services.portfolio_service import PortfolioService


def test_portfolio_risk_summary_defaults_without_open_positions(client):
    response = client.get("/api/portfolio/risk")

    assert response.status_code == 200
    payload = response.json()
    for key in (
        "account_equity",
        "risk_per_trade",
        "max_daily_loss",
        "open_positions_count",
        "total_position_notional",
        "available_risk_budget",
        "warnings",
        "latest_signal_date",
        "proposed_positions",
        "proposed_notional",
        "broker_mode",
    ):
        assert key in payload
    assert payload["open_positions_count"] == 0
    assert payload["proposed_positions"] == 0
    assert payload["gross_exposure"] == 0
    assert payload["max_open_positions"] == 5
    assert payload["sector_exposure"]["combined"] == {}
    assert payload["symbol_exposure"]["combined"] == {}
    assert payload["strategy_exposure"]["combined"] == {}
    assert payload["daily_loss_budget"]["max_loss_amount"] == 3000000.0
    assert payload["gap_risk_estimate"]["status"] == "not_available"


def test_portfolio_risk_summary_calculates_concentration_and_daily_budget(db_session):
    db_session.add_all(
        [
            SymbolMaster(symbol="RISK1", name="Risk One", sector="Technology"),
            SymbolMaster(symbol="RISK2", name="Risk Two", sector="Technology"),
            SymbolMaster(symbol="RISK3", name="Risk Three", sector="Financials"),
        ]
    )
    db_session.add_all(
        [
            Position(
                symbol="RISK1",
                entry_ts=datetime(2026, 5, 20, 9, 0, 0),
                avg_price=25000000.0,
                qty=1,
                stop_price=24500000.0,
                strategy_tag="momentum",
            ),
            Position(
                symbol="RISK2",
                entry_ts=datetime(2026, 5, 20, 9, 0, 0),
                avg_price=20000000.0,
                qty=1,
                stop_price=19500000.0,
                strategy_tag="momentum",
            ),
            Position(
                symbol="RISK3",
                entry_ts=datetime(2026, 5, 20, 9, 0, 0),
                avg_price=5000000.0,
                qty=1,
                stop_price=4900000.0,
                strategy_tag="mean_reversion",
            ),
            ScreenResult(
                trade_date=date(2026, 5, 20),
                symbol="RISK1",
                strategy_tag="breakout",
                passed=True,
                pass_flags="{}",
                failed_conditions="[]",
                reason_summary="passed",
                total_score=0.95,
                entry_price=10000000.0,
                stop_price=9500000.0,
                risk_per_share=500000.0,
                position_size=1,
                position_notional=10000000.0,
            ),
        ]
    )
    db_session.commit()

    payload = PortfolioService(db_session).risk_summary()

    assert payload["open_positions_count"] == 3
    assert payload["proposed_positions"] == 1
    assert payload["gross_exposure"] == 50000000.0
    assert payload["proposed_gross_exposure"] == 10000000.0
    assert payload["combined_gross_exposure"] == 60000000.0
    assert payload["gross_exposure_pct"] == pytest.approx(0.5)
    assert payload["combined_gross_exposure_pct"] == pytest.approx(0.6)

    sector = payload["sector_exposure"]["combined"]
    assert sector["Technology"]["notional"] == 55000000.0
    assert sector["Technology"]["pct_of_equity"] == pytest.approx(0.55)
    assert sector["Technology"]["count"] == 3

    symbol = payload["symbol_exposure"]["combined"]
    assert symbol["RISK1"]["notional"] == 35000000.0
    assert symbol["RISK1"]["pct_of_equity"] == pytest.approx(0.35)

    strategy = payload["strategy_exposure"]["combined"]
    assert strategy["momentum"]["notional"] == 45000000.0
    assert strategy["momentum"]["pct_of_equity"] == pytest.approx(0.45)

    daily_loss = payload["daily_loss_budget"]
    assert daily_loss["max_loss_amount"] == 3000000.0
    assert daily_loss["current_open_risk"] == 1100000.0
    assert daily_loss["proposed_open_risk"] == 500000.0
    assert daily_loss["combined_open_risk"] == 1600000.0
    assert daily_loss["remaining_after_combined_open_risk"] == 1400000.0

    warnings = payload["concentration_warnings"]
    assert any("RISK1" in warning and "symbol" in warning for warning in warnings)
    assert any("Technology" in warning and "sector" in warning for warning in warnings)


def test_portfolio_gap_risk_missing_data_is_not_available(db_session):
    db_session.add(SymbolMaster(symbol="MISS1", name="Missing One", sector="Technology"))
    db_session.add(
        ScreenResult(
            trade_date=date(2026, 5, 20),
            symbol="MISS1",
            strategy_tag="breakout",
            passed=True,
            pass_flags="{}",
            failed_conditions="[]",
            reason_summary="missing risk data",
            total_score=0.8,
            position_size=0,
            position_notional=0.0,
        )
    )
    db_session.commit()

    payload = PortfolioService(db_session).risk_summary()

    assert payload["proposed_positions"] == 1
    assert payload["gap_risk_estimate"]["status"] == "not_available"
    assert payload["gap_risk_estimate"]["amount"] is None
    assert payload["gap_risk_estimate"]["missing_symbols"] == ["MISS1"]
