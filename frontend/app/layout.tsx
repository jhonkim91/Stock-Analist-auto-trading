import "./globals.css";

import { AppChrome } from "../components/app-chrome";

export const metadata = {
  title: "Stock Analyst MVP",
  description: "Phase 2 MVP web flow"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body>
        <AppChrome>{children}</AppChrome>
      </body>
    </html>
  );
}
