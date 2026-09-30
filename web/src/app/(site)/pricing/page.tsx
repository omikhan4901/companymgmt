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
  { q: "Can I export my data?", a: "Yes. Attendance exports to a spreadsheet today, and a full workspace export is coming with the next release." },
];

export default function PricingPage() {
  return (
    <>
      <section className="mx-auto max-w-6xl px-4 py-16 md:px-6">
        <h1 className="text-center text-4xl font-semibold tracking-tight">Pricing</h1>
        <p className="mx-auto mt-3 max-w-xl text-center text-muted">One price for your whole workspace, not per user. Pay yearly and get two months free.</p>
        <div className="mt-10">
          <PlanGrid />
        </div>
        <p className="mt-6 text-center text-sm text-muted">Prices in US dollars. Online payment is coming soon.</p>
      </section>
      <section className="border-t border-border bg-surface">
        <div className="mx-auto max-w-3xl px-4 py-16 md:px-6">
          <h2 className="text-2xl font-semibold">Questions</h2>
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
