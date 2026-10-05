import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "What CompanyMgmt collects, why, where it's kept, for how long, and your rights.",
};

export default function Page() {
  return (
    <article className="prose-legal mx-auto max-w-3xl px-4 py-16 md:px-6">
      <h1 className="font-site-display text-4xl font-extrabold tracking-tight text-ink">Privacy Policy</h1>
      <p className="mt-2 text-sm text-muted">Last updated 5 October 2026. Draft pending legal review.</p>

      <h2>Who we are</h2>
      <p>CompanyMgmt is run by Mehboob Ehsan Khan from Dhaka, Bangladesh. Contact: hello@companymgmt.app (privacy questions and requests).</p>

      <h2>Two roles</h2>
      <p>
        For your own account (name, email, password, sign-in history) and our website, we decide how data is used: we’re the controller. For everything a business
        puts in its workspace (its staff, payroll, customers, sales and records), the business decides and we process it on its behalf under the{" "}
        <Link href="/dpa">Data Processing Addendum</Link>. If you’re a staff member or a customer of a business that uses CompanyMgmt, that business is responsible for
        your data; ask it first, and we’ll help it answer.
      </p>

      <h2>What we hold</h2>
      <ul>
        <li><strong>Account data:</strong> name, email or username, a hashed password, passkeys’ public keys, language, two-step settings (the secret is encrypted).</li>
        <li><strong>Staff and HR data the business enters:</strong> names, contact details, job and department, pay and deductions, leave, documents read, tasks. National ID numbers are encrypted.</li>
        <li><strong>Attendance:</strong> clock-in and clock-out times; if the business turns on the location check, the position at those two moments only (rounded to about 11 m), its accuracy and the distance from the branch. Nothing is tracked in between.</li>
        <li><strong>Shop data:</strong> sales and receipts, the business’s customers and what they owe (names and phone numbers if the business records them), suppliers, expenses and receipt photos, stock and the books.</li>
        <li><strong>AI:</strong> questions people ask the assistant and its answers (kept for the person who asked until they delete them; not in workspace exports).</li>
        <li><strong>Security data:</strong> sign-in times, IP address and browser per session, failed sign-ins, an audit log of important changes, API key usage, webhook delivery logs.</li>
      </ul>

      <h2>Why, and on what basis</h2>
      <ul>
        <li>To provide the service you or your employer signed up for (contract).</li>
        <li>To keep accounts secure: limiting repeated attempts, detecting stolen sign-ins, emailing you about new-device sign-ins (legitimate interest and legal duty).</li>
        <li>To send service emails: confirming your address, resets, invitations, security alerts, digests you can turn off. No marketing without consent.</li>
        <li>For workspace data: only on the business’s instructions.</li>
      </ul>
      <p>We don’t sell data, show ads, or use any of it to train AI models.</p>

      <h2>Who else processes it</h2>
      <p>
        A short list of providers runs parts of the service for us, each under a contract that protects the data: see <Link href="/subprocessors">sub-processors</Link>.
        AI questions go to Google (Gemini) only if the workspace switched the assistant on, with only the records needed for that answer, under Google’s paid-service
        terms, which don’t allow Google to use them to improve its products. Webhooks and integrations send data only where the workspace points them.
      </p>

      <h2>Where it’s stored</h2>
      <p>
        In Singapore (Google Cloud, Neon) and on Cloudflare’s network, encrypted in transit and at rest. If you’re outside Singapore, your data is transferred
        there to provide the service, with safeguards in our contracts with providers and in the Data Processing Addendum.
      </p>

      <h2>How long</h2>
      <ul>
        <li>Workspace data: while the workspace exists. When the owner deletes it, nobody can use it; the owner can restore it for 30 days; then it’s erased (with a signed certificate), and backups holding it expire within 35 more days.</li>
        <li>Audit log entries: for the period the workspace’s plan sets (30 days to several years), then removed.</li>
        <li>Sign-in records and ended sessions: 1 year. One-time links, codes and challenges: days.</li>
        <li>AI conversations: until the person deletes them or leaves the workspace.</li>
        <li>Your account: while you use it. Ask us to delete it at any time; staff accounts end when the business removes them.</li>
      </ul>

      <h2>How it’s protected</h2>
      <p>
        Tenant isolation enforced in the database, encryption of sensitive fields, passkeys and two-step sign-in, short-lived tokens, rate limits, a tamper-evident
        audit log, and more, described on the <Link href="/security">security page</Link>.
      </p>

      <h2>Your rights</h2>
      <p>
        You can see and correct your account data in the app, sign out other devices, and download a copy of what a workspace holds about you from your account
        page. Owners can export the whole workspace. You can also ask us to access, correct, delete or move your data, object to processing, or withdraw consent
        where we rely on it. We answer within 30 days. You can complain to your data protection authority. This policy is written with Bangladesh’s Personal Data
        Protection Ordinance 2025 and the GDPR in mind.
      </p>

      <h2>Children</h2>
      <p>The service is for businesses. Owners and admins must be adults; a business that employs young people is responsible for doing so lawfully.</p>

      <h2>Cookies</h2>
      <p>We use one essential cookie to keep you signed in (it can’t be used to track you elsewhere) and remember your theme and language in your browser. No advertising or tracking cookies.</p>

      <h2>Changes</h2>
      <p>We’ll post changes here and email workspace owners about important ones at least 30 days before they take effect.</p>
    </article>
  );
}
