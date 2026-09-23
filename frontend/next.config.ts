import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Only use standalone output when building with Docker (Vercel uses standard Next.js build)
  ...(process.env.BUILD_STANDALONE === "true" ? { output: "standalone" } : {}),
};

export default nextConfig;
