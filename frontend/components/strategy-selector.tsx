import type { StrategyMetadata } from "../lib/api";

type StrategySelectorProps = {
  selected: string[];
  strategies: StrategyMetadata[];
  onChange: (strategies: string[]) => void;
};

function strategyTitle(strategy: StrategyMetadata) {
  const limitations = strategy.limitations.length ? strategy.limitations.join(", ") : "none";
  const required = strategy.required_fields.length ? strategy.required_fields.join(", ") : "none";
  return `${strategy.description}\nrequired: ${required}\nlimitations: ${limitations}`;
}

/** 전략 metadata를 default/available 구분 pill로 보여주고 선택 상태를 토글한다. */
export function StrategySelector({ selected, strategies, onChange }: StrategySelectorProps) {
  const selectedSet = new Set(selected);

  function toggle(name: string) {
    onChange(selectedSet.has(name) ? selected.filter((strategyName) => strategyName !== name) : [...selected, name]);
  }

  if (strategies.length === 0) {
    return <p className="muted">strategy metadata loading</p>;
  }

  return (
    <div>
      <p className="muted strategyHelp">Default 전략은 자동 선택 · Available 전략은 직접 추가</p>
      <div className="strategyPills" aria-label="Strategy selector">
        {strategies.map((strategy) => {
          const isSelected = selectedSet.has(strategy.name);
          return (
            <button
              aria-pressed={isSelected}
              className={`strategyPill ${isSelected ? "selected" : ""}`}
              key={strategy.name}
              onClick={() => toggle(strategy.name)}
              title={strategyTitle(strategy)}
              type="button"
            >
              <span aria-hidden="true" className="strategyPillIcon">
                {isSelected ? "✓" : "+"}
              </span>
              <span>{strategy.display_name}</span>
              <span className={`strategyTag ${strategy.is_default ? "default" : "available"}`}>
                {strategy.is_default ? "default" : "available"}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
