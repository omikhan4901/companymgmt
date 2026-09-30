// Serves the static export the way Cloudflare does, for end-to-end tests and local
// previews: `/path` → path.html, headers from out/_headers, unknown paths → 404.html.
// Requests to /v1 go to the API (API_ORIGIN), so the refresh cookie stays first-party.
import { createReadStream, existsSync, readFileSync, statSync } from "node:fs";
import http from "node:http";
import { extname, join, normalize } from "node:path";

const root = new URL("../out/", import.meta.url).pathname;
const port = Number(process.env.PORT ?? 3000);
const apiOrigin = new URL(process.env.API_ORIGIN ?? "http://localhost:8000");

const types = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json",
  ".txt": "text/plain; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
  ".ico": "image/x-icon",
};

function parseHeaders() {
  const rules = [];
  if (!existsSync(join(root, "_headers"))) return rules;
  let current = null;
  for (const line of readFileSync(join(root, "_headers"), "utf8").split("\n")) {
    if (!line.trim()) continue;
    if (!line.startsWith(" ")) {
      current = { pattern: line.trim(), headers: [] };
      rules.push(current);
    } else if (current) {
      const i = line.indexOf(":");
      current.headers.push([line.slice(0, i).trim(), line.slice(i + 1).trim()]);
    }
  }
  return rules;
}
// Re-read after each build: the per-page script hashes change with the pages.
let rules = [];
let rulesMtime = 0;
function currentRules() {
  const file = join(root, "_headers");
  const mtime = existsSync(file) ? statSync(file).mtimeMs : 0;
  if (mtime !== rulesMtime) {
    rules = parseHeaders();
    rulesMtime = mtime;
  }
  return rules;
}

function matches(pattern, path) {
  if (pattern.endsWith("*")) return path.startsWith(pattern.slice(0, -1));
  return pattern === path;
}

function resolve(path) {
  const clean = normalize(decodeURIComponent(path)).replace(/^(\.\.[/\\])+/, "");
  const candidates = clean === "/" ? ["index.html"] : [clean, `${clean}.html`, join(clean, "index.html")];
  for (const candidate of candidates) {
    const file = join(root, candidate);
    if (file.startsWith(root) && existsSync(file) && statSync(file).isFile()) return file;
  }
  return null;
}

function proxy(req, res) {
  const upstream = http.request(
    { hostname: apiOrigin.hostname, port: apiOrigin.port, path: req.url, method: req.method, headers: { ...req.headers, host: apiOrigin.host } },
    (up) => {
      res.writeHead(up.statusCode ?? 502, up.headers);
      up.pipe(res);
    },
  );
  upstream.on("error", () => {
    res.writeHead(502).end("API unavailable");
  });
  req.pipe(upstream);
}

http
  .createServer((req, res) => {
    const url = new URL(req.url ?? "/", "http://localhost");
    if (url.pathname.startsWith("/v1/") || url.pathname === "/healthz") return proxy(req, res);
    let file = resolve(url.pathname);
    let status = 200;
    let route = url.pathname.replace(/\/$/, "") || "/";
    if (!file) {
      file = join(root, "404.html");
      status = 404;
      route = "/404";
    }
    const headers = { "content-type": types[extname(file)] ?? "application/octet-stream" };
    for (const rule of currentRules()) {
      if (matches(rule.pattern, route) || matches(rule.pattern, url.pathname)) {
        for (const [name, value] of rule.headers) headers[name] = value;
      }
    }
    res.writeHead(status, headers);
    createReadStream(file).pipe(res);
  })
  .listen(port, () => console.log(`Serving out/ on http://localhost:${port} (API ${apiOrigin.origin})`));
