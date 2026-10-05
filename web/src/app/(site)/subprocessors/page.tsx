import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Sub-processors",
  description: "The providers that process data for CompanyMgmt, and what each one does.",
};

const ROWS = [
  ["Google Cloud (Cloud Run, Secret Manager, Cloud Scheduler)", "Runs the application and its scheduled jobs; keeps server secrets", "Singapore", "All workspace data, while processing"],
  ["Neon", "The Postgres database", "Singapore", "All workspace data"],
  ["Cloudflare (Pages, R2, Turnstile)", "Serves the website and app, stores encrypted backups, bot checks on sign-in", "Global edge; backups in the region chosen at setup", "Requests in transit; encrypted backups; IP address for bot checks"],
  ["Resend (or the SMTP provider in use)", "Sends service emails", "United States", "Email addresses, names, email contents"],
  ["Google (Gemini API, paid tier)", "Answers AI questions, only for workspaces that switch the assistant on", "Global", "The question and the records needed to answer it"],
];

export default function Page() {
  return (
    <article className="prose-legal mx-auto max-w-4xl px-4 py-16 md:px-6">
      <h1 className="font-site-display text-4xl font-extrabold tracking-tight text-ink">Sub-processors</h1>
      <p className="mt-2 text-sm text-muted">Last updated 5 October 2026. Draft pending legal review.</p>
      <p>
        These providers process data for us to run CompanyMgmt, each under a written contract with data-protection terms at least as protective as our{" "}
        <Link href="/dpa">Data Processing Addendum</Link>. We tell workspace owners by email at least 30 days before adding or replacing one; an owner who objects on
        reasonable data-protection grounds can end their subscription before the change and export their data.
      </p>
      <div className="not-prose overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200">
              <th className="py-2 pr-4">Provider</th>
              <th className="py-2 pr-4">Purpose</th>
              <th className="py-2 pr-4">Location</th>
              <th className="py-2">Data</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map(([who, what, where, data]) => (
              <tr key={who} className="border-b border-slate-100 align-top">
                <td className="py-2 pr-4 font-medium">{who}</td>
                <td className="py-2 pr-4">{what}</td>
                <td className="py-2 pr-4">{where}</td>
                <td className="py-2">{data}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p>Webhooks, API integrations and company sign-in send data only to the systems each workspace chooses; those aren’t our sub-processors.</p>
    </article>
  );
}
