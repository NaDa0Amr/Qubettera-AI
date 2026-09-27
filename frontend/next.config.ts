import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  // Next.js blocks cross-origin dev resources (HMR) by default. Without this,
  // loading via 127.0.0.1 silently prevents hydration and the UI never populates.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
};

export default nextConfig;
