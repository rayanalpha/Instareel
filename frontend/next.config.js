/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Required by frontend/Dockerfile (copies .next/standalone + server.js).
  output: "standalone",
  async rewrites() {
    // Proxy /api/* to FastAPI so the browser always talks same-origin
    // (no CORS, no ORB). NEXT_PUBLIC_API_URL is baked at build time.
    const api = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },
};

module.exports = nextConfig;
