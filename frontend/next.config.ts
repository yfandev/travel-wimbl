import type { NextConfig } from "next";

// The browser calls same-origin /api/*; Next.js forwards it to FastAPI, so the backend needs no CORS setup.
const WIMBL_API = process.env.WIMBL_API ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${WIMBL_API}/api/:path*` }];
  },
};

export default nextConfig;
