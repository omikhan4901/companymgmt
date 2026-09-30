// Writes out/_headers for Cloudflare after `next build`.
//
// Next.js puts two small inline scripts in every page (the router bootstrap and the page
// data). Instead of allowing all inline scripts, each page gets a Content-Security-Policy
// that allows exactly its own scripts by SHA-256 hash. Cloudflare joins headers from
// every matching rule, so the policy is set per page, never on a wildcard rule.
import { createHash } from "node:crypto";
import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";

const out = new URL("../out/", import.meta.url).pathname;
const api = process.env.NEXT_PUBLIC_API_URL ?? "";
const turnstile = "https://challenges.cloudflare.com";

function htmlFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === "_next" ? [] : htmlFiles(path);
    return name.endsWith(".html") ? [path] : [];
  });
}

function routeFor(file) {
  const rel = relative(out, file).replace(/\\/g, "/").replace(/\.html$/, "");
  if (rel === "index") return "/";
  if (rel.endsWith("/index")) return `/${rel.slice(0, -"/index".length)}`;
  return `/${rel}`;
}

export function policy(hashes) {
  return [
    "default-src 'self'",
    `script-src 'self' ${hashes.map((h) => `'sha256-${h}'`).join(" ")} ${turnstile}`.replace(/\s+/g, " "),
    // Radix positions popovers with inline style attributes.
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    `connect-src 'self' ${api}`.trim(),
    `frame-src ${turnstile}`,
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
  ].join("; ");
}

const common = [
  "  X-Content-Type-Options: nosniff",
  "  X-Frame-Options: DENY",
  "  Referrer-Policy: strict-origin-when-cross-origin",
  // Location is used for clock-in on this site only.
  "  Permissions-Policy: camera=(), microphone=(), geolocation=(self)",
  "  Strict-Transport-Security: max-age=63072000; includeSubDomains",
];

const lines = ["/*", ...common, "/_next/static/*", "  Cache-Control: public, max-age=31536000, immutable", ""];
let pages = 0;
for (const file of htmlFiles(out).sort()) {
  const html = readFileSync(file, "utf8");
  const hashes = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)]
    .map((m) => m[1])
    .filter((body) => body.length > 0)
    .map((body) => createHash("sha256").update(body, "utf8").digest("base64"));
  const route = routeFor(file);
  const csp = policy([...new Set(hashes)]);
  if (csp.length > 1900) throw new Error(`Policy for ${route} is too long for Cloudflare (${csp.length} chars).`);
  lines.push(route, `  Content-Security-Policy: ${csp}`, "");
  pages += 1;
}
writeFileSync(join(out, "_headers"), lines.join("\n"));
console.log(`_headers: security headers for ${pages} pages`);
