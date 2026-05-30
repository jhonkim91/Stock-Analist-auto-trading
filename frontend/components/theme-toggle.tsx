"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark";

const STORAGE_KEY = "sa-theme";

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
}

/** 라이트/다크를 전환하는 슬라이더 스위치. 선택은 localStorage에 저장된다. */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    // layout의 사전 스크립트가 이미 data-theme를 적용했으므로 현재 값을 읽어 동기화한다.
    // 하이드레이션 불일치를 피하려고 마운트 후 동기화하는 의도된 effect다.
    const current = (document.documentElement.dataset.theme as Theme | undefined) ?? "light";
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTheme(current);
  }, []);

  const toggle = () => {
    setTheme((prev) => {
      const next: Theme = prev === "dark" ? "light" : "dark";
      applyTheme(next);
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        /* 저장 불가 환경은 무시한다 */
      }
      return next;
    });
  };

  const isDark = theme === "dark";

  return (
    <button
      type="button"
      className={`themeToggle ${isDark ? "dark" : ""}`}
      onClick={toggle}
      role="switch"
      aria-checked={isDark}
      aria-label="라이트/다크 테마 전환"
      title="라이트/다크 테마 전환"
    >
      <span className="themeToggleLabel">{isDark ? "Dark" : "Light"}</span>
      <span className="themeToggleTrack" aria-hidden="true">
        <svg className="themeToggleIcon" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4" />
        </svg>
        <svg className="themeToggleIcon" viewBox="0 0 24 24">
          <path d="M20 14.5A7.5 7.5 0 1 1 9.5 4a6 6 0 0 0 10.5 10.5Z" />
        </svg>
        <span className="themeToggleThumb" />
      </span>
    </button>
  );
}
