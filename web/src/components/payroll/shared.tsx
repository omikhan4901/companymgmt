"use client";

import { ApiError } from "@/api/client";
import i18n from "@/i18n";
import { errorMessage } from "@/lib/errors";
import { formatDay, formatMoney } from "@/lib/format";

export const runTone = { draft: "neutral", review: "warn", finalized: "accent", paid: "success" } as const;

const KNOWN = ["self_approval", "run_exists", "empty_run", "wrong_status"];

export function payrollError(error: unknown): string {
  if (error instanceof ApiError && KNOWN.includes(error.code)) return i18n.t(`payroll.errors.${error.code}`);
  return errorMessage(error);
}

/** "September 2026" in the current language. */
export function formatMonth(period: string): string {
  return formatDay(`${period}-01`, { day: undefined, month: "long", year: "numeric" });
}

export function money(minor: number, currency: string): string {
  return formatMoney(minor, currency);
}

const TRANSLATED = new Set(["basic", "house_rent", "medical", "conveyance", "other", "hours", "days", "overtime", "unpaid_leave", "tax", "rounding"]);

/** Standard lines in the reader's language; one-off items keep the name they were given. */
export function lineLabel(code: string, label: string): string {
  return TRANSLATED.has(code) ? i18n.t(`payroll.line.${code}`) : label;
}
