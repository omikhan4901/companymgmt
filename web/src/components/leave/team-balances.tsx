"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Scale, SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import { useLeaveTypes, useTeamBalances } from "@/api/hooks";
import type { PersonBalances } from "@/api/types";
import { useSession, useWorkspace } from "@/auth/session";
import { Button } from "@/components/ui/button";
import { Card, EmptyState } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select } from "@/components/ui/input";
import { Table, Td, Th } from "@/components/ui/table";
import { applyFieldErrors, errorMessage } from "@/lib/errors";
import { formatNumber, formatYear, normalizeDigits, todayIn } from "@/lib/format";

import { TypeDot } from "./shared";

interface AdjustValues {
  leave_type_id: string;
  days: string;
  reason: string;
}

function AdjustDialog({ person, year, onClose }: { person: PersonBalances; year: number; onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const limited = person.balances.filter((b) => !b.unlimited);
  const { register, handleSubmit, setError, formState } = useForm<AdjustValues>({
    defaultValues: { leave_type_id: limited[0]?.leave_type_id ?? "", days: "", reason: "" },
  });
  const save = useMutation({
    mutationFn: (v: AdjustValues) =>
      api("/v1/leave/adjustments", {
        body: { employee_id: person.employee_id, leave_type_id: v.leave_type_id, year, days: Number(normalizeDigits(v.days)), reason: v.reason.trim() },
      }),
    onSuccess: () => {
      toast.success(t("leave.adjustedToast"));
      void queryClient.invalidateQueries({ queryKey: ["leave"] });
      onClose();
    },
    onError: (e) => {
      if (!applyFieldErrors(setError, ["leave_type_id", "days", "reason"], e)) toast.error(errorMessage(e));
    },
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={t("leave.adjustTitle", { name: person.employee_name })}
        description={formatYear(year)}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" type="submit" form="adjust-form" loading={save.isPending}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <form id="adjust-form" onSubmit={handleSubmit((v) => save.mutate(v))} className="flex flex-col gap-4" noValidate>
          <Field label={t("leave.type")} error={formState.errors.leave_type_id?.message}>
            <Select {...register("leave_type_id", { required: t("common.required") })}>
              {limited.map((b) => (
                <option key={b.leave_type_id} value={b.leave_type_id}>
                  {b.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("leave.adjustDays")} help={t("leave.adjustDaysHelp")} error={formState.errors.days?.message}>
            <Input inputMode="decimal" {...register("days", { required: t("common.required") })} />
          </Field>
          <Field label={t("common.reason")} error={formState.errors.reason?.message}>
            <Input maxLength={300} {...register("reason", { required: t("common.required"), minLength: { value: 3, message: t("common.required") } })} />
          </Field>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** Everyone's balances in one table (people with leave.view, within their scope). */
export function TeamBalances() {
  const { t } = useTranslation();
  const { can } = useSession();
  const { timezone } = useWorkspace();
  const thisYear = Number(todayIn(timezone).slice(0, 4));
  const [year, setYear] = useState(thisYear);
  const team = useTeamBalances(year);
  const types = useLeaveTypes();
  const [adjusting, setAdjusting] = useState<PersonBalances | null>(null);
  const columns = types.data ?? [];
  return (
    <div className="flex flex-col gap-4">
      <Field label={t("leave.year")} className="w-32">
        <Select value={year} onChange={(e) => setYear(Number(e.target.value))}>
          {[thisYear - 1, thisYear, thisYear + 1].map((y) => (
            <option key={y} value={y}>
              {formatYear(y)}
            </option>
          ))}
        </Select>
      </Field>
      {team.data?.length === 0 ? (
        <Card>
          <EmptyState icon={<Scale />} title={t("leave.teamEmpty")} />
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <Table label={t("leave.tabs.balances")}>
            <thead>
              <tr>
                <Th>{t("leave.person")}</Th>
                {columns.map((c) => (
                  <Th key={c.id} className="whitespace-nowrap">
                    <span className="flex items-center gap-1.5">
                      <TypeDot color={c.color} />
                      {c.name}
                    </span>
                  </Th>
                ))}
                {can("leave.manage") && (
                  <Th>
                    <span className="sr-only">{t("common.actions")}</span>
                  </Th>
                )}
              </tr>
            </thead>
            <tbody>
              {(team.data ?? []).map((p) => {
                const byType = new Map(p.balances.map((b) => [b.leave_type_id, b]));
                return (
                  <tr key={p.employee_id} className="hover:bg-surface-2/60">
                    <Td className="max-w-52 truncate font-medium">{p.employee_name}</Td>
                    {columns.map((c) => {
                      const b = byType.get(c.id);
                      return (
                        <Td key={c.id} className="tabular-nums">
                          {!b ? "–" : b.unlimited ? <span className="text-muted">{t("leave.noLimit")}</span> : (
                            <>
                              <span className="font-semibold">{formatNumber(b.available ?? 0)}</span>
                              {b.pending > 0 && <span className="ml-1.5 text-[13px] text-warn-text">({t("leave.waiting", { n: formatNumber(b.pending) })})</span>}
                            </>
                          )}
                        </Td>
                      );
                    })}
                    {can("leave.manage") && (
                      <Td className="text-right">
                        <Button size="sm" variant="ghost" onClick={() => setAdjusting(p)} aria-label={`${t("leave.adjust")}: ${p.employee_name}`}>
                          <SlidersHorizontal aria-hidden="true" />
                          {t("leave.adjust")}
                        </Button>
                      </Td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </Table>
        </Card>
      )}
      {adjusting && <AdjustDialog person={adjusting} year={year} onClose={() => setAdjusting(null)} />}
    </div>
  );
}
