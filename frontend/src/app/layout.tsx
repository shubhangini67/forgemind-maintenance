import "./globals.css";
import type { Metadata } from "next";
import { Inter } from "next/font/google";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Tata Steel — AI Maintenance Decision Intelligence",
  description:
    "Industrial AI maintenance command center · Predictive maintenance · C-MAPSS FD001 · 5 plant assets",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen bg-white font-sans text-tata-ink antialiased">{children}</body>
    </html>
  );
}
