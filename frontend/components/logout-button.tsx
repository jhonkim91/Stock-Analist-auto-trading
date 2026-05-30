"use client";

import { clearSession, getUserId, notifyUnauthorized } from "../lib/auth";

/** 사이드바 푸터의 로그아웃 버튼. 세션을 비우고 로그인 화면으로 전환한다. */
export function LogoutButton() {
  const userId = getUserId();
  const logout = () => {
    clearSession();
    notifyUnauthorized();
  };
  return (
    <button type="button" className="logoutButton" onClick={logout} title="로그아웃">
      <svg aria-hidden="true" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M15 12H4M11 8l-4 4 4 4" />
        <path d="M14 4h5v16h-5" />
      </svg>
      <span>{userId ? `${userId} · 로그아웃` : "로그아웃"}</span>
    </button>
  );
}
