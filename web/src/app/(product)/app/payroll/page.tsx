"use client";

import { Banknote, FileText } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useMyPayslips } from "@/api/hooks";
import type { Payslip } from "@/api/types";
import { useSession } from "@/auth/session";
import { PageHeader } from "@/components/page";
import { AdvancesTab } from "@/components/payroll/advances";
import { PayrollSettingsTab } from "@/components/payroll/payroll-settings";
import { PayslipDialog } from "@/components/payroll/payslip-view";
import { RunsTab } from "@/components/payroll/runs";
import { SalariesTab } from "@/components/payroll/salaries";
import { formatMonth, money } from "@/components/payroll/shared";
import { Card, EmptyState } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useTab } from "@/lib/use-tab";

function MineTab() {
  const { t } = useTranslation();
  const payslips = useMyPayslips();
  const [open, setOpen] = useState<Payslip | null>(null);
  if (payslips.data?.length === 0) {
    return (
      <Card>
        <EmptyState icon={<FileText />} title={t("payroll.noPayslips")} />
      </Card>
    );
  }
  return (
    <>
      <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {(payslips.data ?? []).map((p) => (
          <li key={p.id}>
            <button type="button" onClick={() => setOpen(p)} className="w-full text-left">
              <Card className="flex flex-col gap-2 p-5 transition-colors hover:border-border-strong">
                <span className="text-sm text-muted">{p.period ? formatMonth(p.period) : ""}</span>
                <span className="font-display text-3xl font-semibold tabular-nums">{money(p.net, p.currency ?? "BDT")}</span>
                <span className="text-[13px] text-muted">{t("payroll.net")}</span>
              </Card>
            </button>
          </li>
        ))}
      </ul>
      {open && <PayslipDialog slip={open} onClose={() => setOpen(null)} />}
    </>
  );
}

export default function PayrollPage() {
  const { t } = useTranslation();
  const { can, hasModule } = useSession();
  const manage = can("payroll.manage");
  const tabs = [
    { key: "mine", label: t("payroll.tabs.mine"), content: <MineTab />, show: can("payroll.self") },
    { key: "runs", label: t("payroll.tabs.runs"), content: <RunsTab />, show: can("payroll.view") || can("payroll.run") },
    { key: "salaries", label: t("payroll.tabs.salaries"), content: <SalariesTab />, show: manage },
    { key: "advances", label: t("payroll.tabs.advances"), content: <AdvancesTab />, show: manage },
    { key: "settings", label: t("payroll.tabs.settings"), content: <PayrollSettingsTab />, show: manage },
  ].filter((x) => x.show);
  const [active, setActive] = useTab(tabs.map((x) => x.key));
  if (!hasModule("payroll") || tabs.length === 0) return <EmptyState icon={<Banknote />} title={t("common.notAllowed")} />;
  return (
    <>
      <PageHeader title={t("payroll.title")} sub={t("payroll.sub")} />
      <Tabs value={active} onValueChange={setActive}>
        <TabsList className="mb-5 w-fit max-w-full overflow-x-auto">
          {tabs.map((x) => (
            <TabsTrigger key={x.key} value={x.key}>
              {x.label}
            </TabsTrigger>
          ))}
        </TabsList>
        {tabs.map((x) => (
          <TabsContent key={x.key} value={x.key}>
            {active === x.key && x.content}
          </TabsContent>
        ))}
      </Tabs>
    </>
  );
}
