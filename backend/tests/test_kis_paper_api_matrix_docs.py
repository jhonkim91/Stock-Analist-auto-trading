from __future__ import annotations

from pathlib import Path

from backend.app.brokers import kis_paper


ROOT = Path(__file__).resolve().parents[2]


def test_kis_paper_api_matrix_matches_current_adapter_constants() -> None:
    """KIS paper 공식 확인 matrix가 현재 adapter 상수와 동기화되어 있는지 검증한다."""
    matrix = ROOT.joinpath("docs/KIS_PAPER_API_MATRIX.md").read_text(encoding="utf-8")
    research = ROOT.joinpath("docs/research/kis-paper-api-confirmation-matrix.md").read_text(encoding="utf-8")
    combined = f"{matrix}\n{research}"

    expected = {
        "KIS_ORDER_CASH_PATH": "/uapi/domestic-stock/v1/trading/order-cash",
        "KIS_ORDER_CANCEL_PATH": "/uapi/domestic-stock/v1/trading/order-rvsecncl",
        "KIS_DAILY_CCLD_PATH": "/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
        "KIS_BALANCE_PATH": "/uapi/domestic-stock/v1/trading/inquire-balance",
        "KIS_OVERSEAS_ORDER_PATH": "/uapi/overseas-stock/v1/trading/order",
        "KIS_OVERSEAS_ORDER_CANCEL_PATH": "/uapi/overseas-stock/v1/trading/order-rvsecncl",
        "KIS_OVERSEAS_CCLD_PATH": "/uapi/overseas-stock/v1/trading/inquire-ccnl",
        "KIS_OVERSEAS_BALANCE_PATH": "/uapi/overseas-stock/v1/trading/inquire-balance",
        "KIS_PAPER_BUY_TR_ID": "VTTC0012U",
        "KIS_PAPER_SELL_TR_ID": "VTTC0011U",
        "KIS_PAPER_CANCEL_TR_ID": "VTTC0013U",
        "KIS_PAPER_DAILY_CCLD_TR_ID": "VTTC0081R",
        "KIS_PAPER_BALANCE_TR_ID": "VTTC8434R",
        "KIS_PAPER_US_BUY_TR_ID": "VTTT1002U",
        "KIS_PAPER_US_SELL_TR_ID": "VTTT1006U",
        "KIS_PAPER_OVERSEAS_CANCEL_TR_ID": "VTTT1004U",
        "KIS_PAPER_OVERSEAS_CCLD_TR_ID": "VTTS3035R",
        "KIS_PAPER_OVERSEAS_BALANCE_TR_ID": "VTTS3012R",
    }

    for name, value in expected.items():
        assert getattr(kis_paper, name) == value
        assert value in combined

    assert "33e0e1e65cd1c8c8b639531483ec0b327087bab1" in combined
    assert "KIS_PAPER_US_DAYTIME_ORDER_UNSUPPORTED" in combined
    assert "live fallback" in combined
    assert "실계좌 주문/취소/체결 금지" in combined
    assert "현재 token service는 disabled/status-only" not in combined
    assert "KIS paper endpoint/TR-ID/request field는 여전히 추정 구현하지 않는다" not in combined
