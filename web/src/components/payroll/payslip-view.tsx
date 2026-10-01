"use client";

import { Download } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { download } from "@/api/client";
import type { Payslip } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { formatNumber } from "@/lib/format";

import { formatMonth, lineLabel, money, payrollError } from "./shared";

function Lines({ slip, kind }: { slip: Payslip; kind: "earning" | "deduction" }) {
  const { t } = useTranslation();
  const currency = slip.currency ?? "BDT";
  const lines = slip.lines.filter((l) => l.kind === kind);
  return (
    <section className="flex flex-col gap-1">
      <h3 className="text-sm font-semibold">{kind === "earning" ? t("payroll.earnings") : t("payroll.deductions")}</h3>
      {lines.length === 0 && <p className="py-2 text-sm text-muted">{t("payroll.none")}</p>}
      <dl className="divide-y divide-border text-sm">
        {lines.map((l, i) => (
          <div key={`${l.code}-${i}`} className="flex justify-between gap-3 py-2">
            <dt>{lineLabel(l.code, l.label)}</dt>
            <dd className="tabular-nums">{money(l.amount, currency)}</dd>
          </div>
        ))}
        <div className="flex justify-between gap-3 py-2 font-semibold">
          <dt>{kind === "earning" ? t("payroll.totalEarnings") : t("payroll.totalDeductions")}</dt>
          <dd className="tabular-nums">{money(kind === "earning" ? slip.gross : slip.deductions, currency)}</dd>
        </div>
      </dl>
    </section>
  );
}

/** One payslip in a dialog, with PDF downloads in English and Bangla. */
export function PayslipDialog({ slip, onClose }: { slip: Payslip; onClose: () => void }) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState<string | null>(null);
  const currency = slip.currency ?? "BDT";
  const get = async (lang: "en" | "bn") => {
    setBusy(lang);
    try {
      await download(`/v1/payroll/payslips/${slip.id}/pdf`, { lang }, `payslip-${slip.period}-${lang}.pdf`);
    } catch (e) {
      toast.error(payrollError(e));
    } finally {
      setBusy(null);
    }
  };
  const facts = [
    [t("payroll.daysPaid"), `${formatNumber(slip.payable_days)} / ${formatNumber(slip.days_in_period)}`],
    [t("payroll.unpaidDays"), formatNumber(slip.unpaid_leave_days)],
    [t("payroll.hoursWorked"), formatNumber(Math.round((slip.worked_minutes / 60) * 10) / 10)],
    [t("payroll.overtimeHours"), formatNumber(Math.round((slip.overtime_minutes / 60) * 10) / 10)],
    [
      t("payroll.paidBy"),
      [t(`payroll.method.${slip.payment_method}`), slip.provider, slip.account_last4 ? `··${slip.account_last4}` : null].filter(Boolean).join(" · "),
    ],
  ];
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={`${slip.employee_name} · ${slip.period ? formatMonth(slip.period) : ""}`}
        description={[slip.job_title, slip.department_name].filter(Boolean).join(" · ") || undefined}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={() => void get("bn")} loading={busy === "bn"}>
              <Download aria-hidden="true" />
              {t("payroll.downloadBn")}
            </Button>
            <Button variant="primary" onClick={() => void get("en")} loading={busy === "en"}>
              <Download aria-hidden="true" />
              {t("payroll.download")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-5">
          <div className="flex items-baseline justify-between rounded-xl bg-accent-soft px-4 py-3 text-accent-soft-text">
            <span className="font-medium">{t("payroll.net")}</span>
            <span className="font-display text-2xl font-semibold tabular-nums">{money(slip.net, currency)}</span>
          </div>
          {slip.carried_forward > 0 && (
            <p className="text-sm text-warn-text">
              {t("payroll.carried")}: {money(slip.carried_forward, currency)}. {t("payroll.carriedHelp")}
            </p>
          )}
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            {facts.map(([k, v]) => (
              <div key={k} className="flex flex-col">
                <dt className="text-muted">{k}</dt>
                <dd className="font-medium tabular-nums">{v}</dd>
              </div>
            ))}
          </dl>
          <div className="grid gap-5 sm:grid-cols-2">
            <Lines slip={slip} kind="earning" />
            <Lines slip={slip} kind="deduction" />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
