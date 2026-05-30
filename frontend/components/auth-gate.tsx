"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";

import { callApi } from "../lib/api";
import { clearSession, getToken, setSession, UNAUTHORIZED_EVENT } from "../lib/auth";
import { AppChrome } from "./app-chrome";

type AuthStatus = { configured: boolean; setup_required: boolean; user_ids: string[] };
type AuthResult = { ok: boolean; id?: string; token?: string; reason?: string };
type MeResult = { ok: boolean; authenticated: boolean; id?: string };

type Phase = "checking" | "setup" | "login" | "authed";

const REASON_TEXT: Record<string, string> = {
  INVALID_CREDENTIALS: "아이디 또는 비밀번호가 올바르지 않습니다.",
  ID_AND_PASSWORD_REQUIRED: "아이디와 비밀번호를 입력하세요.",
  USER_CREATE_FAILED: "사용자 생성에 실패했습니다.",
  ALREADY_CONFIGURED: "이미 계정이 있습니다. 로그인하세요."
};

export function AuthGate({ children }: { children: ReactNode }) {
  const [phase, setPhase] = useState<Phase>("checking");
  const [id, setId] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const resolve = useCallback(async () => {
    try {
      const status = await callApi<AuthStatus>("/api/auth/status");
      if (status.setup_required) {
        setPhase("setup");
        return;
      }
      const token = getToken();
      if (!token) {
        setPhase("login");
        return;
      }
      const me = await callApi<MeResult>("/api/auth/me");
      setPhase(me.authenticated ? "authed" : "login");
    } catch {
      // 인증 미설정(401 등)일 때도 안전하게 로그인 화면으로
      setPhase("login");
    }
  }, []);

  useEffect(() => {
    void resolve();
    const onUnauthorized = () => setPhase("login");
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, [resolve]);

  const submitSetup = async () => {
    setError("");
    if (!id.trim() || !password) {
      setError("아이디와 비밀번호를 입력하세요.");
      return;
    }
    if (password !== confirmPw) {
      setError("비밀번호가 일치하지 않습니다.");
      return;
    }
    setBusy(true);
    try {
      const result = await callApi<AuthResult>("/api/auth/setup", {
        method: "POST",
        body: JSON.stringify({ id: id.trim(), password })
      });
      if (result.ok && result.token && result.id) {
        setSession(result.token, result.id);
        setPassword("");
        setConfirmPw("");
        setPhase("authed");
      } else {
        setError(REASON_TEXT[result.reason ?? ""] ?? "계정 생성에 실패했습니다.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "계정 생성 실패");
    } finally {
      setBusy(false);
    }
  };

  const submitLogin = async () => {
    setError("");
    if (!id.trim() || !password) {
      setError("아이디와 비밀번호를 입력하세요.");
      return;
    }
    setBusy(true);
    try {
      const result = await callApi<AuthResult>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ id: id.trim(), password })
      });
      if (result.ok && result.token && result.id) {
        setSession(result.token, result.id);
        setPassword("");
        setPhase("authed");
      } else {
        setError(REASON_TEXT[result.reason ?? ""] ?? "로그인에 실패했습니다.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "로그인 실패");
    } finally {
      setBusy(false);
    }
  };

  if (phase === "authed") {
    return <AppChrome>{children}</AppChrome>;
  }

  if (phase === "checking") {
    return (
      <div className="authScreen">
        <div className="authCard">
          <div className="authBrand">Stock Analyst</div>
          <p className="muted">확인 중…</p>
        </div>
      </div>
    );
  }

  const isSetup = phase === "setup";
  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    void (isSetup ? submitSetup() : submitLogin());
  };

  return (
    <div className="authScreen">
      <form className="authCard" onSubmit={onSubmit}>
        <div className="authBrand">
          <span className="authLogoMark" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M8 5v14M12 5v14M16 5v14" />
              <circle cx="8" cy="10" r="1.7" />
              <circle cx="12" cy="15" r="1.7" />
              <circle cx="16" cy="8" r="1.7" />
            </svg>
          </span>
          Stock Analyst
        </div>
        <div className="authTitle">{isSetup ? "계정 만들기" : "로그인"}</div>
        <p className="authHint">
          {isSetup ? "이 프로그램에서 사용할 아이디와 비밀번호를 정하세요. (로컬에 안전하게 저장)" : "아이디와 비밀번호를 입력하세요."}
        </p>

        <label>
          아이디
          <input value={id} onChange={(e) => setId(e.target.value)} autoComplete="username" autoFocus placeholder="아이디" />
        </label>
        <label>
          비밀번호
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={isSetup ? "new-password" : "current-password"} placeholder="비밀번호" />
        </label>
        {isSetup ? (
          <label>
            비밀번호 확인
            <input type="password" value={confirmPw} onChange={(e) => setConfirmPw(e.target.value)} autoComplete="new-password" placeholder="비밀번호 다시 입력" />
          </label>
        ) : null}

        {error ? <div className="authError">{error}</div> : null}

        <button className="primary authSubmit" type="submit" disabled={busy}>
          {busy ? "처리 중…" : isSetup ? "계정 만들고 시작" : "로그인"}
        </button>
      </form>
    </div>
  );
}
