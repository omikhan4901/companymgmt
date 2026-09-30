"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { AttendanceRecord } from "@/api/types";
import { useWorkspace } from "@/auth/session";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Textarea } from "@/components/ui/input";
import { applyFieldErrors, errorMessage } from "@/lib/errors";
import { isoToZoned, zonedToIso } from "@/lib/format";

interface Values {
  clock_in_at: string;
  clock_out_at: string;
  reason: string;
}

/**
 * Ask a manager to fix a shift (wrong or missing times). `record` is the shift to fix;
 * without it, the request adds a missing shift.
 */
export function CorrectionDialog({ record, onClose }: { record?: AttendanceRecord; onClose: () => void }) {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const queryClient = useQueryClient();
  const { register, handleSubmit, setError, formState } = useForm<Values>({
    defaultValues: {
      clock_in_at: record ? isoToZoned(record.clock_in_at, timezone) : "",
      clock_out_at: record?.clock_out_at ? isoToZoned(record.clock_out_at, timezone) : "",
      reason: "",
    },
  });
  const required = { required: t("common.required") };

  const save = useMutation({
    mutationFn: (values: Values) =>
      api("/v1/attendance/corrections", {
        body: {
          kind: record ? "change" : "add",
          record_id: record?.id,
          clock_in_at: zonedToIso(values.clock_in_at, timezone),
          clock_out_at: zonedToIso(values.clock_out_at, timezone),
          reason: values.reason.trim(),
        },
      }),
    onSuccess: async () => {
      toast.success(t("attendance.requested"));
      await queryClient.invalidateQueries({ queryKey: ["attendance"] });
      onClose();
    },
    onError: (e) => {
      if (!applyFieldErrors(setError, ["clock_in_at", "clock_out_at", "reason"], e)) toast.error(errorMessage(e));
    },
  });

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent
        title={record ? t("attendance.fixTitle") : t("attendance.addMissing")}
        description={t("attendance.fixSub")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" type="submit" form="correction-form" loading={save.isPending}>
              {t("attendance.requestFix")}
            </Button>
          </>
        }
      >
        <form id="correction-form" onSubmit={handleSubmit((v) => save.mutate(v))} className="flex flex-col gap-4" noValidate>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("attendance.startTime")} error={formState.errors.clock_in_at?.message}>
              <Input type="datetime-local" {...register("clock_in_at", required)} />
            </Field>
            <Field label={t("attendance.endTime")} error={formState.errors.clock_out_at?.message}>
              <Input type="datetime-local" {...register("clock_out_at", required)} />
            </Field>
          </div>
          <Field label={t("common.reason")} help={t("attendance.reasonHelp")} error={formState.errors.reason?.message}>
            <Textarea rows={2} maxLength={500} {...register("reason", { ...required, minLength: { value: 3, message: t("attendance.reasonHelp") } })} />
          </Field>
        </form>
      </DialogContent>
    </Dialog>
  );
}
