import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "PolicyDiff — Payer Policy Change Monitor",
  description:
    "AI-powered payer policy change intelligence. Detect tightening, loosening, and scope changes across UHC, Aetna, Cigna, and Humana before your hospital faces denials.",
  keywords: "payer policy, prior authorization, denial prevention, healthcare revenue cycle",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body>{children}</body>
    </html>
  );
}
