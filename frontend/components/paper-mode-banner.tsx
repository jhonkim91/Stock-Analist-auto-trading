type PaperModeBannerProps = {
  title?: string;
};

/** Phase 8 화면에서 모의투자와 실거래 경계를 명확히 표시한다. */
export function PaperModeBanner({ title = "모의투자 paper only" }: PaperModeBannerProps) {
  return (
    <section className="panel">
      <div className="sectionHeader">
        <div>
          <h2>{title}</h2>
          <p className="muted">실거래 아님 · backend safety gate required · secrets redacted</p>
        </div>
        <span className="badge fail">paper only</span>
      </div>
    </section>
  );
}
