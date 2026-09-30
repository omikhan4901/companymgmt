import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { type Plugin } from "vite";
import { defineConfig } from "vitest/config";

/** Cloudflare Pages security headers, with the API origin filled in at build time. */
function securityHeaders(): Plugin {
  const api = process.env.VITE_API_URL ?? "";
  const turnstile = "https://challenges.cloudflare.com";
  const csp = [
    "default-src 'self'",
    `script-src 'self' ${turnstile}`,
    // antd injects its component styles at runtime.
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    `connect-src 'self' ${api}`.trim(),
    `frame-src ${turnstile}`,
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
  ].join("; ");
  const body = [
    "/*",
    `  Content-Security-Policy: ${csp}`,
    "  X-Content-Type-Options: nosniff",
    "  X-Frame-Options: DENY",
    "  Referrer-Policy: strict-origin-when-cross-origin",
    "  Permissions-Policy: camera=(), microphone=(), geolocation=()",
    "  Strict-Transport-Security: max-age=63072000; includeSubDomains",
    "/assets/*",
    "  Cache-Control: public, max-age=31536000, immutable",
    "",
  ].join("\n");
  return {
    name: "security-headers",
    apply: "build",
    generateBundle() {
      this.emitFile({ type: "asset", fileName: "_headers", source: body });
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), securityHeaders()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    port: 5173,
    // In development the API runs on :8000 and is reached through this proxy, so the
    // refresh cookie is first-party.
    proxy: {
      "/v1": "http://localhost:8000",
    },
  },
  build: {
    sourcemap: true,
    chunkSizeWarningLimit: 1500,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});
