import type { NextConfig } from "next";
const backendOrigin = "https://salon-pulse-one.vercel.app";
const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: backendOrigin + "/api/:path*" }];
  },
};
export default nextConfig;
