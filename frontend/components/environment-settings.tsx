"use client";

import { useCallback, useEffect, useState } from "react";

import { callApi } from "../lib/api";

type EnvField = {
  key: string;
  label: string;
  placeholder?: string;
  configured: boolean;
  persisted: boolean;
  sensitive: boolean;
  masked_value: string;
};

type EnvGroup = { category: string; label: string; fields: EnvField[] };
type EnvStatus = { persistence: string; secrets_redacted: boolean; groups: EnvGroup[] };

/** 프로그램 내에서 KIS/텔레그램/디스코드 자격증명·환경 값을 입력·저장한다(로컬 영속). */
export function EnvironmentSettings() {
  const [status, setStatus] = useState<EnvStatus | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      const data = await callApi<EnvStatus>("/api/settings/environment");
      setStatus(data);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "환경 값 조회 실패");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const saveField = async (key: string) => {
    const value = drafts[key] ?? "";
    setSavingKey(key);
    setMessage(`${key} 저장 중…`);
    try {
      const result = await callApi<{ ok: boolean; status: string; masked_value?: string }>("/api/settings/environment", {
        method: "POST",
        body: JSON.stringify({ key, value, confirm: true })
      });
      setMessage(result.ok ? `${key} ${result.status === "cleared" ? "삭제됨" : "저장됨"}` : `${key} 저장 실패`);
      setDrafts((prev) => ({ ...prev, [key]: "" }));
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "저장 실패");
    } finally {
      setSavingKey(null);
    }
  };

  if (!status) {
    return (
      <article className="envPanel">
        <div className="card-hd">
          <span className="card-title">자격증명 / 환경 값</span>
        </div>
        <p className="muted">{message || "조회 중…"}</p>
      </article>
    );
  }

  return (
    <article className="envPanel">
      <div className="card-hd">
        <span className="card-title">자격증명 / 환경 값</span>
        <span className="status ok" title={message}>
          로컬 저장
        </span>
      </div>
      <div className="warn-box info">
        <span aria-hidden="true">i</span>
        값은 마스킹되어 표시됩니다. 비우고 저장하면 삭제됩니다. KIS 라이브 모드는 자격증명 입력 후 라이브 토글이 함께 필요합니다.
      </div>
      <div className="envGrid">
        {status.groups.map((group) => (
          <section className="envGroup" key={group.category}>
            <div className="envGroupTitle">{group.label}</div>
            {group.fields.map((field) => (
              <div className="credentialRow" key={field.key}>
                <div className="credentialMeta">
                  <span className="credentialLabel">{field.label}</span>
                  <span className="credentialKey">
                    {field.key}
                    {field.configured ? <span className="credentialSet"> · 설정됨{field.masked_value ? ` (${field.masked_value})` : ""}</span> : <span className="credentialUnset"> · 미설정</span>}
                  </span>
                </div>
                <div className="credentialControls">
                  <input
                    type={field.sensitive ? "password" : "text"}
                    value={drafts[field.key] ?? ""}
                    placeholder={field.configured ? "변경하려면 입력" : field.placeholder ?? ""}
                    onChange={(event) => setDrafts((prev) => ({ ...prev, [field.key]: event.target.value }))}
                    autoComplete="off"
                  />
                  <button type="button" disabled={savingKey === field.key} onClick={() => void saveField(field.key)}>
                    {savingKey === field.key ? "…" : "저장"}
                  </button>
                </div>
              </div>
            ))}
          </section>
        ))}
      </div>
      <div className="envMessage">{message}</div>
    </article>
  );
}
