import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained server for the production image (frontend/Dockerfile.prod).
  output: "standalone",
  poweredByHeader: false,
  // cacheComponents / partialPrefetching are left off: the app is
  // session-authenticated and client-guarded, and the instant-navigation
  // validation they enable flags every guarded route in dev.
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
