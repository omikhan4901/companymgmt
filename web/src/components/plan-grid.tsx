import { Check } from "lucide-react";
import Link from "next/link";

import plans from "@/data/plans.json";
import { cn } from "@/lib/cn";

const money = (cents: number) => `$${(cents / 100).toLocaleString("en-US", { maximumFractionDigits: cents % 100 ? 2 : 0 })}`;

type SitePlan = (typeof plans)[number];

function features(p: SitePlan) {
  const out: { text: string; soon?: boolean }[] = [];
  if (p.max_people !== null) out.push({ text: `Up to ${p.max_people} people` });
  else if (p.included_people && p.extra_person_cents) {
    out.push({ text: `${p.included_people} people included` });
    out.push({ text: `then ${money(p.extra_person_cents)} per extra person` });
  } else out.push({ text: "Any number of people" });
  out.push({ text: p.max_branches === null ? "Unlimited branches" : p.max_branches === 1 ? "1 branch" : `${p.max_branches} branches` });
  out.push({ text: p.max_modules === null ? "Every module" : `Any ${p.max_modules} modules` });
  out.push({ text: "Location-checked clock-in" });
  if (p.features.custom_roles) out.push({ text: "Custom roles" });
  if (p.features.api) out.push({ text: "API access", soon: true });
  if (p.features.sso) out.push({ text: "Single sign-on", soon: true });
  return out;
}

/** The public price list, from the same data the API's plans are checked against. */
export function PlanGrid() {
  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {plans.map((p) => {
        const featured = p.key === "growth";
        return (
          <li key={p.key} className={cn("flex flex-col rounded-[var(--radius-card)] border bg-surface p-5", featured ? "border-accent ring-2 ring-accent/25" : "border-border")}>
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-lg font-semibold">{p.name}</h3>
              {featured && <span className="rounded-md bg-accent-soft px-2 py-0.5 text-xs font-semibold text-accent-soft-text">Most popular</span>}
            </div>
            <p className="mt-3 font-site-display text-3xl font-semibold tabular-nums">
              {p.price_month_cents === null ? "Let's talk" : p.price_month_cents === 0 ? "$0" : money(p.price_month_cents)}
              {p.price_month_cents ? <span className="font-sans text-sm font-normal text-muted">/month</span> : null}
            </p>
            <p className="text-xs text-muted">{p.price_year_cents ? `or ${money(p.price_year_cents)}/year (2 months free)` : p.price_month_cents === 0 ? "Free for good" : "Annual contract"}</p>
            <ul className="mt-4 flex flex-1 flex-col gap-2 text-sm">
              {features(p).map((f) => (
                <li key={f.text} className="flex items-start gap-2">
                  <Check className="mt-0.5 size-4 shrink-0 text-accent-soft-text" aria-hidden="true" />
                  <span>
                    {f.text}
                    {f.soon && <span className="ml-1 text-xs text-muted">(coming soon)</span>}
                  </span>
                </li>
              ))}
            </ul>
            <Link
              href={p.key === "enterprise" ? "mailto:hello@companymgmt.app" : "/signup"}
              className={cn(
                "mt-5 rounded-[10px] px-4 py-2.5 text-center text-sm font-semibold",
                featured ? "bg-accent text-on-accent hover:bg-accent-hover" : "border border-border hover:bg-surface-2",
              )}
            >
              {p.key === "enterprise" ? "Contact us" : p.key === "free" ? "Start free" : "Start 14-day trial"}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
