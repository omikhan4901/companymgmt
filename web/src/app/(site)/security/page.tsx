import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Security",
  description: "How CompanyMgmt keeps businesses' data safe, and how to report a vulnerability.",
};

const POINTS: [string, string][] = [
  ["Workspaces can't see each other", "Every workspace table is protected by the database itself (row-level security), not just the app. An automatic test tries every page of the API with another workspace's records."],
  ["Strong sign-in", "Passkeys, two-step codes, company sign-in (Google, Microsoft, Okta), passwords checked against known breaches, limits on repeated attempts, and an email when your account is opened on a new device."],
  ["Least privilege", "Built-in and custom roles, manager scopes by department, and a review of every route's access in our tests. Shared tills open with a cashier PIN that only works on a registered device and can only sell."],
  ["Encryption", "TLS everywhere; national ids, two-step secrets and integration secrets are encrypted with AES-256-GCM; backups are encrypted."],
  ["A log you can trust", "Important changes go into an audit log chained with hashes, so edits or deletions show up. Export it any time."],
  ["Careful AI", "The assistant uses only tools that check the asker's own permissions, and nothing it proposes happens until a person confirms. Your data isn't used to train models."],
  ["Safe integrations", "API keys with chosen permissions, rate limits and network ranges; signed webhooks that only go to public HTTPS addresses."],
  ["Your data stays yours", "Export the whole workspace or your own data, delete with a 30-day undo, and get a signed certificate when it's erased."],
];

export default function Page() {
  return (
    <article className="prose-legal mx-auto max-w-3xl px-4 py-16 md:px-6">
      <h1 className="font-site-display text-4xl font-extrabold tracking-tight text-ink">Security</h1>
      <p className="mt-2 text-sm text-muted">How we protect the businesses that trust us with their people, pay and sales.</p>
      {POINTS.map(([title, body]) => (
        <section key={title}>
          <h2>{title}</h2>
          <p>{body}</p>
        </section>
      ))}
      <h2>Report a vulnerability</h2>
      <p>
        Email <strong>security@companymgmt.app</strong> with what you found and how to reproduce it. Please don’t access other people’s data or disrupt the service.
        We reply within 3 working days, won’t take action against good-faith research, and will credit you if you’d like. See also{" "}
        <a href="/.well-known/security.txt">security.txt</a>, the <Link href="/privacy">Privacy Policy</Link> and the <Link href="/dpa">Data Processing Addendum</Link>.
      </p>
    </article>
  );
}
