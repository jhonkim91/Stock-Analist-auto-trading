"use client";

import { LiveOrderPanel } from "../../components/live-order-panel";

function PageIcon() {
  return (
    <svg className="pageTitleIcon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 17l6-6 4 4 7-8" />
      <path d="M14 7h6v6" />
    </svg>
  );
}

export default function LiveOrderPage() {
  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <PageIcon />
          <h1>라이브 주문 (실거래)</h1>
        </div>
        <div className="topbar-actions">
          <span className="status error">고위험</span>
        </div>
      </header>
      <section className="scroll">
        <LiveOrderPanel />
      </section>
    </main>
  );
}
