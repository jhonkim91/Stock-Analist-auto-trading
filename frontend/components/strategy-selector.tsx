import type { StrategyMetadata } from "../lib/api";

type StrategySelectorProps = {
  selected: string[];
  strategies: StrategyMetadata[];
  onChange: (strategies: string[]) => void;
};

function strategyTitle(strategy: StrategyMetadata) {
  const limitations = strategy.limitations.length ? strategy.limitations.join(", ") : "없음";
  const required = strategy.required_fields.length ? strategy.required_fields.join(", ") : "없음";
  return `${strategy.description}\n필수 항목: ${required}\n제한 사항: ${limitations}`;
}

/** 전략 metadata를 default/available 구분 pill로 보여주고 선택 상태를 토글한다. */
export function StrategySelector({ selected, strategies, onChange }: StrategySelectorProps) {
  const selectedSet = new Set(selected);

  function toggle(name: string) {
    onChange(selectedSet.has(name) ? selected.filter((strategyName) => strategyName !== name) : [...selected, name]);
  }

  if (strategies.length === 0) {
    return <p className="muted">전략 메타데이터 불러오는 중</p>;
  }

  return (
    <div>
      <p className="muted strategyHelp">Default 전략은 자동 선택 · Available 전략은 직접 추가</p>
      <div className="strategyPills" aria-label="전략 선택기">
        {strategies.map((strategy) => {
          const isSelected = selectedSet.has(strategy.name);
          return (
            <label
              className={`strategyPill ${isSelected ? "selected" : ""}`}
              key={strategy.name}
              title={strategyTitle(strategy)}
            >
              <span className="strategyCardTop">
                <input checked={isSelected} onChange={() => toggle(strategy.name)} type="checkbox" />
                <span>
                  <span className="strategyName">{strategy.name}</span>
                  <span className="strategyMeta">{strategy.display_name}</span>
                </span>
                <span className={`strategyTag ${strategy.is_default ? "default" : "available"}`}>
                  {strategy.is_default ? "기본" : "랭킹"}
                </span>
              </span>
              <span className="strategyDescription">{strategy.description}</span>
            </label>
          );
        })}
      </div>
    </div>
  );
}
