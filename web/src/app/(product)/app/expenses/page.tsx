"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, Paperclip, PiggyBank, Plus, Receipt as ReceiptIcon, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api, download } from "@/api/client";
import type { Expense, Expenses } from "@/api/types";
import { useSession, useWorkspace } from "@/auth/session";
import { PageHeader } from "@/components/page";
import { useExpenseCategories } from "@/components/shop/data";
import { Button } from "@/components/ui/button";
import { Card, EmptyState } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { errorMessage } from "@/lib/errors";
import { formatDay, formatMoney, todayIn } from "@/lib/format";
import { toMinor } from "@/lib/money";

const PAID_FROM = ["petty_cash", "drawer", "bank", "other"] as const;

function ExpenseDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const workspace = useWorkspace();
  const queryClient = useQueryClient();
  const categories = useExpenseCategories();
  const [form, setForm] = useState({ amount: "", occurred_on: todayIn(workspace.timezone), category_id: "", payee: "", note: "", paid_from: "petty_cash" as (typeof PAID_FROM)[number] });
  const [photo, setPhoto] = useState<File | null>(null);
  const amount = toMinor(form.amount);
  const save = useMutation({
    mutationFn: async () => {
      const made = await api<Expense>("/v1/expenses", {
        method: "POST",
        body: { ...form, amount, category_id: form.category_id || null, payee: form.payee || null, note: form.note || null },
      });
      if (photo) await api<Expense>(`/v1/expenses/${made.id}/receipt`, { method: "PUT", query: { filename: photo.name }, rawBody: photo });
      return made;
    },
    onSuccess: () => {
      toast.success(t("common.saved"));
      void queryClient.invalidateQueries({ queryKey: ["expenses"] });
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={t("expenses.new")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" disabled={!amount} loading={save.isPending} onClick={() => save.mutate()}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("expenses.amount")}>
              <Input inputMode="decimal" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} autoFocus />
            </Field>
            <Field label={t("common.date")}>
              <Input type="date" value={form.occurred_on} onChange={(e) => setForm({ ...form, occurred_on: e.target.value })} />
            </Field>
          </div>
          <Field label={t("expenses.category")}>
            <Select value={form.category_id} onChange={(e) => setForm({ ...form, category_id: e.target.value })}>
              <option value="">–</option>
              {(categories.data ?? []).filter((c) => c.active).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("expenses.payee")} optional={t("common.optional")}>
            <Input dir="auto" value={form.payee} maxLength={120} onChange={(e) => setForm({ ...form, payee: e.target.value })} />
          </Field>
          <Field label={t("expenses.paidFrom")}>
            <Select value={form.paid_from} onChange={(e) => setForm({ ...form, paid_from: e.target.value as (typeof PAID_FROM)[number] })}>
              {PAID_FROM.map((p) => (
                <option key={p} value={p}>
                  {t(`expenses.from.${p}`)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("expenses.note")} optional={t("common.optional")}>
            <Input dir="auto" value={form.note} maxLength={2000} onChange={(e) => setForm({ ...form, note: e.target.value })} />
          </Field>
          <Field label={t("expenses.photo")} optional={t("common.optional")} help={t("expenses.photoHelp")}>
            <Input type="file" accept="image/jpeg,image/png,image/webp,application/pdf" capture="environment" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />
          </Field>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function TopUp({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [amount, setAmount] = useState("");
  const value = toMinor(amount);
  const save = useMutation({
    mutationFn: () => api("/v1/expenses/top-ups", { method: "POST", body: { amount: value } }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["expenses"] });
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={t("expenses.topUp")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" disabled={!value} loading={save.isPending} onClick={() => save.mutate()}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <Field label={t("expenses.topUpAmount")}>
          <Input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus />
        </Field>
      </DialogContent>
    </Dialog>
  );
}

export default function ExpensesPage() {
  const { t } = useTranslation();
  const { can, hasModule } = useSession();
  const workspace = useWorkspace();
  const queryClient = useQueryClient();
  const allowed = hasModule("expenses") && can("expenses.record");
  const today = todayIn(workspace.timezone);
  const [month, setMonth] = useState(today.slice(0, 7));
  const [adding, setAdding] = useState(false);
  const [topping, setTopping] = useState(false);
  const last = new Date(Date.UTC(Number(month.slice(0, 4)), Number(month.slice(5, 7)), 0)).toISOString().slice(0, 10);
  const data = useQuery({ queryKey: ["expenses", month], queryFn: () => api<Expenses>("/v1/expenses", { query: { from: `${month}-01`, to: last } }), enabled: allowed });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/v1/expenses/${id}`, { method: "DELETE" }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["expenses"] }),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const money = (n: number) => formatMoney(n, workspace.currency);
  if (!allowed) return <EmptyState icon={<ReceiptIcon />} title={t("common.notAllowed")} />;
  const manage = can("expenses.manage");
  return (
    <>
      <PageHeader
        title={t("expenses.title")}
        sub={t("expenses.sub")}
        actions={
          <div className="flex flex-wrap gap-2">
            {manage && (
              <Button onClick={() => setTopping(true)}>
                <PiggyBank aria-hidden="true" />
                {t("expenses.topUp")}
              </Button>
            )}
            <Button variant="primary" onClick={() => setAdding(true)}>
              <Plus aria-hidden="true" />
              {t("expenses.new")}
            </Button>
          </div>
        }
      />
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        <div className="flex flex-wrap items-end gap-3">
          <Field label={t("expenses.month")} className="w-48">
            <Input type="month" value={month} onChange={(e) => setMonth(e.target.value)} />
          </Field>
        </div>
        {!data.data ? (
          <Spinner />
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <Card className="p-4">
                <p className="text-xs text-muted">{t("expenses.spent")}</p>
                <p className="font-display text-xl font-semibold tabular-nums">{money(data.data.total)}</p>
              </Card>
              {manage && (
                <Card className="p-4">
                  <p className="text-xs text-muted">{t("expenses.pettyCash")}</p>
                  <p className="font-display text-xl font-semibold tabular-nums">{money(data.data.petty_cash)}</p>
                </Card>
              )}
            </div>
            {data.data.by_category.length > 0 && (
              <Card className="p-4">
                <p className="mb-2 text-sm font-semibold">{t("expenses.byCategory")}</p>
                <ul className="flex flex-col gap-1 text-sm">
                  {data.data.by_category.map((c) => (
                    <li key={c.category_id ?? "none"} className="flex justify-between">
                      <span>{c.name || t("expenses.uncategorised")}</span>
                      <span className="tabular-nums">{money(c.total)}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
            {!data.data.items.length ? (
              <EmptyState icon={<Camera />} title={t("expenses.none")} />
            ) : (
              <ul className="flex flex-col gap-2">
                {data.data.items.map((e) => (
                  <li key={e.id}>
                    <Card className="flex items-center gap-3 px-4 py-3">
                      <span className="flex min-w-0 flex-1 flex-col">
                        <span className="font-medium">{e.kind === "top_up" ? t("expenses.topUpLine") : e.payee || e.category_name || t("expenses.expense")}</span>
                        <span className="text-xs text-muted">
                          {[formatDay(e.occurred_on), e.category_name, t(`expenses.from.${e.paid_from}`), e.created_by_name].filter(Boolean).join(" · ")}
                        </span>
                      </span>
                      {e.has_receipt && (
                        <Button
                          variant="ghost"
                          size="iconSm"
                          aria-label={t("expenses.downloadReceipt")}
                          onClick={() => void download(`/v1/expenses/${e.id}/receipt`, {}, e.receipt_name ?? "receipt").catch((err: unknown) => toast.error(errorMessage(err)))}
                        >
                          <Paperclip aria-hidden="true" />
                        </Button>
                      )}
                      <span className={`tabular-nums ${e.kind === "top_up" ? "text-success-text" : ""}`}>{e.kind === "top_up" ? `+${money(e.amount)}` : money(e.amount)}</span>
                      {manage && (
                        <Button variant="ghost" size="iconSm" aria-label={t("expenses.delete")} onClick={() => remove.mutate(e.id)}>
                          <Trash2 aria-hidden="true" />
                        </Button>
                      )}
                    </Card>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>
      {adding && <ExpenseDialog onClose={() => setAdding(false)} />}
      {topping && <TopUp onClose={() => setTopping(false)} />}
    </>
  );
}
