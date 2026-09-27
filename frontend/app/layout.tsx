import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { TopNav } from "@/components/layout/TopNav";
import { Footer } from "@/components/layout/Footer";
import { ToastContainer } from "@/components/ui/Toast";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  display: "swap",
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: {
    default: "Multi-Agent Opinion Simulator",
    template: "%s | Multi-Agent Opinion Simulator",
  },
  description:
    "Simulate multi-agent debates on AI architecture topics. Watch AI personas with distinct expertise argue, retrieve evidence, and converge on positions — then analyze opinion dynamics.",
  keywords: [
    "multi-agent AI",
    "opinion dynamics",
    "transformer architecture",
    "MoE",
    "AI debate simulation",
  ],
  openGraph: {
    title: "Multi-Agent Opinion Simulator",
    description:
      "Simulate AI debates on transformer architecture choices. Powered by LangGraph, FastAPI, and Supabase pgvector.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-slate-50 dark:bg-slate-950 font-sans">
        <TopNav />
        <main className="flex flex-1 flex-col">{children}</main>
        <Footer />
        <ToastContainer />
      </body>
    </html>
  );
}
