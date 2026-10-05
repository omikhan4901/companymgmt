import { Check } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Developers",
  description: "The CompanyMgmt API: keys with chosen permissions, signed webhooks, idempotent writes, company sign-in, SCIM provisioning and SDKs.",
};

const features: [string, string][] = [
  ["API keys you can scope", "Give each integration only the permissions it needs. Per-key rate limits, network ranges, expiry, zero-downtime rotation and daily usage."],
  ["Signed webhooks", "employee.onboarded, leave.approved, sale.completed, stock.low and more, signed with HMAC-SHA256, retried for about a day and a half, with a delivery log and one-click resend."],
  ["Safe retries", "Send an Idempotency-Key with any write and a retry returns the first answer instead of doing the work twice."],
  ["Edits that don't collide", "Records carry a version; send If-Match and you'll never overwrite someone else's change by accident."],
  ["Company sign-in", "OpenID Connect with Google Workspace, Microsoft Entra ID, Okta and others. Require it for everyone if you like."],
  ["SCIM 2.0 provisioning", "Let your identity provider add people when they're hired and remove them when they leave."],
  ["A sandbox", "A separate workspace on the same plan, never billed, to build against without touching real data."],
  ["A contract we keep", "/v1 only grows. Breaking changes are announced at least 6 months ahead with Deprecation and Sunset headers, and every build checks the published contract."],
];

const curl = `curl https://companymgmt.app/v1/members \\
  -H "Authorization: Bearer $CM_KEY"

curl -X POST https://companymgmt.app/v1/branches \\
  -H "Authorization: Bearer $CM_KEY" \\
  -H "Idempotency-Key: 6f0c2d1e-branch-uttara" \\
  -H "Content-Type: application/json" \\
  -d '{"name": "Uttara"}'`;

const verify = `import hashlib, hmac, time

def verify(secret: str, body: bytes, header: str) -> bool:
    parts = dict(p.split("=", 1) for p in header.split(","))
    t = int(parts["t"])
    if abs(time.time() - t) > 300:
        return False
    mac = hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, parts["v1"])`;

const payload = `{
  "id": "0192f3c1-…",
  "type": "leave.approved",
  "created_at": "2026-10-05T09:12:44+00:00",
  "workspace_id": "0192…",
  "subject": { "type": "leave_request", "id": "0192…" },
  "data": { "membership_id": "…", "start_date": "2026-10-12", "days": "2.0" }
}`;

function Code({ children, label }: { children: string; label: string }) {
  return (
    <figure className="overflow-hidden rounded-2xl border border-slate-800 bg-[#0b1d26]">
      <figcaption className="border-b border-white/10 px-4 py-2 text-xs font-medium text-slate-400">{label}</figcaption>
      <pre className="overflow-x-auto p-4 text-[13px] leading-relaxed text-slate-100">
        <code>{children}</code>
      </pre>
    </figure>
  );
}

export default function DevelopersPage() {
  return (
    <>
      <section className="mx-auto max-w-[1100px] px-5 py-16 md:px-8">
        <p className="text-sm font-semibold uppercase tracking-wider text-brand-dark">Developers</p>
        <h1 className="mt-2 max-w-3xl font-site-display text-4xl font-extrabold tracking-tight text-ink md:text-5xl">Connect CompanyMgmt to everything else you run</h1>
        <p className="mt-4 max-w-2xl text-lg text-slate-600">
          The same API the app uses, opened up for your payroll exports, HR systems, dashboards and point-of-sale bridges. On the Business and Enterprise plans.
        </p>
        <ul className="mt-12 grid gap-4 md:grid-cols-2">
          {features.map(([title, text]) => (
            <li key={title} className="flex gap-3 rounded-2xl border border-slate-200 bg-white p-5">
              <Check className="mt-0.5 size-5 shrink-0 text-brand" aria-hidden="true" />
              <span>
                <span className="block font-semibold text-ink">{title}</span>
                <span className="mt-1 block text-slate-600">{text}</span>
              </span>
            </li>
          ))}
        </ul>
      </section>
      <section className="bg-slate-50">
        <div className="mx-auto grid max-w-[1100px] gap-6 px-5 py-16 md:px-8 lg:grid-cols-2">
          <div className="flex flex-col gap-3">
            <h2 className="font-site-display text-2xl font-bold text-ink">Two calls</h2>
            <p className="text-slate-600">Make a key in Settings → Developers. Errors come back as problem documents with a stable code and a request id.</p>
            <Code label="Shell">{curl}</Code>
          </div>
          <div className="flex flex-col gap-3">
            <h2 className="font-site-display text-2xl font-bold text-ink">Webhooks you can trust</h2>
            <p className="text-slate-600">Payloads are thin: ids and a few plain fields, never names, notes or salaries. Check the signature, then fetch details with your key.</p>
            <Code label="A delivery">{payload}</Code>
            <Code label="Python: check CompanyMgmt-Signature">{verify}</Code>
          </div>
        </div>
      </section>
      <section className="mx-auto max-w-[1100px] px-5 py-16 md:px-8">
        <h2 className="font-site-display text-2xl font-bold text-ink">SDKs</h2>
        <p className="mt-2 max-w-2xl text-slate-600">
          Small TypeScript and Python clients handle keys, retries with idempotency keys, pagination and webhook verification. Ask us for access while they&apos;re
          being published.
        </p>
        <p className="mt-6">
          <Link href="mailto:hello@companymgmt.app?subject=API%20access" className="rounded-[10px] bg-brand px-5 py-2.5 font-semibold text-white hover:bg-brand-dark">
            Talk to us about the API
          </Link>
        </p>
      </section>
    </>
  );
}
