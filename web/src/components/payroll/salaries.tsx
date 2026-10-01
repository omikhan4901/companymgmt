"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Wallet } from "lucide-react";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import { useSalaries } from "@/api/hooks";
import type { SalaryStructure } from "@/api/types";
import { useWorkspace } from "@/auth/session";
import { PeopleSelect } from "@/components/people-select";
import { Button } from "@/components/ui/button";
import { Card, EmptyState } from "@/components/ui/card";
import { Switch } from "@/components/ui/choice";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select } from "@/components/ui/input";
import { Table, Td, Th } from "@/components/ui/table";
import { applyFieldErrors } from "@/lib/errors";
import { todayIn } from "@/lib/format";
import { fromMinor, toMinor } from "@/lib/money";

import { money, payrollError } from "./shared";

interface Values {
  employee_id: string;
  effective_from: string;
  pay_rule: "monthly" | "hourly" | "daily";
  basic: string;
  house_rent: string;
  medical: string;
  conveyance: string;
  other: string;
  rate: string;
  overtime: boolean;
  deduct_tax: boolean;
  payment_method: "cash" | "bank" | "wallet";
  provider: string;
  account: string;
  note: string;
}

const AMOUNTS = ["basic", "house_rent", "medical", "conveyance", "other", "rate"] as const;
const FIELDS = ["employee_id", "effective_from", ...AMOUNTS, "provider", "account", "note"] as const;

function SalaryDialog({ current, onClose }: { current: SalaryStructure | null; onClose: () => void }) {
  const { t } = useTranslation();
  const { timezone, currency } = useWorkspace();
  const queryClient = useQueryClient();
  const { register, handleSubmit, setError, setValue, control, formState } = useForm<Values>({
    defaultValues: {
      employee_id: current?.employee_id ?? "",
      effective_from: `${todayIn(timezone).slice(0, 7)}-01`,
      pay_rule: current?.pay_rule ?? "monthly",
      basic: fromMinor(current?.basic),
      house_rent: fromMinor(current?.house_rent),
      medical: fromMinor(current?.medical),
      conveyance: fromMinor(current?.conveyance),
      other: fromMinor(current?.other),
      rate: fromMinor(current?.rate),
      overtime: current?.overtime ?? false,
      deduct_tax: current?.deduct_tax ?? true,
      payment_method: current?.payment_method ?? "cash",
      provider: current?.provider ?? "",
      account: "",
      note: current?.note ?? "",
    },
  });
  const v = useWatch({ control });
  const total = ["basic", "house_rent", "medical", "conveyance", "other"].reduce((sum, k) => sum + (toMinor(String(v[k as keyof Values] ?? "")) ?? 0), 0);
  const save = useMutation({
    mutationFn: (values: Values) => {
      const amounts = Object.fromEntries(AMOUNTS.map((k) => [k, toMinor(values[k]) ?? 0]));
      return api("/v1/payroll/salaries", {
        body: {
          employee_id: values.employee_id,
          effective_from: values.effective_from,
          pay_rule: values.pay_rule,
          ...amounts,
          overtime: values.overtime,
          deduct_tax: values.deduct_tax,
          payment_method: values.payment_method,
          provider: values.payment_method === "cash" ? undefined : values.provider.trim() || undefined,
          account: values.payment_method === "cash" ? undefined : values.account.trim() || undefined,
          note: values.note.trim() || undefined,
        },
      });
    },
    onSuccess: () => {
      toast.success(t("common.saved"));
      void queryClient.invalidateQueries({ queryKey: ["payroll"] });
      onClose();
    },
    onError: (e) => {
      if (!applyFieldErrors(setError, FIELDS, e)) toast.error(payrollError(e));
    },
  });
  const amount = (name: (typeof AMOUNTS)[number], label: string) => (
    <Field label={label} error={formState.errors[name]?.message}>
      <Input inputMode="decimal" {...register(name, { validate: (x) => (toMinor(x) === null || (toMinor(x) ?? 0) < 0 ? t("common.required") : true) })} />
    </Field>
  );
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={current ? `${t("payroll.setSalary")}: ${current.employee_name}` : t("payroll.setSalary")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" type="submit" form="salary-form" loading={save.isPending}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <form id="salary-form" onSubmit={handleSubmit((values) => save.mutate(values))} className="flex flex-col gap-4" noValidate>
          {!current && (
            <Field label={t("payroll.person")} error={formState.errors.employee_id?.message}>
              <PeopleSelect emptyLabel={t("attendance.choosePerson")} {...register("employee_id", { required: t("common.required") })} />
            </Field>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("payroll.effectiveFrom")} help={t("payroll.effectiveHelp")} error={formState.errors.effective_from?.message}>
              <Input type="date" {...register("effective_from", { required: t("common.required") })} />
            </Field>
            <Field label={t("payroll.payRule")}>
              <Select {...register("pay_rule")}>
                {(["monthly", "hourly", "daily"] as const).map((r) => (
                  <option key={r} value={r}>
                    {t(`payroll.rule.${r}`)}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          {v.pay_rule === "monthly" ? (
            <div className="grid gap-4 sm:grid-cols-2">
              {amount("basic", t("payroll.basic"))}
              {amount("house_rent", t("payroll.houseRent"))}
              {amount("medical", t("payroll.medical"))}
              {amount("conveyance", t("payroll.conveyance"))}
              {amount("other", t("payroll.other"))}
              <div className="flex flex-col justify-end pb-2 text-sm">
                <span className="text-muted">{t("payroll.monthlyTotal")}</span>
                <span className="font-display text-xl font-semibold tabular-nums">{money(total, currency)}</span>
              </div>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {amount("rate", v.pay_rule === "hourly" ? t("payroll.rateHourly") : t("payroll.rateDaily"))}
              {amount("basic", t("payroll.basic"))}
            </div>
          )}
          <div className="flex flex-col divide-y divide-border rounded-xl border border-border px-3.5 py-1">
            <label className="flex items-center justify-between gap-4 py-2 text-sm">
              {t("payroll.overtime")}
              <Switch checked={!!v.overtime} onCheckedChange={(on) => setValue("overtime", on)} />
            </label>
            <label className="flex items-center justify-between gap-4 py-2 text-sm">
              {t("payroll.deductTax")}
              <Switch checked={!!v.deduct_tax} onCheckedChange={(on) => setValue("deduct_tax", on)} />
            </label>
          </div>
          <Field label={t("payroll.paidBy")}>
            <Select {...register("payment_method")}>
              {(["cash", "bank", "wallet"] as const).map((m) => (
                <option key={m} value={m}>
                  {t(`payroll.method.${m}`)}
                </option>
              ))}
            </Select>
          </Field>
          {v.payment_method !== "cash" && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t("payroll.provider")} error={formState.errors.provider?.message}>
                <Input maxLength={80} placeholder={t("payroll.providerPlaceholder")} {...register("provider", { required: t("common.required") })} />
              </Field>
              <Field
                label={t("payroll.account")}
                help={current?.account_last4 ? t("payroll.accountKeep", { last4: current.account_last4 }) : t("payroll.accountHelp")}
                error={formState.errors.account?.message}
              >
                <Input inputMode="numeric" autoComplete="off" maxLength={34} {...register("account")} />
              </Field>
            </div>
          )}
          <Field label={t("payroll.note")} optional={t("common.optional")} help={t("payroll.unpaidRoleHelp")}>
            <Input maxLength={300} {...register("note")} />
          </Field>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function SalariesTab() {
  const { t } = useTranslation();
  const { currency } = useWorkspace();
  const salaries = useSalaries();
  const [editing, setEditing] = useState<SalaryStructure | "new" | null>(null);
  return (
    <div className="flex flex-col gap-4">
      <div>
        <Button variant="primary" onClick={() => setEditing("new")}>
          <Plus aria-hidden="true" />
          {t("payroll.setSalary")}
        </Button>
      </div>
      {salaries.data?.length === 0 ? (
        <Card>
          <EmptyState icon={<Wallet />} title={t("payroll.noSalaries")} />
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <Table label={t("payroll.salaries")}>
            <thead>
              <tr>
                <Th>{t("payroll.person")}</Th>
                <Th>{t("payroll.payRule")}</Th>
                <Th className="text-right">{t("payroll.monthlyTotal")}</Th>
                <Th>{t("payroll.paidBy")}</Th>
                <Th>{t("payroll.effectiveFrom")}</Th>
                <Th>
                  <span className="sr-only">{t("common.actions")}</span>
                </Th>
              </tr>
            </thead>
            <tbody>
              {(salaries.data ?? []).map((s) => (
                <tr key={s.id} className="hover:bg-surface-2/60">
                  <Td className="max-w-52 truncate font-medium">{s.employee_name}</Td>
                  <Td className="whitespace-nowrap">{t(`payroll.rule.${s.pay_rule}`)}</Td>
                  <Td className="text-right tabular-nums">{money(s.pay_rule === "monthly" ? s.monthly_total : s.rate, currency)}</Td>
                  <Td className="whitespace-nowrap text-muted">
                    {[t(`payroll.method.${s.payment_method}`), s.provider, s.account_last4 ? `··${s.account_last4}` : null].filter(Boolean).join(" · ")}
                  </Td>
                  <Td className="whitespace-nowrap tabular-nums">{s.effective_from}</Td>
                  <Td className="text-right">
                    <Button size="sm" variant="ghost" onClick={() => setEditing(s)} aria-label={`${t("common.edit")}: ${s.employee_name ?? ""}`}>
                      <Pencil aria-hidden="true" />
                      {t("common.edit")}
                    </Button>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
      {editing && <SalaryDialog current={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}
