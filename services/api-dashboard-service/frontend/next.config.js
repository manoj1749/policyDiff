/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow fetching from localhost:8003 during SSR
  experimental: {
    serverComponentsExternalPackages: [],
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8003"}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
