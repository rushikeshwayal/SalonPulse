import type { NextConfig } from "next";

const backendOrigin = (process.env.SALONPULSE_API_ORIGIN || "https://salon-pulse-one.vercel.app").replace(/\/$/, "");

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: backendOrigin + "/api/:path*",
      },
    ];
  },
};

export default nextConfig;
