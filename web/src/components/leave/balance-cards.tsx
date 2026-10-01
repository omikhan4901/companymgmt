"use client";

import { useTranslation } from "react-i18next";

import type { LeaveBalance } from "@/api/types";
import { Card } from "@/components/ui/card";
import { formatNumber } from "@/lib/format";

import { TypeDot } from "./shared";

/** One card per leave type: what's left, big; how it adds up, small. */
export function BalanceCards({ balances }: { balances: LeaveBalance[] }) {
  const { t } = useTranslation();
  return (
    <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {balances.map((b) => {
        const parts = [
          b.used ? t("leave.used", { n: formatNumber(b.used) }) : null,
          b.pending ? t("leave.waiting", { n: formatNumber(b.pending) }) : null,
          b.carried_over ? t("leave.carried", { n: formatNumber(b.carried_over) }) : null,
          b.adjusted ? t("leave.adjustedBy", { n: formatNumber(b.adjusted) }) : null,
        ].filter(Boolean);
        return (
          <li key={b.leave_type_id}>
            <Card className="flex h-full flex-col gap-3 p-5">
              <span className="flex items-center gap-2 text-sm font-medium">
                <TypeDot color={b.color} />
                {b.name}
              </span>
              {b.unlimited ? (
                <span className="font-display text-2xl font-semibold text-muted">{t("leave.noLimit")}</span>
              ) : (
                <span className="flex items-baseline gap-2">
                  <span className="font-display text-4xl font-semibold tracking-tight tabular-nums">{formatNumber(b.available ?? 0)}</span>
                  <span className="text-sm text-muted">{t("leave.available")}</span>
                </span>
              )}
              <span className="mt-auto text-[13px] text-muted">
                {!b.unlimited && b.full_year !== null && t("leave.ofYear", { total: formatNumber(b.full_year) })}
                {parts.length > 0 && <span className="block">{parts.join(" · ")}</span>}
              </span>
            </Card>
          </li>
        );
      })}
    </ul>
  );
}
