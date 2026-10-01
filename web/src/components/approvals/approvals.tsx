"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { ApprovalItem } from "@/api/types";
import { useWorkspace } from "@/auth/session";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { errorMessage } from "@/lib/errors";
import { formatAgo, formatDateTime, formatDay, formatNumber, formatTime } from "@/lib/format";

export const approvalKeys = { all: ["approvals"] as const };

export function useApprovals(enabled = true) {
  return useQuery({
    queryKey: approvalKeys.all,
    queryFn: () => api<{ items: ApprovalItem[] }>("/v1/approvals").then((r) => r.items),
    enabled,
    refetchInterval: 60_000,
  });
}

/** What's being asked, in one line. */
export function useSummary() {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  return (item: ApprovalItem): string => {
    if (item.kind === "leave") {
      const dates = item.start_date === item.end_date ? formatDay(item.start_date, { weekday: "short" }) : `${formatDay(item.start_date, { year: undefined })} – ${formatDay(item.end_date)}`;
      return `${item.leave_type_name ?? t("leave.away")} · ${dates} · ${t("approvals.days", { count: item.days ?? 0, formatted: formatNumber(item.days ?? 0) })}`;
    }
    const kind = t(`attendance.kind.${item.fix_kind}`);
    if (!item.clock_in_at) return kind;
    const end = item.clock_out_at ? `–${formatTime(item.clock_out_at, timezone)}` : "";
    return `${kind} · ${formatDateTime(item.clock_in_at, timezone)}${end}`;
  };
}

/** One request with Approve and Reject (and an optional note). */
export function ApprovalRow({ item, compact = false }: { item: ApprovalItem; compact?: boolean }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const summary = useSummary();
  const [note, setNote] = useState("");
  const decide = useMutation({
    mutationFn: (action: "approve" | "reject") => api(`/v1/approvals/${item.kind}/${item.id}/${action}`, { body: { note: note.trim() || null } }),
    onSuccess: (_, action) => {
      toast.success(action === "approve" ? t("approvals.approved", { name: item.employee_name }) : t("approvals.rejected", { name: item.employee_name }));
      void queryClient.invalidateQueries({ queryKey: approvalKeys.all });
      void queryClient.invalidateQueries({ queryKey: ["leave"] });
      void queryClient.invalidateQueries({ queryKey: ["attendance"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const name = item.employee_name ?? t("notifications.someone");
  return (
    <li className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-3.5">
      <div className="flex items-start gap-3">
        <Avatar name={name} className="size-9" />
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="flex flex-wrap items-center gap-2 text-sm font-semibold">
            {name}
            <Badge tone={item.kind === "leave" ? "accent" : "warn"}>{t(`approvals.kinds.${item.kind}`)}</Badge>
          </span>
          <span className="text-sm">{summary(item)}</span>
          {item.reason && !compact && <span className="text-sm text-muted">“{item.reason}”</span>}
          <span className="text-xs text-muted">{t("approvals.asked", { when: formatAgo(item.requested_at) })}</span>
        </div>
        {compact && (
          <div className="flex shrink-0 gap-1.5">
            <Button size="iconSm" aria-label={`${t("approvals.reject")}: ${name}`} onClick={() => decide.mutate("reject")} disabled={decide.isPending}>
              <X aria-hidden="true" />
            </Button>
            <Button size="iconSm" variant="solid" aria-label={`${t("approvals.approve")}: ${name}`} onClick={() => decide.mutate("approve")} disabled={decide.isPending}>
              <Check aria-hidden="true" />
            </Button>
          </div>
        )}
      </div>
      {!compact && (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} placeholder={t("approvals.note")} aria-label={`${t("approvals.note")}: ${name}`} className="sm:flex-1" />
          <div className="flex gap-2">
            <Button onClick={() => decide.mutate("reject")} disabled={decide.isPending} aria-label={`${t("approvals.reject")}: ${name}`}>
              <X aria-hidden="true" />
              {t("approvals.reject")}
            </Button>
            <Button variant="primary" onClick={() => decide.mutate("approve")} loading={decide.isPending} aria-label={`${t("approvals.approve")}: ${name}`}>
              <Check aria-hidden="true" />
              {t("approvals.approve")}
            </Button>
          </div>
        </div>
      )}
    </li>
  );
}
