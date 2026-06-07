import type { Metadata } from "next";
import "./globals.css";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";
const siteName = "詐欺チェッカー";
const title = "詐欺チェッカー | LINEで詐欺SMS・メールをAI確認";
const description =
  "怪しいSMSやメールのスクリーンショットをLINEで送るだけ。AIが詐欺メールやフィッシングの危険度、理由、対応方法を短く分かりやすく返信します。";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title,
  description,
  applicationName: siteName,
  keywords: [
    "ネット詐欺",
    "詐欺メール",
    "フィッシング",
    "迷惑メール",
    "SMS詐欺",
    "スミッシング",
    "LINE相談",
    "AI判定",
    "高齢者見守り",
  ],
  authors: [{ name: siteName }],
  creator: siteName,
  publisher: siteName,
  alternates: {
    canonical: "/",
  },
  openGraph: {
    type: "website",
    locale: "ja_JP",
    url: "/",
    siteName,
    title,
    description,
    images: [
      {
        url: "/hero-phish-guard.png",
        width: 1536,
        height: 864,
        alt: "スマートフォンで詐欺SMSやメールをAIに相談する様子",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: ["/hero-phish-guard.png"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
      "max-video-preview": -1,
    },
  },
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
