import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "What CompanyMgmt collects, why, and your rights.",
};

export default function Page() {
  return (
    <article className="prose-legal mx-auto max-w-3xl px-4 py-16 md:px-6">
    <h1 className="text-4xl font-semibold tracking-tight">Privacy Policy</h1>
    <p className="mt-2 text-sm text-muted">Last updated 30 September 2026. Draft pending legal review.</p>

    <h2>Who we are</h2>
    <p>CompanyMgmt is run by Mehboob Ehsan Khan from Dhaka, Bangladesh. Contact: hello@companymgmt.app.</p>

    <h2>Two roles</h2>
    <p>For your account (name, email, password, sign-in history) we decide how data is used. For the data a business puts in its workspace (its people, attendance and records), the business decides and we process it on its behalf.</p>

    <h2>What we collect</h2>
    <ul>
      <li>Account data: name, email or username, a hashed password, language, and two-step verification settings.</li>
      <li>Workspace data entered by the business: people's names, contact details, job details, departments, branches, attendance times and notes. National ID numbers are stored encrypted.</li>
      <li>Location at clock-in and clock-out, if the workspace turns on the location check: the position rounded to about 11 m, its accuracy, and the distance from the branch. Nothing is recorded between those two moments.</li>
      <li>Security data: sign-in times, IP address and browser for each session, and an audit log of important changes.</li>
    </ul>

    <h2>Why</h2>
    <ul>
      <li>To run the service you asked for.</li>
      <li>To keep accounts secure (detecting stolen sign-ins, limiting repeated attempts).</li>
      <li>To send service emails: confirming your address, password resets, invitations and security alerts. We don&apos;t send marketing without your consent.</li>
    </ul>

    <h2>Where it's stored</h2>
    <p>Data is stored with our hosting providers (Google Cloud, Neon and Cloudflare) in Singapore and encrypted in transit and at rest. We don&apos;t sell data or use it for advertising.</p>

    <h2>How long</h2>
    <p>Workspace data is kept while the workspace exists. The owner can delete the workspace in Settings: nobody can use it from that moment, the owner can restore it for 30 days, and then every record is erased and the owner gets a signed deletion certificate by email. Encrypted backups that still hold it expire within 35 days after that. Audit log entries are kept for as long as the workspace&apos;s plan says (30 days to several years), then removed.</p>

    <h2>Your rights</h2>
    <p>You can see and correct your account data in the app, sign out other devices, and download a copy of what a workspace holds about you from your account page. Owners can export the whole workspace. You can also ask us for a copy of your data or for deletion. If your data is in a business&apos;s workspace, ask that business first; we help them respond. This policy is written with Bangladesh's Personal Data Protection Act 2026 and GDPR-style rights in mind.</p>

    <h2>Changes</h2>
    <p>We&apos;ll post changes here and tell workspace owners by email about important ones.</p>
  </article>
  );
}
