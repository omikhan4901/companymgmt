"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useForm, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { ApiError, api } from "@/api/client";
import { useLeaveTypes } from "@/api/hooks";
import type { LeaveQuote } from "@/api/types";
import { useSession, useWorkspace } from "@/auth/session";
import { PeopleSelect } from "@/components/people-select";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { applyFieldErrors } from "@/lib/errors";
import { formatDay, formatNumber, todayIn } from "@/lib/format";

import { leaveError, useDays } from "./shared";

interface Values {
  employee_id: string;
  leave_type_id: string;
  start_date: string;
  end_date: string;
  half_day: "none" | "morning" | "afternoon";
  reason: string;
}

const FIELDS = ["employee_id", "leave_type_id", "start_date", "end_date", "half_day", "reason"] as const;

export function RequestDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const { can } = useSession();
  const { timezone } = useWorkspace();
  const queryClient = useQueryClient();
  const days = useDays();
  const types = useLeaveTypes();
  const today = todayIn(timezone);
  const { register, handleSubmit, setError, setValue, control, formState } = useForm<Values>({
    defaultValues: { employee_id: "", leave_type_id: "", start_date: today, end_date: today, half_day: "none", reason: "" },
  });
  const [employee, typeId, start, end, half] = useWatch({ control, name: ["employee_id", "leave_type_id", "start_date", "end_date", "half_day"] });

  // Pick the first type once types load, and keep the end date from going before the start.
  useEffect(() => {
    if (!typeId && types.data?.[0]) setValue("leave_type_id", types.data[0].id);
  }, [typeId, types.data, setValue]);
  useEffect(() => {
    if (start && end && end < start) setValue("end_date", start);
  }, [start, end, setValue]);

  const kind = types.data?.find((x) => x.id === typeId);
  const singleDay = !!start && start === end;
  const halves = singleDay && kind?.allow_half_day;
  useEffect(() => {
    if (!halves && half !== "none") setValue("half_day", "none");
  }, [halves, half, setValue]);

  const ready = !!typeId && !!start && !!end && end >= start;
  const quote = useQuery({
    queryKey: ["leave", "quote", typeId, start, end, half, employee],
    queryFn: () =>
      api<LeaveQuote>("/v1/leave/quote", {
        query: { leave_type_id: typeId, from: start, to: end, half_day: half, employee_id: employee || undefined },
      }),
    enabled: ready,
    retry: false,
  });

  const save = useMutation({
    mutationFn: (v: Values) =>
      api("/v1/leave/requests", {
        body: {
          leave_type_id: v.leave_type_id,
          start_date: v.start_date,
          end_date: v.end_date,
          half_day: v.half_day,
          reason: v.reason.trim() || undefined,
          employee_id: v.employee_id || undefined,
        },
      }),
    onSuccess: () => {
      toast.success(t("leave.sent"));
      void queryClient.invalidateQueries({ queryKey: ["leave"] });
      onClose();
    },
    onError: (e) => {
      if (e instanceof ApiError && e.code !== "invalid") return toast.error(leaveError(e));
      if (!applyFieldErrors(setError, FIELDS, e)) toast.error(leaveError(e));
    },
  });

  const q = quote.data;
  const left = q && q.available !== null ? q.available - q.days : null;
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={t("leave.ask")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" type="submit" form="leave-form" loading={save.isPending} disabled={!!q && !q.enough}>
              {t("leave.ask")}
            </Button>
          </>
        }
      >
        <form id="leave-form" onSubmit={handleSubmit((v) => save.mutate(v))} className="flex flex-col gap-4" noValidate>
          {can("leave.manage") && (
            <Field label={t("leave.askFor")} error={formState.errors.employee_id?.message}>
              <PeopleSelect emptyLabel={t("leave.me")} {...register("employee_id")} />
            </Field>
          )}
          <Field label={t("leave.type")} error={formState.errors.leave_type_id?.message}>
            <Select {...register("leave_type_id", { required: t("common.required") })}>
              {(types.data ?? []).map((x) => (
                <option key={x.id} value={x.id}>
                  {x.name}
                </option>
              ))}
            </Select>
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("leave.from")} error={formState.errors.start_date?.message}>
              <Input type="date" {...register("start_date", { required: t("common.required") })} />
            </Field>
            <Field label={t("leave.to")} error={formState.errors.end_date?.message}>
              <Input type="date" min={start || undefined} {...register("end_date", { required: t("common.required") })} />
            </Field>
          </div>
          {halves && (
            <Field label={t("leave.length")}>
              <Select {...register("half_day")}>
                {(["none", "morning", "afternoon"] as const).map((h) => (
                  <option key={h} value={h}>
                    {t(`leave.half.${h}`)}
                  </option>
                ))}
              </Select>
            </Field>
          )}
          <Field label={t("common.reason")} optional={t("common.optional")} help={t("leave.reasonHelp")}>
            <Textarea rows={2} maxLength={500} {...register("reason")} />
          </Field>
          <div aria-live="polite">
            {q && q.days === 0 && <Alert tone="warn">{t("leave.errors.no_working_days")}</Alert>}
            {q && q.days > 0 && (
              <Alert tone={q.enough ? "info" : "warn"} title={days(q.days)}>
                {q.available === null ? t("leave.noLimit") : t("leave.leftAfter", { left: formatNumber(Math.max(left ?? 0, 0)) })}
                {!q.enough && <> · {leaveError(new ApiError(422, { code: "not_enough_balance", available: q.available }))}</>}
                {q.skipped.length > 0 && (
                  <span className="mt-1 block text-[13px]">
                    {t("leave.notCounted", { days: q.skipped.map((d) => formatDay(d, { weekday: "short", year: undefined })).join(", ") })}
                  </span>
                )}
              </Alert>
            )}
            {quote.error && <Alert tone="warn">{leaveError(quote.error)}</Alert>}
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
