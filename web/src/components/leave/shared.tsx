"use client";

import { useTranslation } from "react-i18next";

import { ApiError } from "@/api/client";
import i18n from "@/i18n";
import { cn } from "@/lib/cn";
import { errorMessage } from "@/lib/errors";
import { formatDay, formatNumber } from "@/lib/format";

export const requestTone = { pending: "warn", approved: "success", rejected: "danger", cancelled: "neutral" } as const;

const KNOWN = ["not_enough_balance", "overlap", "crosses_year", "no_working_days", "self_approval", "already_started"];

/** Leave errors in the person's language (the API answers in English). */
export function leaveError(error: unknown): string {
  if (error instanceof ApiError && error.code && KNOWN.includes(error.code)) {
    const available = typeof error.body.available === "number" ? formatNumber(error.body.available) : "";
    return i18n.t(`leave.errors.${error.code}`, { available });
  }
  return errorMessage(error);
}

/** "3 days", "½ day" in the current language. */
export function useDays() {
  const { t } = useTranslation();
  return (n: number) => t("leave.days", { count: n === 1 ? 1 : 2, formatted: formatNumber(n) });
}

/** A date range in a compact form ("12 Mar – 14 Mar 2027", or one day). */
export function formatSpan(start: string, end: string, half?: string | null): string {
  if (start === end) {
    const day = formatDay(start, { weekday: "short" });
    return half && half !== "none" ? `${day} · ${i18n.t(`leave.half.${half}`)}` : day;
  }
  const sameYear = start.slice(0, 4) === end.slice(0, 4);
  return `${formatDay(start, sameYear ? { year: undefined } : {})} – ${formatDay(end)}`;
}

export function TypeDot({ color, className }: { color?: string | null; className?: string }) {
  return <span className={cn("inline-block size-2.5 shrink-0 rounded-full bg-accent", className)} style={color ? { background: color } : undefined} aria-hidden="true" />;
}
