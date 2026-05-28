"use client";

import { useCallback, useEffect, useState } from "react";

import { callApi, reportMarkdownUrl, type ApiStatus, type ReportDetail, type ReportItem } from "../../lib/api";

function PageIcon() {
  return (
    <svg className="pageTitleIcon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 3h7l4 4v14H7z" />
      <path d="M14 3v5h5" />
      <path d="M9 13h6M9 17h6" />
    </svg>
  );
}

function StatRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="stat-row">
      <span className="stat-k">{label}</span>
      <span>{value}</span>
    </div>
  );
}

function Badge({ children, tone }: { children: React.ReactNode; tone?: string }) {
  return <span className={`bdg ${tone ?? "bdg-info"}`}>{children}</span>;
}

export default function ReportsPage() {
  const [status, setStatus] = useState<ApiStatus>("loading");
  const [message, setMessage] = useState("조회 중");
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [selectedReport, setSelectedReport] = useState<ReportDetail | null>(null);

  const loadDetail = useCallback(async (reportId: string) => {
    const detail = await callApi<ReportDetail>(`/api/reports/${encodeURIComponent(reportId)}`);
    setSelectedReport(detail);
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
        }
        setStatus("ok");
        setMessage(`조회 완료: ${list.length}건`);
      } catch (error) {
        setStatus("error");
        setMessage(error instanceof Error ? error.message : "조회 실패");
        setReports([]);
        setSelectedReport(null);
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

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <PageIcon />
          <h1>Reports</h1>
        </div>
        <div className="topbar-actions" title={message}>
          <span className={`status ${status}`}>{message}</span>
        </div>
      </header>

      <section className="scroll">
        <div className="g2">
          <article>
            <div className="card-hd">
              <span className="card-title">리포트 목록</span>
              <span className="muted">최근 20건</span>
            </div>
            <div className="tableWrap">
              <table className="tbl mockCompactTable">
                <thead>
                  <tr>
                    <th style={{ width: "24%" }}>날짜</th>
                    <th style={{ width: "20%" }}>유형</th>
                    <th>제목</th>
                  </tr>
                </thead>
                <tbody>
                  {reports.map((report) => (
                    <tr
                      key={report.id}
                      className={selectedReport?.id === report.id ? "selectedRow" : ""}
                      role="button"
                      tabIndex={0}
                      onClick={() => void selectReport(report.id)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          void selectReport(report.id);
                        }
                      }}
                    >
                      <td>{report.report_date}</td>
                      <td>
                        <Badge>{report.report_type}</Badge>
                      </td>
                      <td>{report.title}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>

          <article>
            <div className="card-hd">
              <span className="card-title">선택된 리포트</span>
              {selectedReport ? (
                <a className="textLink" href={reportMarkdownUrl(selectedReport.id)} download={`report-${selectedReport.id}.md`}>
                  markdown
                </a>
              ) : null}
            </div>
            {selectedReport ? (
              <>
                <div className="strongLine">{selectedReport.title}</div>
                <StatRow label="date" value={selectedReport.report_date} />
                <StatRow label="model_version" value={<span className="muted">{selectedReport.model_version}</span>} />
                <StatRow label="strategy_version" value={<span className="muted">{selectedReport.strategy_version}</span>} />
                <pre className="markdownPreview">{selectedReport.markdown}</pre>
              </>
            ) : (
              <p className="muted">생성된 리포트가 없습니다.</p>
            )}
          </article>
        </div>
      </section>
    </main>
  );
}
