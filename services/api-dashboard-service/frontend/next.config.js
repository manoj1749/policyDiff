/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // API_BASE_URL is a server-side-only env var (no NEXT_PUBLIC_ prefix).
    // Set it to the Railway backend URL on Vercel — never baked into the client bundle.
    const backendUrl =
      process.env.API_BASE_URL ??
      process.env.NEXT_PUBLIC_API_BASE_URL ??
      "http://localhost:8003";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
