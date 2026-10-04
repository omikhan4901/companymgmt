/** Workspace addresses: `<slug>.companymgmt.app` (the domain is set at build time). */
export const WORKSPACE_DOMAIN = process.env.NEXT_PUBLIC_WORKSPACE_DOMAIN || "companymgmt.app";

/** The workspace slug when the app is opened on a workspace's own address, else null. */
export function slugFromHost(host: string, domain: string = WORKSPACE_DOMAIN): string | null {
  const h = host.toLowerCase().replace(/:\d+$/, "");
  if (!h.endsWith(`.${domain}`)) return null;
  const sub = h.slice(0, -(domain.length + 1));
  if (!sub || sub.includes(".") || ["www", "app", "api"].includes(sub)) return null;
  return /^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$/.test(sub) ? sub : null;
}

export function addressFor(slug: string, domain: string = WORKSPACE_DOMAIN): string {
  return `https://${slug}.${domain}`;
}
