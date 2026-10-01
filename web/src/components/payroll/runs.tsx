"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Banknote, Download, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api, download } from "@/api/client";
import { usePayRun, usePayRuns } from "@/api/hooks";
import type { PayRunDetail, Payslip } from "@/api/types";
import { useSession, useWorkspace } from "@/auth/session";
import { PeopleSelect } from "@/components/people-select";
import { useStepUp } from "@/components/step-up";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, EmptyState } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select } from "@/components/ui/input";
import { Table, Td, Th } from "@/components/ui/table";
import { applyFieldErrors } from "@/lib/errors";
import { formatNumber, todayIn } from "@/lib/format";
import { toMinor } from "@/lib/money";

import { PayslipDialog } from "./payslip-view";
import { formatMonth, money, payrollError, runTone } from "./shared";

function previousMonth(today: string): string {
  const [y, m] = today.split("-").map(Number) as [number, number];
  return m === 1 ? `${y - 1}-12` : `${y}-${String(m - 1).padStart(2, "0")}`;
}

function NewRunDialog({ onDone }: { onDone: (id: string | null) => void }) {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const queryClient = useQueryClient();
  const { register, handleSubmit, setError, formState } = useForm({
    defaultValues: { period: previousMonth(todayIn(timezone)), bonus_label: "" },
  });
  const create = useMutation({
    mutationFn: (v: { period: string; bonus_label: string }) =>
      api<PayRunDetail>("/v1/payroll/runs", { body: { period: v.period, bonus_label: v.bonus_label.trim() || undefined } }),
    onSuccess: (run) => {
      void queryClient.invalidateQueries({ queryKey: ["payroll"] });
      onDone(run.id);
    },
    onError: (e) => {
      if (!applyFieldErrors(setError, ["period", "bonus_label"], e)) toast.error(payrollError(e));
    },
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onDone(null)}>
      <DialogContent
        title={t("payroll.newRun")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={() => onDone(null)}>{t("common.cancel")}</Button>
            <Button variant="primary" type="submit" form="run-form" loading={create.isPending}>
              {t("payroll.newRun")}
            </Button>
          </>
        }
      >
        <form id="run-form" onSubmit={handleSubmit((v) => create.mutate(v))} className="flex flex-col gap-4" noValidate>
          <Field label={t("payroll.month")} error={formState.errors.period?.message}>
            <Input type="month" {...register("period", { required: t("common.required") })} />
          </Field>
          <Field label={t("payroll.bonus")} optional={t("common.optional")} help={t("payroll.bonusHelp")}>
            <Input maxLength={80} placeholder={t("payroll.bonusPlaceholder")} {...register("bonus_label")} />
          </Field>
        </form>
      </DialogContent>
    </Dialog>
  );
}

interface ItemValues {
  employee_id: string;
  kind: "earning" | "deduction";
  label: string;
  amount: string;
}

function ItemDialog({ runId, onDone }: { runId: string; onDone: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { register, handleSubmit, setError, formState } = useForm<ItemValues>({
    defaultValues: { employee_id: "", kind: "earning", label: "", amount: "" },
  });
  const add = useMutation({
    mutationFn: (v: ItemValues) => api(`/v1/payroll/runs/${runId}/items`, { body: { ...v, label: v.label.trim(), amount: toMinor(v.amount) } }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["payroll", "runs"] });
      onDone();
    },
    onError: (e) => {
      if (!applyFieldErrors(setError, ["employee_id", "kind", "label", "amount"], e)) toast.error(payrollError(e));
    },
  });
  const required = { required: t("common.required") };
  return (
    <Dialog open onOpenChange={(o) => !o && onDone()}>
      <DialogContent
        title={t("payroll.addItem")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onDone}>{t("common.cancel")}</Button>
            <Button variant="primary" type="submit" form="item-form" loading={add.isPending}>
              {t("common.add")}
            </Button>
          </>
        }
      >
        <form id="item-form" onSubmit={handleSubmit((v) => add.mutate(v))} className="flex flex-col gap-4" noValidate>
          <Field label={t("payroll.person")} error={formState.errors.employee_id?.message}>
            <PeopleSelect emptyLabel={t("attendance.choosePerson")} {...register("employee_id", required)} />
          </Field>
          <Field label={t("payroll.itemKind")}>
            <Select {...register("kind")}>
              <option value="earning">{t("payroll.kind.earning")}</option>
              <option value="deduction">{t("payroll.kind.deduction")}</option>
            </Select>
          </Field>
          <Field label={t("payroll.itemLabel")} error={formState.errors.label?.message}>
            <Input maxLength={120} placeholder={t("payroll.itemLabelPlaceholder")} {...register("label", required)} />
          </Field>
          <Field label={t("payroll.amount")} error={formState.errors.amount?.message}>
            <Input
              inputMode="decimal"
              {...register("amount", { ...required, validate: (v) => ((toMinor(v) ?? 0) > 0 ? true : t("common.required")) })}
            />
          </Field>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function RunView({ id, onBack }: { id: string; onBack: () => void }) {
  const { t } = useTranslation();
  const { can } = useSession();
  const queryClient = useQueryClient();
  const run = usePayRun(id);
  const [open, setOpen] = useState<Payslip | null>(null);
  const [adding, setAdding] = useState(false);
  const [confirm, setConfirm] = useState<"finalize" | "delete" | null>(null);
  const [stepUp, stepUpDialog] = useStepUp();
  const act = useMutation({
    mutationFn: (action: "recompute" | "submit" | "reopen" | "finalize" | "paid" | "delete") =>
      action === "delete"
        ? api(`/v1/payroll/runs/${id}`, { method: "DELETE" })
        : stepUp(() => api(`/v1/payroll/runs/${id}/${action}`, { method: "POST" })),
    onSuccess: (_, action) => {
      setConfirm(null);
      void queryClient.invalidateQueries({ queryKey: ["payroll"] });
      const toasts: Record<string, string> = {
        recompute: t("payroll.recomputed"),
        submit: t("payroll.submitted"),
        finalize: t("payroll.finalized"),
        paid: t("payroll.paidToast"),
      };
      if (toasts[action]) toast.success(toasts[action]);
      if (action === "delete") onBack();
    },
    onError: (e) => {
      setConfirm(null);
      if (e !== null) toast.error(payrollError(e));
    },
  });
  const sheet = async () => {
    try {
      await stepUp(() => download(`/v1/payroll/runs/${id}/transfers.csv`, {}, `payroll-${run.data?.period}-transfers.csv`));
    } catch (e) {
      if (e !== null) toast.error(payrollError(e));
    }
  };
  const r = run.data;
  if (!r) return null;
  const month = formatMonth(r.period);
  const preparer = can("payroll.run");
  const approver = can("payroll.approve");
  return (
    <div className="flex flex-col gap-4">
      <div>
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft aria-hidden="true" />
          {t("payroll.back")}
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-display text-2xl font-semibold">{month}</h2>
        <Badge tone={runTone[r.status]}>{t(`payroll.status.${r.status}`)}</Badge>
        {r.bonus_label && <Badge>{r.bonus_label}</Badge>}
        <div className="ml-auto flex flex-wrap gap-2">
          {r.status === "draft" && preparer && (
            <>
              <Button size="sm" variant="ghost" className="text-danger" onClick={() => setConfirm("delete")}>
                <Trash2 aria-hidden="true" />
                {t("payroll.deleteRun")}
              </Button>
              <Button size="sm" onClick={() => setAdding(true)}>
                <Plus aria-hidden="true" />
                {t("payroll.addItem")}
              </Button>
              <Button size="sm" onClick={() => act.mutate("recompute")} loading={act.isPending && act.variables === "recompute"}>
                <RefreshCw aria-hidden="true" />
                {t("payroll.recompute")}
              </Button>
              <Button size="sm" variant="primary" onClick={() => act.mutate("submit")} loading={act.isPending && act.variables === "submit"}>
                {t("payroll.submit")}
              </Button>
            </>
          )}
          {r.status === "review" && (
            <>
              {preparer && (
                <Button size="sm" onClick={() => act.mutate("reopen")}>
                  {t("payroll.reopen")}
                </Button>
              )}
              {approver && (
                <Button size="sm" variant="primary" onClick={() => setConfirm("finalize")}>
                  {t("payroll.finalize")}
                </Button>
              )}
            </>
          )}
          {(r.status === "finalized" || r.status === "paid") && approver && (
            <Button size="sm" onClick={() => void sheet()}>
              <Download aria-hidden="true" />
              {t("payroll.transferSheet")}
            </Button>
          )}
          {r.status === "finalized" && approver && (
            <Button size="sm" variant="primary" onClick={() => act.mutate("paid")}>
              {t("payroll.markPaid")}
            </Button>
          )}
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-4">
        {[
          [t("nav.people"), formatNumber(r.headcount)],
          [t("payroll.gross"), money(r.gross, r.currency)],
          [t("payroll.deductions"), money(r.deductions, r.currency)],
          [t("payroll.net"), money(r.net, r.currency)],
        ].map(([label, value]) => (
          <Card key={label} className="flex flex-col gap-1 p-4">
            <span className="text-sm text-muted">{label}</span>
            <span className="font-display text-xl font-semibold tabular-nums">{value}</span>
          </Card>
        ))}
      </div>
      {r.missing.length > 0 && <Alert tone="warn">{t("payroll.missing", { names: r.missing.map((m) => String(m.employee_name)).join(", ") })}</Alert>}
      <Card className="overflow-hidden">
        <Table label={month}>
          <thead>
            <tr>
              <Th>{t("payroll.person")}</Th>
              <Th className="text-right">{t("payroll.gross")}</Th>
              <Th className="text-right">{t("payroll.deductions")}</Th>
              <Th className="text-right">{t("payroll.net")}</Th>
              <Th>{t("payroll.paidBy")}</Th>
            </tr>
          </thead>
          <tbody>
            {r.payslips.map((s) => (
              <tr key={s.id} className="hover:bg-surface-2/60">
                <Td className="max-w-56 truncate">
                  <button type="button" className="font-medium text-accent-soft-text hover:underline" onClick={() => setOpen(s)}>
                    {s.employee_name}
                  </button>
                  {s.carried_forward > 0 && (
                    <Badge tone="warn" className="ml-2">
                      {t("payroll.carried")}
                    </Badge>
                  )}
                </Td>
                <Td className="text-right tabular-nums">{money(s.gross, r.currency)}</Td>
                <Td className="text-right tabular-nums">{money(s.deductions, r.currency)}</Td>
                <Td className="text-right font-semibold tabular-nums">{money(s.net, r.currency)}</Td>
                <Td className="whitespace-nowrap text-muted">{t(`payroll.method.${s.payment_method}`)}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>
      {open && <PayslipDialog slip={open} onClose={() => setOpen(null)} />}
      {adding && <ItemDialog runId={r.id} onDone={() => setAdding(false)} />}
      <ConfirmDialog
        open={confirm === "delete"}
        title={t("payroll.deleteRunTitle", { month })}
        confirmLabel={t("common.delete")}
        busy={act.isPending}
        onConfirm={() => act.mutate("delete")}
        onClose={() => setConfirm(null)}
      />
      <Dialog open={confirm === "finalize"} onOpenChange={(o) => !o && setConfirm(null)}>
        <DialogContent
          title={t("payroll.finalizeTitle", { month })}
          description={t("payroll.finalizeBody")}
          closeLabel={t("common.close")}
          footer={
            <>
              <Button onClick={() => setConfirm(null)}>{t("common.cancel")}</Button>
              <Button variant="primary" loading={act.isPending} onClick={() => act.mutate("finalize")}>
                {t("payroll.finalize")}
              </Button>
            </>
          }
        >
          <p className="text-2xl font-semibold tabular-nums">{money(r.net, r.currency)}</p>
        </DialogContent>
      </Dialog>
      {stepUpDialog}
    </div>
  );
}

export function RunsTab() {
  const { t } = useTranslation();
  const { can } = useSession();
  const runs = usePayRuns();
  const [selected, setSelected] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  if (selected) return <RunView id={selected} onBack={() => setSelected(null)} />;
  return (
    <div className="flex flex-col gap-4">
      {can("payroll.run") && (
        <div>
          <Button variant="primary" onClick={() => setCreating(true)}>
            <Plus aria-hidden="true" />
            {t("payroll.newRun")}
          </Button>
        </div>
      )}
      {runs.data?.length === 0 ? (
        <Card>
          <EmptyState icon={<Banknote />} title={t("payroll.noRuns")} />
        </Card>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {(runs.data ?? []).map((r) => (
            <li key={r.id}>
              <button type="button" onClick={() => setSelected(r.id)} className="w-full text-left">
                <Card className="flex flex-col gap-3 p-4 transition-colors hover:border-border-strong">
                  <span className="flex items-center justify-between gap-2">
                    <span className="font-semibold">{formatMonth(r.period)}</span>
                    <Badge tone={runTone[r.status]}>{t(`payroll.status.${r.status}`)}</Badge>
                  </span>
                  <span className="font-display text-2xl font-semibold tabular-nums">{money(r.net, r.currency)}</span>
                  <span className="text-[13px] text-muted">
                    {t("payroll.people", { count: r.headcount, formatted: formatNumber(r.headcount) })}
                    {r.bonus_label ? ` · ${r.bonus_label}` : ""}
                  </span>
                </Card>
              </button>
            </li>
          ))}
        </ul>
      )}
      {creating && (
        <NewRunDialog
          onDone={(id) => {
            setCreating(false);
            if (id) setSelected(id);
          }}
        />
      )}
    </div>
  );
}
