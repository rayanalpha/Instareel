/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Required by frontend/Dockerfile (copies .next/standalone + server.js).
  output: "standalone",
  async rewrites() {
    // Proxy /api/* to FastAPI so the browser always talks same-origin
    // (no CORS, no ORB). rewrites() is evaluated AT BUILD TIME (serialized
    // into the routes manifest), so the destination must be resolvable from
    // the frontend container: API_INTERNAL_URL wins, then the public URL
    // (direct-exposure deploys), then localhost (local dev).
    const api =
      process.env.API_INTERNAL_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },
};

module.exports = nextConfig;
