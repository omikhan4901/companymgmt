// Cloudflare Pages Function: serves /v1/* on the web app's own origin by forwarding to the
// API on Cloud Run. The refresh cookie then stays first-party (it works on the free
// *.pages.dev address too), no CORS is needed, and the API only accepts traffic that
// carries the shared PROXY_TOKEN, with the real client IP from Cloudflare.
//
// Environment (Pages project → Settings → Variables and secrets):
//   API_ORIGIN   e.g. https://companymgmt-api-xxxx.a.run.app
//   PROXY_TOKEN  secret, the same value as the API's PROXY_TOKEN

const HOP_BY_HOP = ["host", "connection", "keep-alive", "transfer-encoding", "upgrade", "x-cm-proxy-token", "x-cm-client-ip", "x-forwarded-for"];

export async function onRequest({ request, env }) {
  if (!env.API_ORIGIN || !env.PROXY_TOKEN) {
    return new Response(JSON.stringify({ title: "Service is being set up", status: 503 }), {
      status: 503,
      headers: { "content-type": "application/problem+json" },
    });
  }
  const url = new URL(request.url);
  const target = new URL(url.pathname + url.search, env.API_ORIGIN);
  const headers = new Headers(request.headers);
  for (const name of HOP_BY_HOP) headers.delete(name);
  headers.set("x-cm-proxy-token", env.PROXY_TOKEN);
  headers.set("x-cm-client-ip", request.headers.get("cf-connecting-ip") ?? "");
  const hasBody = !["GET", "HEAD"].includes(request.method);
  const response = await fetch(target, {
    method: request.method,
    headers,
    body: hasBody ? request.body : undefined,
    redirect: "manual",
  });
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers: response.headers });
}
