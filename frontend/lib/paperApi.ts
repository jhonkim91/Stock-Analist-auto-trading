import {
  callApi,
  type PaperBotRunRequest,
  type PaperBotRunResponse,
  type PaperBotStatus,
  type PaperBotStopResponse,
  type PaperCancelRequest,
  type PaperCancelResponse,
  type PaperFillsResponse,
  type PaperOrderListResponse,
  type PaperPortfolioResponse,
  type PaperPositionsResponse,
  type PaperPreviewRequest,
  type PaperPreviewResponse,
  type PaperStatus,
  type PaperSubmitRequest,
  type PaperSubmitResponse,
  type PaperSyncResponse
} from "./api";

/** 모의투자 런타임 안전 상태를 조회한다. */
export function getPaperStatus() {
  return callApi<PaperStatus>("/api/paper/status");
}

/** 모의투자 주문 목록을 조회한다. */
export function listPaperOrders() {
  return callApi<PaperOrderListResponse>("/api/paper/orders");
}

/** 모의투자 체결 목록을 조회한다. */
export function listPaperFills() {
  return callApi<PaperFillsResponse>("/api/paper/fills");
}

/** 모의투자 포지션 목록을 조회한다. */
export function listPaperPositions() {
  return callApi<PaperPositionsResponse>("/api/paper/positions");
}

/** 모의투자 포트폴리오 스냅샷을 조회한다. */
export function getPaperPortfolio() {
  return callApi<PaperPortfolioResponse>("/api/paper/portfolio");
}

/** 모의투자 주문 preview를 수행한다. */
export function previewPaperOrder(payload: PaperPreviewRequest) {
  return callApi<PaperPreviewResponse>("/api/paper/orders/preview", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

/** 명시적 확인값이 포함된 모의투자 주문 submit을 요청한다. */
export function submitPaperOrder(payload: PaperSubmitRequest) {
  return callApi<PaperSubmitResponse>("/api/paper/orders/submit", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

/** 명시적 확인값이 포함된 모의투자 주문 cancel을 요청한다. */
export function cancelPaperOrder(payload: PaperCancelRequest) {
  return callApi<PaperCancelResponse>("/api/paper/orders/cancel", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

/** 모의투자 상태 동기화를 요청한다. */
export function syncPaperState(scope = "all") {
  return callApi<PaperSyncResponse>("/api/paper/sync", {
    method: "POST",
    body: JSON.stringify({ scope })
  });
}

/** paper-only bot 상태를 조회한다. */
export function getBotStatus() {
  return callApi<PaperBotStatus>("/api/bot/status");
}

/** paper-only bot run-once preview loop를 실행한다. */
export function runBotOnce(payload: PaperBotRunRequest = {}) {
  return callApi<PaperBotRunResponse>("/api/bot/run-once", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

/** paper-only bot scheduler stop 요청을 보낸다. */
export function stopBot() {
  return callApi<PaperBotStopResponse>("/api/bot/stop", {
    method: "POST"
  });
}
