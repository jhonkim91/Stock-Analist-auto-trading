import { formatNumber, formatPercent, type StrategyValidationSummary } from "../lib/api";

type ValidationSummaryCardProps = {
  summary: StrategyValidationSummary | null;
  message?: string;
};

function numericValue(value: number | string | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function average(values: Array<number | null>) {
  const valid = values.filter((value): value is number => value !== null);
  if (valid.length === 0) {
    return null;
  }
  return valid.reduce((sum, value) => sum + value, 0) / valid.length;
}

/** /api/backtest/strategy-summary의 walk-forward/PBO/DSR 요약을 목업형 카드로 렌더링한다. */
export function ValidationSummaryCard({ summary, message = "summary loading" }: ValidationSummaryCardProps) {
  if (!summary) {
    return (
      <div className="validationGrid">
        <article className="validationCard">
          <h2>Walk-forward OOS</h2>
          <p className="validationValue neu">{message}</p>
          <p className="muted">train/test windows loading</p>
        </article>
        <article className="validationCard">
          <h2>PBO</h2>
          <p className="validationValue neu">waiting</p>
          <p className="muted">probability of backtest overfitting</p>
        </article>
        <article className="validationCard">
          <h2>Deflated Sharpe</h2>
          <p className="validationValue neu">waiting</p>
          <p className="muted">multiple testing adjusted</p>
        </article>
      </div>
    );
  }

  const walkForward = summary.validation_framework.walk_forward;
  const pbo = summary.validation_framework.overfitting.pbo;
  const dsr = summary.validation_framework.overfitting.deflated_sharpe_ratio;
  const windowCount = walkForward.strategy_summaries.reduce(
    (count, row) => count + (typeof row.summary?.oos_window_count === "number" ? row.summary.oos_window_count : 0),
    0
  );
  const averageOosReturn = average(
    walkForward.strategy_summaries.map((row) => numericValue(row.summary?.oos_total_return ?? undefined))
  );
  const pboValue = numericValue(typeof pbo.value === "number" ? pbo.value : pbo.probability_of_backtest_overfitting);
  const dsrValue = numericValue(typeof dsr.value === "number" ? dsr.value : dsr.deflated_sharpe_ratio);

  return (
    <div className="validationGrid">
      <article className="validationCard">
        <h2>Walk-forward OOS</h2>
        {walkForward.calculated ? (
          <>
            <p className="validationValue pos">
              {formatNumber(windowCount)} windows · avg {formatPercent(averageOosReturn)}
            </p>
            <p className="muted">
              train {walkForward.train_window_trading_days}d / test {walkForward.test_window_trading_days}d / step{" "}
              {walkForward.step_trading_days}d
            </p>
          </>
        ) : (
          <p className="validationValue warn">{walkForward.reason ?? "insufficient data"}</p>
        )}
      </article>

      <article className="validationCard">
        <h2>PBO</h2>
        {pbo.calculated && pboValue !== null ? (
          <p className={`validationValue ${pboValue > 0.5 ? "neg" : "pos"}`}>{formatPercent(pboValue)}</p>
        ) : (
          <p className="validationValue neu">{pbo.reason ?? "not_available"}</p>
        )}
        <p className="muted">probability of backtest overfitting</p>
      </article>

      <article className="validationCard">
        <h2>Deflated Sharpe</h2>
        {dsr.calculated && dsrValue !== null ? (
          <p className="validationValue">{formatNumber(dsrValue, 3)}</p>
        ) : (
          <p className="validationValue neu">{dsr.reason ?? "not_available"}</p>
        )}
        <p className="muted">multiple testing adjusted</p>
      </article>
    </div>
  );
}
