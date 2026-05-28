"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { GlobalStatusBar } from "./global-status-bar";

type NavItem = {
  href: string;
  label: string;
  icon: NavIconName;
  badge?: {
    label: string;
    tone: "ok" | "warn";
  };
};

type NavSection = {
  label: string;
  items: NavItem[];
};

type NavIconName =
  | "dashboard"
  | "filter"
  | "history"
  | "shield"
  | "file"
  | "database"
  | "clock"
  | "paper"
  | "bot"
  | "settings";

const navSections: NavSection[] = [
  {
    label: "OVERVIEW",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: "dashboard" },
      { href: "/screener", label: "Screener", icon: "filter", badge: { label: "7 pass", tone: "ok" } }
    ]
  },
  {
    label: "ANALYSIS",
    items: [
      { href: "/backtest", label: "Backtest", icon: "history" },
      { href: "/portfolio", label: "Portfolio", icon: "shield", badge: { label: "!", tone: "warn" } },
      { href: "/reports", label: "Reports", icon: "file" }
    ]
  },
  {
    label: "DATA",
    items: [
      { href: "/data", label: "Data Quality", icon: "database" },
      { href: "/paper", label: "Paper Trading", icon: "paper" },
      { href: "/bot", label: "Paper Bot", icon: "bot" },
      { href: "/settings", label: "Settings", icon: "settings" }
    ]
  }
];

function isActive(pathname: string, href: string) {
  if (href === "/dashboard") {
    return pathname === "/" || pathname === "/dashboard";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

function NavIcon({ name }: { name: NavIconName }) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    strokeWidth: 1.8
  };

  return (
    <svg aria-hidden="true" className="appNavIcon" viewBox="0 0 24 24">
      {name === "dashboard" ? (
        <>
          <rect {...common} height="6" width="6" x="4" y="4" />
          <rect {...common} height="6" width="6" x="14" y="4" />
          <rect {...common} height="6" width="6" x="4" y="14" />
          <rect {...common} height="6" width="6" x="14" y="14" />
        </>
      ) : null}
      {name === "filter" ? <path {...common} d="M4 5h16l-6.4 7.2v5.1L10.4 19v-6.8L4 5Z" /> : null}
      {name === "history" ? (
        <>
          <path {...common} d="M5 12a7 7 0 1 0 2.1-5" />
          <path {...common} d="M5 5v5h5" />
          <path {...common} d="M12 8v4l3 2" />
        </>
      ) : null}
      {name === "shield" ? <path {...common} d="M12 3 19 6v5c0 4.4-2.9 8-7 10-4.1-2-7-5.6-7-10V6l7-3Z" /> : null}
      {name === "file" ? (
        <>
          <path {...common} d="M7 3h7l4 4v14H7V3Z" />
          <path {...common} d="M14 3v5h5" />
          <path {...common} d="M9.5 13h5" />
          <path {...common} d="M9.5 17h4" />
        </>
      ) : null}
      {name === "database" ? (
        <>
          <ellipse {...common} cx="12" cy="5.5" rx="7" ry="2.5" />
          <path {...common} d="M5 5.5v6c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-6" />
          <path {...common} d="M5 11.5v6c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-6" />
        </>
      ) : null}
      {name === "clock" ? (
        <>
          <circle {...common} cx="12" cy="12" r="8" />
          <path {...common} d="M12 8v4l3 2" />
        </>
      ) : null}
      {name === "paper" ? (
        <>
          <path {...common} d="M6 7h12v12H6z" />
          <path {...common} d="M8 5h8" />
          <path {...common} d="M9 11h6" />
          <path {...common} d="M9 15h4" />
        </>
      ) : null}
      {name === "bot" ? (
        <>
          <rect {...common} height="10" rx="2" width="12" x="6" y="8" />
          <path {...common} d="M12 5v3" />
          <path {...common} d="M9.5 13h.1" />
          <path {...common} d="M14.5 13h.1" />
          <path {...common} d="M9.5 16h5" />
        </>
      ) : null}
      {name === "settings" ? (
        <>
          <circle {...common} cx="12" cy="12" r="3" />
          <path {...common} d="M19 12a7.2 7.2 0 0 0-.1-1l2-1.5-2-3.4-2.4 1a7 7 0 0 0-1.7-1L14.5 3h-5l-.3 3.1a7 7 0 0 0-1.7 1l-2.4-1-2 3.4 2 1.5a7.2 7.2 0 0 0 0 2l-2 1.5 2 3.4 2.4-1a7 7 0 0 0 1.7 1l.3 3.1h5l.3-3.1a7 7 0 0 0 1.7-1l2.4 1 2-3.4-2-1.5c.1-.3.1-.7.1-1Z" />
        </>
      ) : null}
    </svg>
  );
}

/** 모든 화면에 영상 목업과 같은 사이드바, 톤, preview-only 상태선을 제공한다. */
export function AppChrome({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="appChrome">
      <aside className="appSidebar" aria-label="Primary navigation">
        <Link className="appLogo" href="/dashboard">
          <span className="appLogoMark" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="M8 5v14" />
              <path d="M12 5v14" />
              <path d="M16 5v14" />
              <circle cx="8" cy="10" r="1.7" />
              <circle cx="12" cy="15" r="1.7" />
              <circle cx="16" cy="8" r="1.7" />
            </svg>
          </span>
          <span className="appLogoText">
            <span className="appLogoName">Stock Analyst</span>
            <span className="appLogoVersion">MVP v0.24.0</span>
          </span>
        </Link>

        <nav className="appNav">
          {navSections.map((section) => (
            <div className="appNavSection" key={section.label}>
              <div className="appNavSectionLabel">{section.label}</div>
              {section.items.map((item) => {
                const active = isActive(pathname, item.href);
                return (
                  <Link aria-current={active ? "page" : undefined} className={`appNavItem ${active ? "active" : ""}`} href={item.href} key={item.href}>
                    <NavIcon name={item.icon} />
                    <span>{item.label}</span>
                    {item.badge ? <span className={`appNavBadge ${item.badge.tone}`}>{item.badge.label}</span> : null}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="appSidebarFooter">
          <div>orders_count == 0 · fail-closed</div>
          <div className="appNoOrderBadge">
            <svg aria-hidden="true" viewBox="0 0 24 24">
              <rect height="10" rx="2" width="14" x="5" y="10" />
              <path d="M8 10V8a4 4 0 0 1 8 0v2" />
            </svg>
            preview-only · no real orders
          </div>
        </div>
      </aside>
      <div className="appContent">
        <GlobalStatusBar />
        {children}
      </div>
    </div>
  );
}
