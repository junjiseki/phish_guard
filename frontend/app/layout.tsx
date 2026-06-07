import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ネット詐欺チェッカー | LINEで詐欺SMS・メールをかんたん確認",
  description:
    "LINEに届いたSMSやメールのスクリーンショットをAIが確認し、危険度と対応方法を短く分かりやすく返す相談サービスです。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
