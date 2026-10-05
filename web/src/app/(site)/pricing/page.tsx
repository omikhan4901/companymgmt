import type { Metadata } from "next";

import { PlanGrid } from "@/components/plan-grid";

export const metadata: Metadata = {
  title: "Pricing",
  description: "Free for up to 5 people. Paid plans from $9 a month for the whole workspace, with a 14-day trial.",
};

const faq = [
  { q: "What counts as a person?", a: "Anyone with an active profile in your workspace, whether or not they can sign in. People who have left don't count." },
  { q: "What happens when the trial ends?", a: "You move to the Free plan. Nothing is deleted. If you use more than the Free plan allows, the extra modules become read-only until you upgrade or switch some off." },
  { q: "Is the location check on every plan?", a: "Yes. Place your branches on the map and choose whether location is required, recorded only, or off." },
  { q: "Can I pay in taka?", a: "Online payment is coming soon, in US dollars by card. Until then, contact us and we'll set up your plan." },
  { q: "Can I export my data?", a: "Yes. Download your whole workspace at any time, or attendance and timesheets as spreadsheets. You can also bring your team in from a spreadsheet." },
  { q: "Do I need every module?", a: "No. Switch on only what you use: attendance, leave, payroll, point of sale, customers and dues, expenses, inventory, accounting, tasks, announcements, documents. Your plan sets how many." },
  { q: "Is the AI assistant included?", a: "Paid plans include a monthly number of questions. It's off until the workspace owner switches it on, and it never sees more than the person asking. Enterprise workspaces can use their own Gemini key." },
  { q: "Do you calculate my taxes?", a: "You or your accountant set the tax rates, payroll tax table and tax-return templates; CompanyMgmt applies them consistently. We don't give tax advice." },
  { q: "Can I connect other systems?", a: "Business and Enterprise include API keys, signed webhooks and a sandbox workspace. Enterprise adds company sign-in with Google, Microsoft or Okta, SCIM provisioning and network restrictions." },
];

export default function PricingPage() {
  return (
    <>
      <section className="mx-auto max-w-6xl px-4 py-16 md:px-6">
        <h1 className="text-center font-site-display text-4xl font-extrabold tracking-tight text-ink">Pricing</h1>
        <p className="mx-auto mt-3 max-w-xl text-center text-muted">One price for your whole workspace, not per user. Pay yearly and get two months free.</p>
        <div className="mt-10">
          <PlanGrid />
        </div>
        <p className="mt-6 text-center text-sm text-muted">Prices in US dollars. Online payment is coming soon.</p>
      </section>
      <section className="border-t border-slate-200 bg-slate-50">
        <div className="mx-auto max-w-3xl px-4 py-16 md:px-6">
          <h2 className="font-site-display text-2xl font-bold text-ink">Questions</h2>
          <dl className="mt-6 flex flex-col gap-6">
            {faq.map((f) => (
              <div key={f.q}>
                <dt className="font-semibold">{f.q}</dt>
                <dd className="mt-1 text-muted">{f.a}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>
    </>
  );
}
