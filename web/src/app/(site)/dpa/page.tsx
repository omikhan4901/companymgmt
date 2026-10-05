import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Data Processing Addendum",
  description: "How CompanyMgmt processes personal data on behalf of the businesses that use it.",
};

export default function Page() {
  return (
    <article className="prose-legal mx-auto max-w-3xl px-4 py-16 md:px-6">
      <h1 className="font-site-display text-4xl font-extrabold tracking-tight text-ink">Data Processing Addendum</h1>
      <p className="mt-2 text-sm text-muted">Last updated 5 October 2026. Draft pending legal review. Part of the <Link href="/terms">Terms of Service</Link>.</p>

      <h2>1. Roles and scope</h2>
      <p>
        The business that owns a workspace (“customer”) is the controller of the personal data in it; CompanyMgmt (“we”) is its processor. This addendum covers
        that data for as long as we hold it. It follows the GDPR (Article 28) and Bangladesh’s Personal Data Protection Ordinance 2025; where a law gives more
        protection, it prevails.
      </p>

      <h2>2. What we process</h2>
      <ul>
        <li><strong>People:</strong> the customer’s staff and contractors, its customers and suppliers, and anyone named in its records.</li>
        <li><strong>Data:</strong> identity and contact details, job, attendance (and clock-in/out location if switched on), leave, pay and deductions, national ids (encrypted), documents and tasks, sales, dues, expenses and receipts, and whatever else the customer enters.</li>
        <li><strong>Purpose and duration:</strong> to provide the service the customer chose, for the subscription plus the export and deletion periods below.</li>
      </ul>

      <h2>3. Our commitments</h2>
      <ul>
        <li>Process the data only on the customer’s documented instructions (the terms, its settings and its use of the service), and tell it if an instruction seems unlawful.</li>
        <li>Make sure people with access are bound by confidentiality; access to production data is limited to what support and security require.</li>
        <li>Keep the security measures in section 7 in place and up to date.</li>
        <li>Help the customer answer people’s requests (the app’s exports, corrections and deletion cover most) and with impact assessments and regulator questions.</li>
        <li>Never sell the data, use it for advertising, or use it to train AI models.</li>
      </ul>

      <h2>4. Sub-processors</h2>
      <p>
        The customer authorises the providers on the <Link href="/subprocessors">sub-processors page</Link>. We bind each to equivalent terms, remain responsible for
        them, and give 30 days’ notice of changes; the customer may object on reasonable grounds and end the service before the change.
      </p>

      <h2>5. Transfers</h2>
      <p>
        Data is hosted in Singapore and may be processed by the listed providers elsewhere. Transfers rely on the contract between the customer and us for the
        service, the providers’ contractual safeguards and, for data from the EU/UK, the European Commission’s Standard Contractual Clauses (module two/three), which
        we’ll sign on request.
      </p>

      <h2>6. Personal data breaches</h2>
      <p>
        We tell the customer without undue delay, aiming for within 48 hours of confirming a breach that affects its data, with what we know: what happened, the
        data and people affected, likely consequences and what we’re doing. We follow up as we learn more, so the customer can meet its own deadlines (for example
        72 hours to a regulator).
      </p>

      <h2>7. Security measures</h2>
      <ul>
        <li>Database-enforced isolation between workspaces (row-level security), tested automatically on every route.</li>
        <li>Encryption in transit (TLS) and at rest; field-level AES-256-GCM encryption for national ids and secrets; encrypted backups.</li>
        <li>Strong sign-in: argon2id passwords, passkeys, two-step codes, company sign-in, short-lived tokens, rate limits, new-device alerts, admin two-step policy.</li>
        <li>Least-privilege roles and department scopes; every route declares who may call it.</li>
        <li>Tamper-evident audit log; backups with point-in-time restore; tested restore and incident procedures.</li>
        <li>Dependency audits and weekly updates; a vulnerability disclosure policy.</li>
      </ul>

      <h2>8. Audits</h2>
      <p>
        We make available the information needed to show compliance (this addendum, our security documentation and answers to reasonable questionnaires). Where
        that isn’t enough, the customer may audit once a year with 30 days’ notice, at its cost, under confidentiality, without access to other customers’ data.
      </p>

      <h2>9. End of service</h2>
      <p>
        The customer can export everything at any time. When a workspace is deleted, it can be restored for 30 days; then we erase the data and send a signed
        certificate, and backups holding it expire within a further 35 days, unless a law requires us to keep something.
      </p>
    </article>
  );
}
