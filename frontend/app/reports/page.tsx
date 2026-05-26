"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { PaperModeBanner } from "../../components/paper-mode-banner";
import {
  callApi,
  reportMarkdownUrl,
  type ApiStatus,
  type ReportDetail,
  type ReportItem,
  type ReportNotifyResponse
} from "../../lib/api";

function Metric({ label, value }: { label: string; value: string | number | boolean | null | undefined }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value === undefined || value === null ? "-" : String(value)}</strong>
    </div>
  );
}

export default function ReportsPage() {
  const [status, setStatus] = useState<ApiStatus>("loading");
  const [message, setMessage] = useState("조회 중");
  const [notifyStatus, setNotifyStatus] = useState<ApiStatus>("idle");
  const [notifyMessage, setNotifyMessage] = useState("notify 대기");
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [selectedReport, setSelectedReport] = useState<ReportDetail | null>(null);
  const [notifyResult, setNotifyResult] = useState<ReportNotifyResponse | null>(null);
  const [showRaw, setShowRaw] = useState(false);

  const loadDetail = useCallback(async (reportId: string) => {
    const detail = await callApi<ReportDetail>(`/api/reports/${encodeURIComponent(reportId)}`);
    setSelectedReport(detail);
    setNotifyResult(null);
    setNotifyStatus("idle");
    setNotifyMessage("notify 대기");
  }, []);

  const loadReports = useCallback(
    async (showLoading = true) => {
      if (showLoading) {
        setStatus("loading");
        setMessage("조회 중");
      }
      try {
        const list = await callApi<ReportItem[]>("/api/reports?limit=20");
        setReports(list);
        if (list[0]) {
          await loadDetail(list[0].id);
        } else {
          setSelectedReport(null);
          setNotifyResult(null);
        }
        setStatus("ok");
        setMessage(`조회 완료: ${list.length}건`);
      } catch (error) {
        setStatus("error");
        setMessage(error instanceof Error ? error.message : "조회 실패");
        setReports([]);
        setSelectedReport(null);
        setNotifyResult(null);
      }
    },
    [loadDetail]
  );

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadReports(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadReports]);

  async function selectReport(reportId: string) {
    setStatus("loading");
    setMessage("상세 조회 중");
    try {
      await loadDetail(reportId);
      setStatus("ok");
      setMessage("상세 조회 완료");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "상세 조회 실패");
    }
  }

  async function notifySelectedReport() {
    if (!selectedReport) {
      return;
    }
    setNotifyStatus("loading");
    setNotifyMessage("모의투자 리포트 notify 요청 중");
    try {
      const result = await callApi<ReportNotifyResponse>(
        `/api/reports/${encodeURIComponent(selectedReport.id)}/notify`,
        {
          method: "POST",
          body: JSON.stringify({ mode: "summary", dry_run: true })
        }
      );
      setNotifyResult(result);
      setNotifyStatus(result.ok ? "ok" : "error");
      setNotifyMessage(result.ok ? `notify ${result.status}` : "notify 실패");
    } catch (error) {
      setNotifyStatus("error");
      setNotifyMessage(error instanceof Error ? error.message : "notify 실패");
      setNotifyResult(null);
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Phase 8 · Reports</p>
          <h1>Reports</h1>
        </div>
        <nav className="nav">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/data">Data</Link>
          <Link href="/screener">Screener</Link>
          <Link href="/backtest">Backtest</Link>
          <Link href="/portfolio">Portfolio</Link>
          <Link href="/paper">Paper</Link>
          <Link href="/settings">Settings</Link>
        </nav>
        <span className={`status ${status}`}>{message}</span>
      </header>

      <PaperModeBanner title="모의투자 리포트 알림 · 실거래 아님" />

      <section className="grid wideLeft">
        <div className="tableWrap">
          <table>
            <thead>
              <tr>
                <th>id</th>
                <th>report_date</th>
                <th>report_type</th>
                <th>title</th>
                <th>model_version</th>
                <th>strategy_version</th>
                <th>data_timestamp</th>
                <th>created_at</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((report) => (
                <tr
                  key={report.id}
                  className={selectedReport?.id === report.id ? "selectedRow" : ""}
                  role="button"
                  tabIndex={0}
                  onClick={() => selectReport(report.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      void selectReport(report.id);
                    }
                  }}
                >
                  <td>{report.id}</td>
                  <td>{report.report_date}</td>
                  <td>{report.report_type}</td>
                  <td>{report.title}</td>
                  <td>{report.model_version}</td>
                  <td>{report.strategy_version}</td>
                  <td>{report.data_timestamp}</td>
                  <td>{report.created_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <aside className="detailPanel">
          <div className="sectionHeader">
            <h2>Latest Report</h2>
            {selectedReport ? (
              <a className="textLink" href={reportMarkdownUrl(selectedReport.id)} download={`report-${selectedReport.id}.md`}>
                markdown 다운로드
              </a>
            ) : null}
          </div>
          {selectedReport ? (
            <>
              <p className="strongLine">{selectedReport.title}</p>
              <div className="metricGrid">
                <Metric label="date" value={selectedReport.report_date} />
                <Metric label="model" value={selectedReport.model_version} />
                <Metric label="strategy" value={selectedReport.strategy_version} />
                <Metric label="data" value={selectedReport.data_timestamp} />
              </div>
              <div className="toolbar compactToolbar">
                <button type="button" onClick={() => setShowRaw(false)}>
                  Markdown Preview
                </button>
                <button type="button" className="secondary" onClick={() => setShowRaw(true)}>
                  Raw Markdown
                </button>
                <button type="button" className="secondary" onClick={notifySelectedReport}>
                  Notify dry-run
                </button>
              </div>
              <div className="metricGrid">
                <Metric label="notify_status" value={notifyResult?.status ?? notifyMessage} />
                <Metric label="dry_run" value={notifyResult?.dry_run ?? true} />
                <Metric label="secrets_redacted" value={notifyResult?.secrets_redacted ?? "-"} />
                <Metric label="message_count" value={notifyResult?.message_count ?? "-"} />
              </div>
              <span className={`status ${notifyStatus}`}>{notifyMessage}</span>
              <pre className={showRaw ? "markdownPreview rawMarkdown" : "markdownPreview"}>{selectedReport.markdown}</pre>
            </>
          ) : (
            <p className="muted">생성된 리포트가 없습니다.</p>
          )}
        </aside>
      </section>
    </main>
  );
}
