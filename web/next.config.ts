import type { NextConfig } from "next";

/**
 * One Next.js app for the marketing site and the product.
 *
 * Production builds are a static export (`out/`) served from Cloudflare: every page is
 * pre-rendered HTML, product screens render in the browser and talk to the API. In
 * development, `/v1` is proxied to the API on :8000 so the refresh cookie is first-party.
 */
const isDev = process.env.NODE_ENV === "development";

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  images: { unoptimized: true },
  ...(isDev
    ? { rewrites: async () => [{ source: "/v1/:path*", destination: `${process.env.DEV_API_ORIGIN ?? "http://localhost:8000"}/v1/:path*` }] }
    : { output: "export" as const }),
};

export default config;
