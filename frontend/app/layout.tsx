import "./globals.css";

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
      <body>{children}</body>
    </html>
  );
}
