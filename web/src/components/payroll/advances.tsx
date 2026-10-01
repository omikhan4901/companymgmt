"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { HandCoins, Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import { useLoans } from "@/api/hooks";
import type { Loan } from "@/api/types";
import { useWorkspace } from "@/auth/session";
import { PeopleSelect } from "@/components/people-select";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, EmptyState } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select } from "@/components/ui/input";
import { Table, Td, Th } from "@/components/ui/table";
import { applyFieldErrors } from "@/lib/errors";
import { todayIn } from "@/lib/format";
import { toMinor } from "@/lib/money";

import { formatMonth, money, payrollError } from "./shared";

interface Values {
  employee_id: string;
  kind: "advance" | "loan";
  label: string;
  principal: string;
  installment: string;
  start_period: string;
}

function AdvanceDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const queryClient = useQueryClient();
  const { register, handleSubmit, setError, formState } = useForm<Values>({
    defaultValues: { employee_id: "", kind: "advance", label: "", principal: "", installment: "", start_period: todayIn(timezone).slice(0, 7) },
  });
  const save = useMutation({
    mutationFn: (v: Values) =>
      api("/v1/payroll/loans", {
        body: { ...v, label: v.label.trim(), principal: toMinor(v.principal), installment: toMinor(v.installment) },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["payroll", "loans"] });
      onClose();
    },
    onError: (e) => {
      if (!applyFieldErrors(setError, ["employee_id", "label", "principal", "installment", "start_period"], e)) toast.error(payrollError(e));
    },
  });
  const required = { required: t("common.required") };
  const positive = { ...required, validate: (x: string) => ((toMinor(x) ?? 0) > 0 ? true : t("common.required")) };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={t("payroll.addAdvance")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" type="submit" form="advance-form" loading={save.isPending}>
              {t("common.add")}
            </Button>
          </>
        }
      >
        <form id="advance-form" onSubmit={handleSubmit((v) => save.mutate(v))} className="flex flex-col gap-4" noValidate>
          <Field label={t("payroll.person")} error={formState.errors.employee_id?.message}>
            <PeopleSelect emptyLabel={t("attendance.choosePerson")} {...register("employee_id", required)} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("payroll.itemKind")}>
              <Select {...register("kind")}>
                <option value="advance">{t("payroll.advanceKind.advance")}</option>
                <option value="loan">{t("payroll.advanceKind.loan")}</option>
              </Select>
            </Field>
            <Field label={t("payroll.itemLabel")} error={formState.errors.label?.message}>
              <Input maxLength={120} {...register("label", required)} />
            </Field>
            <Field label={t("payroll.principal")} error={formState.errors.principal?.message}>
              <Input inputMode="decimal" {...register("principal", positive)} />
            </Field>
            <Field label={t("payroll.installment")} error={formState.errors.installment?.message}>
              <Input inputMode="decimal" {...register("installment", positive)} />
            </Field>
            <Field label={t("payroll.startPeriod")} error={formState.errors.start_period?.message}>
              <Input type="month" {...register("start_period", required)} />
            </Field>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function AdvancesTab() {
  const { t } = useTranslation();
  const { currency } = useWorkspace();
  const queryClient = useQueryClient();
  const loans = useLoans(true);
  const [adding, setAdding] = useState(false);
  const [closing, setClosing] = useState<Loan | null>(null);
  const close = useMutation({
    mutationFn: (id: string) => api(`/v1/payroll/loans/${id}/close`, { method: "POST" }),
    onSuccess: () => {
      setClosing(null);
      void queryClient.invalidateQueries({ queryKey: ["payroll", "loans"] });
    },
    onError: (e) => toast.error(payrollError(e)),
  });
  return (
    <div className="flex flex-col gap-4">
      <div>
        <Button variant="primary" onClick={() => setAdding(true)}>
          <Plus aria-hidden="true" />
          {t("payroll.addAdvance")}
        </Button>
      </div>
      {loans.data?.length === 0 ? (
        <Card>
          <EmptyState icon={<HandCoins />} title={t("payroll.noAdvances")} />
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <Table label={t("payroll.advances")}>
            <thead>
              <tr>
                <Th>{t("payroll.person")}</Th>
                <Th>{t("payroll.itemLabel")}</Th>
                <Th className="text-right">{t("payroll.principal")}</Th>
                <Th className="text-right">{t("payroll.installment")}</Th>
                <Th className="text-right">{t("payroll.outstanding")}</Th>
                <Th>{t("payroll.startPeriod")}</Th>
                <Th>
                  <span className="sr-only">{t("common.actions")}</span>
                </Th>
              </tr>
            </thead>
            <tbody>
              {(loans.data ?? []).map((l) => (
                <tr key={l.id} className="hover:bg-surface-2/60">
                  <Td className="max-w-48 truncate font-medium">{l.employee_name}</Td>
                  <Td className="max-w-56 truncate">
                    {l.label} <Badge className="ml-1">{t(`payroll.advanceKind.${l.kind}`)}</Badge>
                  </Td>
                  <Td className="text-right tabular-nums">{money(l.principal, currency)}</Td>
                  <Td className="text-right tabular-nums">{money(l.installment, currency)}</Td>
                  <Td className="text-right font-semibold tabular-nums">{money(l.outstanding, currency)}</Td>
                  <Td className="whitespace-nowrap">{formatMonth(l.start_period)}</Td>
                  <Td className="text-right">
                    {l.status === "active" ? (
                      <Button size="sm" variant="ghost" onClick={() => setClosing(l)} aria-label={`${t("payroll.closeAdvance")}: ${l.label}`}>
                        {t("payroll.closeAdvance")}
                      </Button>
                    ) : (
                      <Badge>{t("payroll.closed")}</Badge>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
      {adding && <AdvanceDialog onClose={() => setAdding(false)} />}
      <ConfirmDialog
        open={!!closing}
        title={t("payroll.closeTitle", { label: closing?.label ?? "" })}
        confirmLabel={t("payroll.closeAdvance")}
        busy={close.isPending}
        onConfirm={() => closing && close.mutate(closing.id)}
        onClose={() => setClosing(null)}
      >
        <p className="text-sm text-muted">{t("payroll.closeBody")}</p>
      </ConfirmDialog>
    </div>
  );
}
