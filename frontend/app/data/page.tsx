"use client";

import Link from "next/link";
import { ChangeEvent, KeyboardEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  callApi,
  formatNumber,
  type ApiStatus,
  type DataPreviewRow,
  type DataQualityCheck,
  type DataSourceConfig,
  type ImportRun
} from "../../lib/api";

function StatusPill({ status, text }: { status: ApiStatus; text: string }) {
  return <span className={`status ${status}`}>{text}</span>;
}

function Metric({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value ?? "-"}</strong>
    </div>
  );
}

function Badge({ children, tone }: { children: React.ReactNode; tone?: string }) {
  return <span className={`badge ${tone ?? ""}`}>{children}</span>;
}

function PreviewTable({ rows }: { rows: DataPreviewRow[] }) {
  if (!rows.length) {
    return <p className="muted">preview row가 없습니다.</p>;
  }
  return (
    <div className="tableWrap compactTable">
      <table>
        <thead>
          <tr>
            <th>row</th>
            <th>trade_date</th>
            <th>symbol</th>
            <th>open</th>
            <th>high</th>
            <th>low</th>
            <th>close</th>
            <th>volume</th>
            <th>venue</th>
            <th>flags</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.row_number}-${row.symbol}-${row.trade_date}`}>
              <td>{row.row_number}</td>
              <td>{row.trade_date}</td>
              <td>{row.symbol}</td>
              <td>{formatNumber(row.open, 2)}</td>
              <td>{formatNumber(row.high, 2)}</td>
              <td>{formatNumber(row.low, 2)}</td>
              <td>{formatNumber(row.close, 2)}</td>
              <td>{formatNumber(row.volume)}</td>
              <td>{row.venue}</td>
              <td className="summaryCell">{row.quality_flags.join(", ") || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function QualityTable({ checks }: { checks: DataQualityCheck[] }) {
  if (!checks.length) {
    return <p className="muted">quality check가 없습니다.</p>;
  }
  return (
    <div className="tableWrap compactTable">
      <table>
        <thead>
          <tr>
            <th>severity</th>
            <th>row</th>
            <th>symbol</th>
            <th>trade_date</th>
            <th>field</th>
            <th>check_code</th>
            <th>message</th>
          </tr>
        </thead>
        <tbody>
          {checks.map((check) => (
            <tr key={check.id}>
              <td>
                <Badge tone={check.severity === "error" ? "fail" : check.severity === "warning" ? "gradeC" : "pass"}>
                  {check.severity}
                </Badge>
              </td>
              <td>{check.row_number ?? "-"}</td>
              <td>{check.symbol ?? "-"}</td>
              <td>{check.trade_date ?? "-"}</td>
              <td>{check.field ?? "-"}</td>
              <td>{check.check_code}</td>
              <td className="summaryCell">{check.message}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function DataPage() {
  const [status, setStatus] = useState<ApiStatus>("loading");
  const [message, setMessage] = useState("조회 중");
  const [sources, setSources] = useState<DataSourceConfig[]>([]);
  const [selectedSource, setSelectedSource] = useState("csv_krx");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [runs, setRuns] = useState<ImportRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<ImportRun | null>(null);
  const [qualityChecks, setQualityChecks] = useState<DataQualityCheck[]>([]);
  const [validationRun, setValidationRun] = useState<ImportRun | null>(null);
  const [confirmRun, setConfirmRun] = useState<ImportRun | null>(null);
  const [actionStatus, setActionStatus] = useState<ApiStatus>("idle");
  const [actionMessage, setActionMessage] = useState("CSV 파일을 선택하세요");

  const activeSources = useMemo(() => sources.filter((source) => source.enabled), [sources]);

  const loadRuns = useCallback(async () => {
    const data = await callApi<ImportRun[]>("/api/data/import-runs?limit=20");
    setRuns(data);
    return data;
  }, []);

  const loadRunDetail = useCallback(async (runId: string) => {
    const [run, checks] = await Promise.all([
      callApi<ImportRun>(`/api/data/import-runs/${encodeURIComponent(runId)}`),
      callApi<DataQualityCheck[]>(`/api/data/quality/${encodeURIComponent(runId)}`)
    ]);
    setSelectedRun(run);
    setQualityChecks(checks);
    return run;
  }, []);

  const loadPage = useCallback(async (showLoading = true) => {
    if (showLoading) {
      setStatus("loading");
      setMessage("조회 중");
    }
    try {
      const [sourceData, runData] = await Promise.all([callApi<DataSourceConfig[]>("/api/data/sources"), loadRuns()]);
      setSources(sourceData);
      if (!sourceData.some((source) => source.source_id === selectedSource)) {
        setSelectedSource(sourceData.find((source) => source.enabled)?.source_id ?? "csv_krx");
      }
      if (runData[0]) {
        await loadRunDetail(runData[0].run_id);
      }
      setStatus("ok");
      setMessage("조회 완료");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "조회 실패");
    }
  }, [loadRunDetail, loadRuns, selectedSource]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadPage(false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadPage]);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFile(event.target.files?.[0] ?? null);
    setValidationRun(null);
    setConfirmRun(null);
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
      setConfirmRun(null);
      await loadRuns();
      await loadRunDetail(run.run_id);
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
      setConfirmRun(run);
      await loadRuns();
      await loadRunDetail(run.run_id);
      setActionStatus("ok");
      setActionMessage("Import confirm 완료");
    } catch (error) {
      setActionStatus("error");
      setActionMessage(error instanceof Error ? error.message : "Import confirm 실패");
    }
  }

  function handleRunKeyDown(event: KeyboardEvent<HTMLTableRowElement>, runId: string) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      void loadRunDetail(runId);
    }
  }

  const summaryRun = validationRun ?? selectedRun;

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Phase 3A</p>
          <h1>Data Quality</h1>
        </div>
        <nav className="nav">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/data">Data</Link>
          <Link href="/screener">Screener</Link>
          <Link href="/reports">Reports</Link>
          <Link href="/backtest">Backtest</Link>
          <Link href="/portfolio">Portfolio</Link>
          <Link href="/settings">Settings</Link>
        </nav>
        <StatusPill status={status} text={message} />
      </header>

      <section className="panel">
        <div className="sectionHeader">
          <div>
            <h2>CSV Validation Preview</h2>
            <p className="muted">validate 단계는 import_runs와 data_quality_checks만 기록한다.</p>
          </div>
          <StatusPill status={actionStatus} text={actionMessage} />
        </div>
        <div className="formRow">
          <label>
            source_id
            <select value={selectedSource} onChange={(event) => setSelectedSource(event.target.value)}>
              {activeSources.map((source) => (
                <option key={source.source_id} value={source.source_id}>
                  {source.source_id}
                </option>
              ))}
            </select>
          </label>
          <label>
            CSV file
            <input type="file" accept=".csv,text/csv" onChange={handleFileChange} />
          </label>
          <button type="button" onClick={validateCsv}>
            Validate CSV
          </button>
          <button type="button" className="secondary" disabled={!validationRun?.can_confirm} onClick={confirmImport}>
            Confirm Import
          </button>
        </div>
      </section>

      <section className="cardGrid compactCards">
        <article>
          <h2>status</h2>
          <p className="bigNumber">{summaryRun?.status ?? "-"}</p>
        </article>
        <article>
          <h2>total_rows</h2>
          <p className="bigNumber">{formatNumber(summaryRun?.total_rows)}</p>
        </article>
        <article>
          <h2>valid_rows</h2>
          <p className="bigNumber">{formatNumber(summaryRun?.valid_rows)}</p>
        </article>
        <article>
          <h2>errors</h2>
          <p className="bigNumber">{formatNumber(summaryRun?.error_count)}</p>
        </article>
        <article>
          <h2>warnings</h2>
          <p className="bigNumber">{formatNumber(summaryRun?.warning_count)}</p>
        </article>
        <article>
          <h2>info</h2>
          <p className="bigNumber">{formatNumber(summaryRun?.info_count)}</p>
        </article>
        <article>
          <h2>inserted</h2>
          <p className="bigNumber">{formatNumber(confirmRun?.inserted_count ?? summaryRun?.inserted_count)}</p>
        </article>
        <article>
          <h2>updated</h2>
          <p className="bigNumber">{formatNumber(confirmRun?.updated_count ?? summaryRun?.updated_count)}</p>
        </article>
      </section>

      <section className="grid">
        <article>
          <h2>Data Sources</h2>
          <div className="sourceList">
            {sources.map((source) => (
              <div className="metric" key={source.source_id}>
                <span>{source.source_id}</span>
                <strong>{source.provider_type}</strong>
                <p className="muted">
                  {source.enabled ? "enabled" : "disabled"} / {source.market} / {source.venue} / max {formatNumber(source.max_rows)}
                </p>
              </div>
            ))}
          </div>
        </article>
        <article>
          <h2>Import Run Detail</h2>
          <pre className="tinyPre">{JSON.stringify(selectedRun ?? {}, null, 2)}</pre>
        </article>
      </section>

      <section className="panel">
        <div className="sectionHeader">
          <h2>Preview Rows</h2>
          <p className="muted">최대 100개 row</p>
        </div>
        <PreviewTable rows={summaryRun?.preview_rows ?? []} />
      </section>

      <section className="panel">
        <h2>Data Quality</h2>
        <QualityTable checks={qualityChecks} />
      </section>

      <section className="panel">
        <h2>Import History</h2>
        <div className="tableWrap">
          <table>
            <thead>
              <tr>
                <th>run_id</th>
                <th>source_id</th>
                <th>status</th>
                <th>can_confirm</th>
                <th>rows</th>
                <th>errors</th>
                <th>warnings</th>
                <th>inserted</th>
                <th>updated</th>
                <th>created_at</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr
                  key={run.run_id}
                  className={selectedRun?.run_id === run.run_id ? "selectedRow" : ""}
                  role="button"
                  tabIndex={0}
                  onClick={() => loadRunDetail(run.run_id)}
                  onKeyDown={(event) => handleRunKeyDown(event, run.run_id)}
                >
                  <td>{run.run_id}</td>
                  <td>{run.source_id}</td>
                  <td>{run.status}</td>
                  <td>{run.can_confirm ? "yes" : "no"}</td>
                  <td>{formatNumber(run.total_rows)}</td>
                  <td>{formatNumber(run.error_count)}</td>
                  <td>{formatNumber(run.warning_count)}</td>
                  <td>{formatNumber(run.inserted_count)}</td>
                  <td>{formatNumber(run.updated_count)}</td>
                  <td>{run.created_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
