import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ['192.168.1.20'],
  serverExternalPackages: ['puppeteer-core', '@sparticuz/chromium'],
};

export default nextConfig;
