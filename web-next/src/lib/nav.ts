/** Only same-site app paths, never "//host" or "https://…" (open-redirect guard). */
export function safeNext(next: string | null, fallback = "/app"): string {
  return next && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\") ? next : fallback;
}
