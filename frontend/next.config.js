/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  async rewrites() {
    const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [{ source: "/backend/:path*", destination: `${api}/:path*` }];
  },
};

module.exports = nextConfig;
