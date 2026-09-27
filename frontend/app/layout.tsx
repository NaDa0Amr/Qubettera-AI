import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { publicEnv } from "@/lib/env";
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
    default: publicEnv.appName,
    template: `%s | ${publicEnv.appName}`,
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
    title: publicEnv.appName,
    description:
      "Simulate AI debates on transformer architecture choices. Powered by LangGraph, FastAPI, and PostgreSQL + pgvector.",
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
        <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-indigo-600 focus:px-4 focus:py-2 focus:text-white">Skip to content</a>
        <TopNav />
        <main id="main-content" tabIndex={-1} className="flex flex-1 flex-col">{children}</main>
        <Footer />
        <ToastContainer />
      </body>
    </html>
  );
}
