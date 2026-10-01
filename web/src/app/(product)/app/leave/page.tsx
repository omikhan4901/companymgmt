"use client";

import { CalendarOff, Plus } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useBalances, useLeaveRequests } from "@/api/hooks";
import { useSession, useWorkspace } from "@/auth/session";
import { AwayCalendar } from "@/components/leave/away-calendar";
import { BalanceCards } from "@/components/leave/balance-cards";
import { LeaveSettings } from "@/components/leave/leave-settings";
import { RequestDialog } from "@/components/leave/request-dialog";
import { RequestList } from "@/components/leave/request-list";
import { TeamBalances } from "@/components/leave/team-balances";
import { PageHeader } from "@/components/page";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { todayIn } from "@/lib/format";
import { useTab } from "@/lib/use-tab";

function MineTab() {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const year = Number(todayIn(timezone).slice(0, 4));
  const balances = useBalances(year);
  const requests = useLeaveRequests({ mine: true });
  return (
    <div className="flex flex-col gap-5">
      {balances.data && <BalanceCards balances={balances.data.balances} />}
      <h2 className="text-lg font-semibold">{t("leave.myRequests")}</h2>
      <RequestList requests={requests.data} mine canDecide={false} />
    </div>
  );
}

function RequestsTab() {
  const { t } = useTranslation();
  const [status, setStatus] = useState("pending");
  const requests = useLeaveRequests({ status });
  return (
    <div className="flex flex-col gap-3">
      <Field label={t("common.status")} className="w-52">
        <Select value={status} onChange={(e) => setStatus(e.target.value)}>
          {["pending", "approved", "rejected", "cancelled", "all"].map((s) => (
            <option key={s} value={s}>
              {s === "all" ? t("common.all") : t(`leave.status.${s}`)}
            </option>
          ))}
        </Select>
      </Field>
      <RequestList requests={requests.data} mine={false} canDecide />
    </div>
  );
}

export default function LeavePage() {
  const { t } = useTranslation();
  const { can, hasModule } = useSession();
  const [asking, setAsking] = useState(false);
  const tabs = [
    { key: "mine", label: t("leave.tabs.mine"), content: <MineTab />, show: can("leave.self") },
    { key: "requests", label: t("leave.tabs.requests"), content: <RequestsTab />, show: can("leave.approve") },
    { key: "calendar", label: t("leave.tabs.calendar"), content: <AwayCalendar />, show: can("leave.self") },
    { key: "balances", label: t("leave.tabs.balances"), content: <TeamBalances />, show: can("leave.view") },
    { key: "settings", label: t("leave.tabs.settings"), content: <LeaveSettings />, show: can("leave.settings") },
  ].filter((x) => x.show);
  const [active, setActive] = useTab(tabs.map((x) => x.key));
  if (!hasModule("leave") || !can("leave.self")) return <EmptyState icon={<CalendarOff />} title={t("common.notAllowed")} />;
  return (
    <>
      <PageHeader
        title={t("leave.title")}
        sub={t("leave.sub")}
        actions={
          <Button variant="primary" onClick={() => setAsking(true)}>
            <Plus aria-hidden="true" />
            {t("leave.ask")}
          </Button>
        }
      />
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
      {asking && <RequestDialog onClose={() => setAsking(false)} />}
    </>
  );
}
