type PaperModeBannerProps = {
  title?: string;
};

/** Phase 8 화면에서 모의투자와 실거래 경계를 명확히 표시한다. */
export function PaperModeBanner({ title = "모의투자 전용" }: PaperModeBannerProps) {
  return (
    <section className="panel">
      <div className="sectionHeader">
        <div>
          <h2>{title}</h2>
          <p className="muted">실거래 아님 · 백엔드 안전 차단 필요 · 시크릿 마스킹</p>
        </div>
        <span className="badge fail">모의투자 전용</span>
      </div>
    </section>
  );
}
