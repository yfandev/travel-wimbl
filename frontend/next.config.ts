import type { NextConfig } from "next";

// NEXT_PUBLIC_API_URL (frontend/.env.local) is the one backend setting. The browser calls same-origin /api/* and
// Next.js forwards it there, so the FastAPI app needs no CORS setup.
const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  // A live plan can take ~50 s when You.com Research is not cached; the default proxy limit hung up and the page
  // fell back to sample data.
  experimental: { proxyTimeout: 120_000 },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
