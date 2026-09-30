"use client";

import { Check } from "lucide-react";
import { useTranslation } from "react-i18next";

import { usePlans } from "@/api/hooks";
import type { Plan } from "@/api/types";
import { cn } from "@/lib/cn";
import { formatMoney, formatNumber } from "@/lib/format";

import { Badge } from "./ui/badge";

export function planFeatures(plan: Plan, t: (k: string, v?: Record<string, unknown>) => string): string[] {
  const out: string[] = [];
  if (plan.max_people !== null) out.push(t("plans.people", { count: formatNumber(plan.max_people) }));
  else if (plan.included_people && plan.extra_person_cents) {
    out.push(t("plans.included", { count: formatNumber(plan.included_people) }));
    out.push(t("plans.extraPerson", { price: formatMoney(plan.extra_person_cents, "USD") }));
  } else out.push(t("plans.unlimitedPeople"));
  out.push(plan.max_branches === null ? t("plans.unlimitedBranches") : plan.max_branches === 1 ? t("plans.branch") : t("plans.branches", { count: formatNumber(plan.max_branches) }));
  out.push(plan.max_modules === null ? t("plans.allModules") : t("plans.modules", { count: formatNumber(plan.max_modules) }));
  if (plan.features.custom_roles) out.push(t("plans.customRoles"));
  if (plan.features.api) out.push(`${t("plans.api")} (${t("common.comingSoon")})`);
  if (plan.features.sso) out.push(`${t("plans.sso")} (${t("common.comingSoon")})`);
  return out;
}

export function PlanCards({ current }: { current?: string }) {
  const { t } = useTranslation();
  const plans = usePlans();
  return (
    <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {(plans.data ?? []).map((plan) => (
        <li key={plan.key} className={cn("flex flex-col rounded-[var(--radius-card)] border bg-surface p-5", plan.key === current ? "border-accent ring-2 ring-accent/25" : "border-border")}>
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-lg font-semibold">{plan.name}</h3>
            {plan.key === current && <Badge tone="accent">{t("plans.current")}</Badge>}
          </div>
          <p className="mt-3 font-display text-3xl font-semibold tabular-nums">
            {plan.price_month_cents === null ? t("plans.custom") : plan.price_month_cents === 0 ? t("plans.free") : formatMoney(plan.price_month_cents, "USD")}
            {plan.price_month_cents ? <span className="font-sans text-sm font-normal text-muted">{t("plans.month")}</span> : null}
          </p>
          {plan.price_year_cents ? (
            <p className="text-xs text-muted tabular-nums">
              {formatMoney(plan.price_year_cents, "USD")}
              {t("plans.year")}
            </p>
          ) : null}
          <ul className="mt-4 flex flex-col gap-2 text-sm">
            {planFeatures(plan, t).map((f) => (
              <li key={f} className="flex items-start gap-2">
                <Check className="mt-0.5 size-4 shrink-0 text-accent-soft-text" aria-hidden="true" />
                {f}
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ul>
  );
}
