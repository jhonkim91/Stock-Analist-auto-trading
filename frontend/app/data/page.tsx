"use client";

import { type ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  callApi,
  formatNumber,
  type ApiStatus,
  type DataQualitySummary,
  type DataSourceConfig,
  type ImportRun
} from "../../lib/api";

function PageIcon() {
  return (
    <svg className="pageTitleIcon" viewBox="0 0 24 24" aria-hidden="true">
      <ellipse cx="12" cy="5" rx="7" ry="3" />
      <path d="M5 5v6c0 1.7 3.1 3 7 3s7-1.3 7-3V5" />
      <path d="M5 11v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" />
    </svg>
  );
}

function StatusPill({ status, text }: { status: ApiStatus; text: string }) {
  return <span className={`status ${status}`}>{text}</span>;
}

function Badge({ children, tone }: { children: React.ReactNode; tone?: string }) {
  return <span className={`bdg ${tone ?? ""}`}>{children}</span>;
}

function Kpi({ label, tone, value }: { label: string; tone?: "pos" | "neg"; value: string }) {
  return (
    <div className="kpi">
      <div className="kpi-lbl">{label}</div>
      <div className={`kpi-val ${tone ?? ""}`}>{value}</div>
    </div>
  );
}

function isSafetyClosed(summary: DataQualitySummary | null) {
  const safety = summary?.safety_counts;
  return Boolean(
    safety &&
      safety.orders_count === 0 &&
      safety.paper_orders_count === 0 &&
      safety.paper_fills_count === 0 &&
      safety.paper_positions_count === 0 &&
      safety.paper_audit_events_count === 0 &&
      !safety.token_issued &&
      !safety.token_cache_enabled &&
      !safety.network_call_performed &&
      !safety.adapter_order_call_performed &&
      !safety.adapter_network_call_performed
  );
}

export default function DataPage() {
  const [status, setStatus] = useState<ApiStatus>("loading");
  const [message, setMessage] = useState("조회 중");
  const [sources, setSources] = useState<DataSourceConfig[]>([]);
  const [summary, setSummary] = useState<DataQualitySummary | null>(null);
  const [runs, setRuns] = useState<ImportRun[]>([]);
  const [selectedSource, setSelectedSource] = useState("csv_krx");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [validationRun, setValidationRun] = useState<ImportRun | null>(null);
  const [actionStatus, setActionStatus] = useState<ApiStatus>("idle");
  const [actionMessage, setActionMessage] = useState("CSV 파일을 선택하세요");

  const activeSources = useMemo(
    () => sources.filter((source) => source.enabled && source.provider_type === "csv"),
    [sources]
  );

  const loadPage = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setStatus("loading");
      setMessage("조회 중");
    }
    try {
      const [sourceData, summaryData, runData] = await Promise.all([
        callApi<DataSourceConfig[]>("/api/data/sources"),
        callApi<DataQualitySummary>("/api/data/quality-summary"),
        callApi<ImportRun[]>("/api/data/import-runs?limit=20")
      ]);
      setSources(sourceData);
      setSummary(summaryData);
      setRuns(runData);
      setSelectedSource((current) =>
        sourceData.some((source) => source.source_id === current)
          ? current
          : (sourceData.find((source) => source.enabled && source.provider_type === "csv")?.source_id ?? "csv_krx")
      );
      setStatus("ok");
      setMessage("조회 완료");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "조회 실패");
      setSources([]);
      setSummary(null);
      setRuns([]);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadPage(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadPage]);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFile(event.target.files?.[0] ?? null);
    setValidationRun(null);
  }

  async function validateCsv() {
    if (!selectedFile) {
      setActionStatus("error");
      setActionMessage("CSV 파일을 먼저 선택하세요");
      return;
    }
    setActionStatus("loading");
    setActionMessage("CSV 검증 중");
    const formData = new FormData();
    formData.append("source_id", selectedSource);
    formData.append("file", selectedFile);
    try {
      const run = await callApi<ImportRun>("/api/data/validate-csv", { method: "POST", body: formData });
      setValidationRun(run);
      await loadPage(false);
      setActionStatus(run.can_confirm ? "ok" : "error");
      setActionMessage(run.can_confirm ? "CSV 검증 완료" : "CSV 검증 실패");
    } catch (error) {
      setActionStatus("error");
      setActionMessage(error instanceof Error ? error.message : "CSV 검증 실패");
    }
  }

  async function confirmImport() {
    if (!validationRun?.can_confirm) {
      setActionStatus("error");
      setActionMessage("confirm 가능한 run이 없습니다.");
      return;
    }
    setActionStatus("loading");
    setActionMessage("Import confirm 중");
    try {
      const run = await callApi<ImportRun>("/api/data/import-csv-confirmed", {
        method: "POST",
        body: JSON.stringify({ run_id: validationRun.run_id })
      });
      setValidationRun(run);
      await loadPage(false);
      setActionStatus("ok");
      setActionMessage("Import confirm 완료");
    } catch (error) {
      setActionStatus("error");
      setActionMessage(error instanceof Error ? error.message : "Import confirm 실패");
    }
  }

  const safetyClosed = isSafetyClosed(summary);
  const coverageRatio = summary?.missing_rows.coverage_ratio;

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <PageIcon />
          <h1>Data Quality</h1>
        </div>
        <div className="topbar-actions" title={message}>
          <span className="muted">Phase 3B</span>
          <StatusPill status={status} text={message} />
        </div>
      </header>

      <section className="scroll">
        <div className="g4">
          <Kpi label="daily_rows" value={formatNumber(summary?.row_counts.daily_ohlcv)} />
          <Kpi label="active_symbols" value={formatNumber(summary?.row_counts.active_symbols)} />
          <Kpi label="coverage" value={coverageRatio === null || coverageRatio === undefined ? "-" : `${formatNumber(coverageRatio * 100, 1)}%`} tone="pos" />
          <Kpi label="safety_closed" value={String(safetyClosed)} tone={safetyClosed ? "pos" : "neg"} />
        </div>

        <div className="g2">
          <article>
            <div className="card-hd">
              <span className="card-title">CSV Validation</span>
              <button type="button" onClick={validateCsv}>
                Validate CSV
              </button>
            </div>
            <div className="mockFilters">
              <select value={selectedSource} onChange={(event) => setSelectedSource(event.target.value)}>
                {activeSources.map((source) => (
                  <option key={source.source_id} value={source.source_id}>
                    {source.source_id}
                  </option>
                ))}
              </select>
              <input type="file" accept=".csv,text/csv" onChange={handleFileChange} />
            </div>
            <div className="mockButtonRow">
              <button type="button" className="secondary" disabled={!validationRun?.can_confirm} onClick={confirmImport}>
                Confirm Import
              </button>
              <StatusPill status={actionStatus} text={actionMessage} />
            </div>
          </article>

          <article>
            <div className="card-hd">
              <span className="card-title">Source Freshness</span>
            </div>
            <div className="tableWrap">
              <table className="tbl mockCompactTable">
                <thead>
                  <tr>
                    <th>source_id</th>
                    <th>freshness</th>
                    <th>lag</th>
                  </tr>
                </thead>
                <tbody>
                  {(summary?.source_freshness ?? []).slice(0, 4).map((source) => (
                    <tr key={source.source_id}>
                      <td>{source.source_id}</td>
                      <td>
                        <Badge tone={source.freshness_status === "CURRENT" ? "bdg-ok" : source.freshness_status === "STALE" ? "bdg-warn" : "bdg-fail"}>
                          {source.freshness_status}
                        </Badge>
                      </td>
                      <td>{source.trading_date_lag ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>
        </div>

        <article className="mockTableCard">
          <div className="card-hd">
            <span className="card-title">Import History</span>
            <span className="muted">최근 20건</span>
          </div>
          <div className="tableWrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>run_id</th>
                  <th>source_id</th>
                  <th>status</th>
                  <th>can_confirm</th>
                  <th>rows</th>
                  <th>errors</th>
                  <th>warnings</th>
                  <th>created_at</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.run_id}>
                    <td>{run.run_id}</td>
                    <td>{run.source_id}</td>
                    <td>{run.status}</td>
                    <td>{run.can_confirm ? "yes" : "no"}</td>
                    <td>{formatNumber(run.total_rows)}</td>
                    <td>{formatNumber(run.error_count)}</td>
                    <td>{formatNumber(run.warning_count)}</td>
                    <td>{run.created_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </main>
  );
}
