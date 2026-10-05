import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "The terms for using CompanyMgmt.",
};

export default function Page() {
  return (
    <article className="prose-legal mx-auto max-w-3xl px-4 py-16 md:px-6">
      <h1 className="font-site-display text-4xl font-extrabold tracking-tight text-ink">Terms of Service</h1>
      <p className="mt-2 text-sm text-muted">Last updated 5 October 2026. Draft pending legal review.</p>

      <h2>1. Who we are and what these terms cover</h2>
      <p>
        CompanyMgmt is an online service for running a business: people and attendance, leave, payroll, tasks, announcements and documents, a point of sale with
        customers’ dues, expenses, inventory and accounting, an optional AI assistant, and tools to connect other systems (an API, webhooks, company sign-in and
        provisioning). It is run by Mehboob Ehsan Khan, Dhaka, Bangladesh (“we”, “us”). These terms are between us and the business that creates a workspace
        (“you”), represented by the person who accepts them. The <Link href="/privacy">Privacy Policy</Link>, the <Link href="/dpa">Data Processing Addendum</Link> and
        the plan on the <Link href="/pricing">pricing page</Link> are part of these terms.
      </p>

      <h2>2. Accounts and access</h2>
      <ul>
        <li>Workspace owners and admins must be at least 18 and able to act for the business. You decide who else gets access, including staff accounts.</li>
        <li>Keep passwords, passkeys, API keys, till PINs and registered till devices safe. You’re responsible for what happens under your workspace’s accounts and keys.</li>
        <li>Tell us straight away at security@companymgmt.app if you think an account, key or device has been misused.</li>
      </ul>

      <h2>3. Your data</h2>
      <p>
        Everything your workspace holds (“customer data”) belongs to you. You let us store and process it only to provide, secure and support the service, as set
        out in the Data Processing Addendum. We don’t sell it, use it for advertising, or use it to train AI models. You can export it at any time.
      </p>

      <h2>4. Your responsibilities</h2>
      <ul>
        <li>You need a lawful basis to collect what you put in, and you must tell your staff (and your customers, where relevant) what you record and why.</li>
        <li>
          If you turn on the location check, tell staff that their position is checked when they clock in and out, use it only to confirm attendance, and do any
          assessment your local law requires.
        </li>
        <li>You keep the records your law requires (for example wage, attendance and leave records, receipts and books) for as long as it requires. Export before you delete.</li>
        <li>You’re responsible for the systems you connect with the API, webhooks or company sign-in, and for keeping their credentials safe.</li>
      </ul>

      <h2>5. Calculations, taxes and records</h2>
      <p>
        CompanyMgmt is a tool, not an adviser. Taxes, prices, payroll rules, salary tax tables and tax-return templates are set by you and your accountant; the
        defaults we provide are starting points. You’re responsible for checking that pay, deductions, taxes charged on sales, receipts, payslips and returns are
        correct and meet your legal obligations, and for filing and paying taxes. Receipts printed by the till aren’t official VAT invoices (for example Mushak
        forms in Bangladesh) unless your accountant confirms they meet the rules. Document acknowledgements record that someone confirmed they read a document;
        they are not electronic signatures.
      </p>

      <h2>6. AI features</h2>
      <ul>
        <li>The assistant is off until the workspace owner accepts these AI terms and switches it on; admins choose which features are on.</li>
        <li>
          Questions and the records needed to answer them are sent to Google (Gemini) under its paid-service terms, which don’t allow Google to use them to improve
          its products. Your workspace can use its own Gemini key instead.
        </li>
        <li>The assistant only sees what the person asking may see. Anything it proposes to change does nothing until that person confirms it.</li>
        <li>AI answers can be wrong. Check important facts, numbers and drafts before relying on them. AI output in your workspace is your data.</li>
      </ul>

      <h2>7. API and integrations</h2>
      <ul>
        <li>The API, webhooks, company sign-in and provisioning are available on the plans that include them, subject to rate limits and the developer documentation.</li>
        <li>We keep the /v1 API backwards compatible and announce breaking changes at least 6 months ahead (12 months for provisioning), as the developer documentation describes.</li>
        <li>Webhooks go only to public HTTPS addresses you choose; what happens there is your responsibility.</li>
      </ul>

      <h2>8. Acceptable use</h2>
      <p>
        Don’t use the service for anything unlawful or harmful: no unlawful surveillance of people, no data you have no right to hold, no malware, no attempts to
        get around security or access other workspaces, no scraping or load that degrades the service for others, and no reselling without our written agreement.
        Report security issues as described on the <Link href="/security">security page</Link>.
      </p>

      <h2>9. Plans, trials and fees</h2>
      <p>
        Plans and limits are on the pricing page. At the end of a trial the workspace moves to the Free plan; nothing is deleted. Online payment isn’t live yet;
        when it is, fees, renewals, taxes on fees and refunds will be set out here with at least 30 days’ notice before anything is charged.
      </p>

      <h2>10. Availability, support and changes</h2>
      <p>
        We work to keep the service running and your data backed up, but we can’t promise it will never be interrupted. We may change or improve features; we’ll
        give at least 30 days’ notice of changes that take something important away or that materially change these terms. If you don’t agree to a change you can
        stop using the service and export your data.
      </p>

      <h2>11. Suspension</h2>
      <p>
        We may suspend access if needed to stop a security threat, serious abuse or a breach of these terms. We’ll tell you why, limit it to what’s necessary, and
        lift it once the problem is fixed.
      </p>

      <h2>12. Ending, export and deletion</h2>
      <ul>
        <li>You can stop at any time. The owner can export the whole workspace from Settings and delete it.</li>
        <li>
          A deleted workspace can be restored by its owner for 30 days. After that every record is erased and the owner receives a signed deletion certificate;
          encrypted backups that still hold it expire within a further 35 days.
        </li>
        <li>If we end the service for you (other than for serious breach), we’ll give you at least 30 days to export first.</li>
      </ul>

      <h2>13. Warranties</h2>
      <p>The service is provided “as is”. To the extent the law allows, we don’t give warranties beyond those in these terms, including that it fits a particular purpose.</p>

      <h2>14. Liability</h2>
      <p>
        To the extent the law allows, neither of us is liable for indirect or consequential losses (such as lost profits or data you could have exported), and our
        total liability for all claims is limited to the greater of the amount you paid us in the 12 months before the claim and USD 100. Nothing limits liability
        that can’t be limited by law, such as for fraud.
      </p>

      <h2>15. Indemnity</h2>
      <p>You’ll cover our reasonable losses from claims by third parties caused by data you had no right to put in the service or by your unlawful use of it.</p>

      <h2>16. Law and disputes</h2>
      <p>These terms are governed by the laws of Bangladesh, and the courts of Dhaka have jurisdiction. Mandatory consumer or data-protection rights where you are still apply.</p>

      <h2>17. Contact</h2>
      <p>hello@companymgmt.app · security issues: security@companymgmt.app</p>
    </article>
  );
}
