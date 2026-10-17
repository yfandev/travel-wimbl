import type { NextConfig } from "next";

// NEXT_PUBLIC_API_URL (frontend/.env.local) is the one backend setting. The browser calls same-origin /api/* and
// Next.js forwards it there, so the FastAPI app needs no CORS setup.
const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
