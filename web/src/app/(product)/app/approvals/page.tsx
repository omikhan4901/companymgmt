"use client";

import { CheckCircle2, Inbox } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useSession } from "@/auth/session";
import { ApprovalRow, useApprovals } from "@/components/approvals/approvals";
import { PageHeader } from "@/components/page";
import { EmptyState } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatNumber } from "@/lib/format";

const FILTERS = ["all", "leave", "time_fix"] as const;

export default function ApprovalsPage() {
  const { t } = useTranslation();
  const { can } = useSession();
  const allowed = can("leave.approve") || can("attendance.approve");
  const approvals = useApprovals(allowed);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");
  if (!allowed) return <EmptyState icon={<Inbox />} title={t("common.notAllowed")} />;
  const items = (approvals.data ?? []).filter((i) => filter === "all" || i.kind === filter);
  const count = (k: string) => (approvals.data ?? []).filter((i) => k === "all" || i.kind === k).length;
  return (
    <>
      <PageHeader title={t("approvals.title")} sub={t("approvals.sub")} />
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        <Tabs value={filter} onValueChange={(v) => setFilter(v as (typeof FILTERS)[number])}>
          <TabsList className="mb-4 w-fit max-w-full overflow-x-auto">
            {FILTERS.map((f) => (
              <TabsTrigger key={f} value={f}>
                {t(`approvals.filters.${f}`)} ({formatNumber(count(f))})
              </TabsTrigger>
            ))}
          </TabsList>
          {FILTERS.map((f) => (
            <TabsContent key={f} value={f}>
              {filter !== f ? null : approvals.isPending ? (
                <div className="grid place-items-center py-16">
                  <Spinner />
                </div>
              ) : items.length === 0 ? (
                <EmptyState icon={<CheckCircle2 />} title={t("approvals.empty")}>
                  {t("approvals.emptyBody")}
                </EmptyState>
              ) : (
                <ul className="flex flex-col gap-3">
                  {items.map((item) => (
                    <ApprovalRow key={`${item.kind}-${item.id}`} item={item} />
                  ))}
                </ul>
              )}
            </TabsContent>
          ))}
        </Tabs>
      </div>
    </>
  );
}
