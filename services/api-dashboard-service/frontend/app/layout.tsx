import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PolicyDiff | Payer Policy Change Monitor",
  description:
    "AI-powered payer policy change intelligence. Detect tightening, loosening, and scope changes across major payers before denials hit revenue operations.",
  keywords: "payer policy, prior authorization, denial prevention, healthcare revenue cycle",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
