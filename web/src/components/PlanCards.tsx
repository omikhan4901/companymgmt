import { Check } from "lucide-react";
import { useTranslation } from "react-i18next";

import { usePlans } from "@/api/hooks";
import type { Plan } from "@/api/types";
import { formatMoney, formatNumber } from "@/lib/format";

import { Pill } from "./ui";

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

export default function PlanCards({ current }: { current?: string }) {
  const { t } = useTranslation();
  const plans = usePlans();
  return (
    <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {(plans.data ?? []).map((plan) => (
        <li key={plan.key} className={`flex flex-col rounded-2xl border bg-white p-4 ${plan.key === current ? "border-brand ring-2 ring-brand-100" : "border-slate-200"}`}>
          <div className="flex items-center justify-between gap-2">
            <h3 className="font-display text-lg font-bold text-ink">{plan.name}</h3>
            {plan.key === current ? <Pill tone="brand">{t("plans.current")}</Pill> : null}
          </div>
          <p className="mt-2 text-2xl font-bold text-ink tabular">
            {plan.price_month_cents === null ? t("plans.custom") : plan.price_month_cents === 0 ? t("plans.free") : formatMoney(plan.price_month_cents, "USD")}
            {plan.price_month_cents ? <span className="text-sm font-normal text-slate-500">{t("plans.month")}</span> : null}
          </p>
          {plan.price_year_cents ? (
            <p className="text-xs text-slate-500 tabular">
              {formatMoney(plan.price_year_cents, "USD")}
              {t("plans.year")}
            </p>
          ) : null}
          <ul className="mt-3 flex flex-col gap-1.5 text-sm text-slate-700">
            {planFeatures(plan, t).map((f) => (
              <li key={f} className="flex items-start gap-2">
                <Check size={16} className="mt-0.5 shrink-0 text-brand" aria-hidden="true" />
                {f}
              </li>
            ))}
          </ul>
        </li>
      ))}
    </ul>
  );
}
