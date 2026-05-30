import "./globals.css";

import { AuthGate } from "../components/auth-gate";

export const metadata = {
  title: "Stock Analyst",
  description: "Phase 2 MVP web flow"
};

// 페인트 이전에 테마를 적용해 깜빡임(FOUC)을 막는다.
const themeBootstrap = `(function(){try{var t=localStorage.getItem('sa-theme');if(t!=='light'&&t!=='dark'){t=window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}document.documentElement.dataset.theme=t;}catch(e){document.documentElement.dataset.theme='light';}})();`;

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" data-theme="light">
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootstrap }} />
      </head>
      <body>
        <AuthGate>{children}</AuthGate>
      </body>
    </html>
  );
}
