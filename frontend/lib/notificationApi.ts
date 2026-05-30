import {
  callApi,
  type NotificationStatus,
  type NotificationTestRequest,
  type NotificationTestResponse,
  type ReportNotifyRequest,
  type ReportNotifyResponse
} from "./api";

/** 알림 채널 상태를 secret 원문 없이 조회한다. */
export function getNotificationStatus() {
  return callApi<NotificationStatus>("/api/notifications/status");
}

/** 알림 test 메시지를 dry-run 기본값으로 요청한다. */
export function sendNotificationTest(payload: NotificationTestRequest) {
  return callApi<NotificationTestResponse>("/api/notifications/test", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

/** 저장된 리포트의 알림 전송 또는 dry-run을 요청한다. */
export function notifyReport(reportId: string, payload: ReportNotifyRequest) {
  return callApi<ReportNotifyResponse>(`/api/reports/${encodeURIComponent(reportId)}/notify`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
