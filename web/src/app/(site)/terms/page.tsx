import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "The terms for using CompanyMgmt.",
};

export default function Page() {
  return (
    <article className="prose-legal mx-auto max-w-3xl px-4 py-16 md:px-6">
    <h1 className="text-4xl font-semibold tracking-tight">Terms of Service</h1>
    <p className="mt-2 text-sm text-muted">Last updated 30 September 2026. Draft pending legal review.</p>

    <h2>The service</h2>
    <p>CompanyMgmt lets businesses manage their people and attendance online. These terms are between you (or the business you act for) and CompanyMgmt, run by Mehboob Ehsan Khan, Dhaka, Bangladesh.</p>

    <h2>Accounts</h2>
    <ul>
      <li>You must be at least 18 and give accurate information.</li>
      <li>Keep your password safe. Workspace owners are responsible for who they give access to.</li>
      <li>Tell us straight away if you think your account has been misused.</li>
    </ul>

    <h2>Your data</h2>
    <p>The data you put in your workspace belongs to you. You give us permission to store and process it only to provide the service. You&apos;re responsible for having the right to collect it, including telling your staff that attendance is recorded and, if you turn on the location check, that their location is checked when they clock in and out.</p>

    <h2>Acceptable use</h2>
    <p>Don't use the service for anything illegal, to harm others, to probe or break its security, or to overload it.</p>

    <h2>Plans and trials</h2>
    <p>Plans and limits are described on the pricing page. At the end of a trial the workspace moves to the Free plan; nothing is deleted. Paid plans will be billed through our payment partner when online payment launches.</p>

    <h2>Availability and changes</h2>
    <p>We work to keep the service running and your data backed up, but we can&apos;t promise it will never be interrupted. We may change features; we&apos;ll give notice of changes that take something away.</p>

    <h2>Ending</h2>
    <p>You can stop using the service at any time and ask us to delete your workspace. Export what you need first (attendance exports to a spreadsheet today). We may suspend accounts that break these terms.</p>

    <h2>Liability</h2>
    <p>The service is provided as it is. To the extent the law allows, our total liability is limited to the amount you paid us in the 12 months before the claim.</p>

    <h2>Law</h2>
    <p>These terms are governed by the laws of Bangladesh, and the courts of Dhaka have jurisdiction.</p>
  </article>
  );
}
