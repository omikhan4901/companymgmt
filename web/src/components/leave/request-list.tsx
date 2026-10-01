"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CalendarCheck } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { LeaveRequest } from "@/api/types";
import { useWorkspace } from "@/auth/session";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, EmptyState } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Textarea } from "@/components/ui/input";
import { todayIn } from "@/lib/format";

import { formatSpan, leaveError, requestTone, useDays } from "./shared";

type Action = "approve" | "reject" | "cancel";

function NoteDialog({ request, action, onDone }: { request: LeaveRequest; action: "reject" | "cancel"; onDone: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const send = useMutation({
    mutationFn: () => api(`/v1/leave/requests/${request.id}/${action}`, { body: { note: note.trim() || undefined } }),
    onSuccess: () => {
      toast.success(t(action === "reject" ? "leave.rejectedToast" : "leave.cancelledToast"));
      void queryClient.invalidateQueries({ queryKey: ["leave"] });
      onDone();
    },
    onError: (e) => toast.error(leaveError(e)),
  });
  const name = request.employee_name ?? "";
  return (
    <Dialog open onOpenChange={(o) => !o && onDone()}>
      <DialogContent
        title={action === "reject" ? t("leave.rejectTitle", { name }) : t("leave.cancelTitle")}
        description={`${request.leave_type_name} · ${formatSpan(request.start_date, request.end_date, request.half_day)}`}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onDone}>{t("leave.keep")}</Button>
            <Button variant="danger" loading={send.isPending} onClick={() => send.mutate()}>
              {action === "reject" ? t("leave.reject") : t("leave.cancel")}
            </Button>
          </>
        }
      >
        <Field label={t("leave.note", { name })} optional={t("common.optional")}>
          <Textarea rows={2} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>
      </DialogContent>
    </Dialog>
  );
}

/** Leave requests as cards. `mine` shows the person's own; otherwise approvers decide. */
export function RequestList({ requests, mine, canDecide }: { requests: LeaveRequest[] | undefined; mine: boolean; canDecide: boolean }) {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const queryClient = useQueryClient();
  const days = useDays();
  const today = todayIn(timezone);
  const [asking, setAsking] = useState<{ request: LeaveRequest; action: "reject" | "cancel" } | null>(null);
  const approve = useMutation({
    mutationFn: (id: string) => api(`/v1/leave/requests/${id}/approve`, { body: {} }),
    onSuccess: () => {
      toast.success(t("leave.approvedToast"));
      void queryClient.invalidateQueries({ queryKey: ["leave"] });
    },
    onError: (e) => toast.error(leaveError(e)),
  });
  if (requests && requests.length === 0) {
    return (
      <Card>
        <EmptyState icon={<CalendarCheck />} title={mine ? t("leave.noRequests") : t("leave.noPending")} />
      </Card>
    );
  }
  const actions = (r: LeaveRequest): Action[] => {
    const live = r.status === "pending" || r.status === "approved";
    if (!live) return [];
    if (!mine && canDecide) return r.status === "pending" ? ["approve", "reject"] : ["cancel"];
    if (mine && (r.status === "pending" || r.start_date > today)) return ["cancel"];
    return [];
  };
  return (
    <>
      <ul className="grid gap-3 lg:grid-cols-2">
        {(requests ?? []).map((r) => (
          <li key={r.id}>
            <Card className="flex h-full flex-col gap-3 p-4">
              <div className="flex items-start gap-3">
                {!mine && <Avatar name={r.employee_name ?? "?"} className="size-9" />}
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">{mine ? r.leave_type_name : `${r.employee_name} · ${r.leave_type_name}`}</p>
                  <p className="text-sm text-muted tabular-nums">
                    {formatSpan(r.start_date, r.end_date, r.half_day)} · {days(r.days)}
                  </p>
                </div>
                <Badge tone={requestTone[r.status as keyof typeof requestTone] ?? "neutral"}>{t(`leave.status.${r.status}`)}</Badge>
              </div>
              {r.reason && <blockquote className="rounded-lg bg-surface-2 px-3 py-2 text-sm">{r.reason}</blockquote>}
              {r.decision_note && <p className="text-sm text-muted">→ {r.decision_note}</p>}
              {actions(r).length > 0 && (
                <div className="mt-auto flex flex-wrap gap-2">
                  {actions(r).map((a) =>
                    a === "approve" ? (
                      <Button key={a} size="sm" variant="solid" disabled={approve.isPending} onClick={() => approve.mutate(r.id)}>
                        {t("leave.approve")}
                      </Button>
                    ) : (
                      <Button key={a} size="sm" onClick={() => setAsking({ request: r, action: a })}>
                        {a === "reject" ? t("leave.reject") : t("leave.cancel")}
                      </Button>
                    ),
                  )}
                </div>
              )}
            </Card>
          </li>
        ))}
      </ul>
      {asking && <NoteDialog request={asking.request} action={asking.action} onDone={() => setAsking(null)} />}
    </>
  );
}
