"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookUser, HandCoins, MessageCircle, Plus, Printer } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { Customer, Statement } from "@/api/types";
import { useSession, useWorkspace } from "@/auth/session";
import { PageHeader } from "@/components/page";
import { useCustomers } from "@/components/shop/data";
import { Button } from "@/components/ui/button";
import { Card, EmptyState } from "@/components/ui/card";
import { Switch } from "@/components/ui/choice";
import { Dialog, DialogContent, SheetContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Textarea } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Table, Td, Th } from "@/components/ui/table";
import { errorMessage } from "@/lib/errors";
import { formatDay, formatMoney } from "@/lib/format";
import { toMinor } from "@/lib/money";
import { whatsappLink } from "@/lib/whatsapp";

function CustomerDialog({ customer, onClose }: { customer: Customer | null; onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ name: customer?.name ?? "", phone: customer?.phone ?? "", address: customer?.address ?? "", note: customer?.note ?? "" });
  const [limit, setLimit] = useState(customer?.credit_limit != null ? String(customer.credit_limit / 100) : "");
  const save = useMutation({
    mutationFn: () => {
      const amount = limit.trim() ? toMinor(limit) : null;
      const body = { name: form.name.trim(), phone: form.phone || null, address: form.address || null, note: form.note || null, credit_limit: amount, ...(customer && amount === null ? { no_limit: true } : {}) };
      return customer ? api<Customer>(`/v1/customers/${customer.id}`, { method: "PATCH", body, version: customer.version }) : api<Customer>("/v1/customers", { method: "POST", body });
    },
    onSuccess: () => {
      toast.success(t("common.saved"));
      void queryClient.invalidateQueries({ queryKey: ["customers"] });
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={customer ? t("customers.edit") : t("customers.new")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" disabled={!form.name.trim()} loading={save.isPending} onClick={() => save.mutate()}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <Field label={t("common.name")}>
            <Input dir="auto" value={form.name} maxLength={200} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Field>
          <Field label={t("customers.phone")} optional={t("common.optional")}>
            <Input type="tel" value={form.phone} maxLength={40} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          </Field>
          <Field label={t("customers.address")} optional={t("common.optional")}>
            <Textarea dir="auto" rows={2} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
          </Field>
          <Field label={t("customers.limit")} help={t("customers.limitHelp")} optional={t("common.optional")}>
            <Input inputMode="decimal" value={limit} onChange={(e) => setLimit(e.target.value)} />
          </Field>
          <Field label={t("customers.note")} optional={t("common.optional")}>
            <Textarea dir="auto" rows={2} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
          </Field>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function CustomerSheet({ customer, onEdit }: { customer: Customer; onEdit: () => void }) {
  const { t } = useTranslation();
  const { can } = useSession();
  const workspace = useWorkspace();
  const queryClient = useQueryClient();
  const money = (n: number) => formatMoney(n, workspace.currency);
  const statement = useQuery({ queryKey: ["customers", customer.id, "statement"], queryFn: () => api<Statement>(`/v1/customers/${customer.id}/statement`) });
  const [amount, setAmount] = useState("");
  const [adjusting, setAdjusting] = useState(false);
  const [note, setNote] = useState("");
  const value = toMinor(amount);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["customers"] });
  const pay = useMutation({
    mutationFn: () =>
      adjusting
        ? api<Customer>(`/v1/customers/${customer.id}/adjustments`, { method: "POST", body: { amount: value, note } })
        : api<Customer>(`/v1/customers/${customer.id}/payments`, { method: "POST", body: { amount: value, note: note || null } }),
    onSuccess: () => {
      toast.success(t("common.saved"));
      setAmount("");
      setNote("");
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const balance = statement.data?.closing ?? customer.balance;
  const reminder = customer.phone && balance > 0 ? whatsappLink(customer.phone, t("customers.reminderText", { name: customer.name, amount: money(balance), shop: workspace.name }), workspace.country) : null;
  return (
    <SheetContent title={customer.name} closeLabel={t("common.close")}>
      <div className="flex flex-col gap-4 text-sm">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <span className="text-muted">{balance >= 0 ? t("customers.owes") : t("customers.youOwe")}</span>
          <span className="font-display text-2xl font-semibold tabular-nums">{money(Math.abs(balance))}</span>
        </div>
        <div className="flex flex-wrap gap-2 print:hidden">
          {reminder && (
            <a href={reminder} target="_blank" rel="noopener noreferrer" className="inline-flex h-8 items-center gap-2 rounded-[10px] border border-border px-3 text-[13px] font-medium hover:bg-surface-2">
              <MessageCircle className="size-4" aria-hidden="true" />
              {t("customers.remind")}
            </a>
          )}
          <Button size="sm" onClick={() => window.print()}>
            <Printer aria-hidden="true" />
            {t("customers.printStatement")}
          </Button>
          {can("customers.manage") && (
            <Button size="sm" onClick={onEdit}>
              {t("common.edit")}
            </Button>
          )}
        </div>
        {can("customers.manage") && (
          <Card className="flex flex-col gap-3 p-3 print:hidden">
            <label className="flex items-center gap-2">
              <Switch checked={adjusting} onCheckedChange={setAdjusting} aria-label={t("customers.adjustInstead")} />
              {t("customers.adjustInstead")}
            </label>
            <Field label={adjusting ? t("customers.adjustAmount") : t("customers.paymentAmount")} help={adjusting ? t("customers.adjustHelp") : undefined}>
              <Input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
            </Field>
            <Field label={t("customers.note")} optional={adjusting ? undefined : t("common.optional")}>
              <Input value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} />
            </Field>
            <Button variant="primary" className="self-start" disabled={!value || (adjusting && !note.trim())} loading={pay.isPending} onClick={() => pay.mutate()}>
              <HandCoins aria-hidden="true" />
              {adjusting ? t("customers.saveAdjustment") : t("customers.recordPayment")}
            </Button>
          </Card>
        )}
        {statement.isPending ? (
          <Spinner />
        ) : (
          <Table label={t("customers.statement")}>
            <thead>
              <tr>
                <Th>{t("common.date")}</Th>
                <Th>{t("customers.what")}</Th>
                <Th className="text-right">{t("customers.amount")}</Th>
                <Th className="text-right">{t("customers.balance")}</Th>
              </tr>
            </thead>
            <tbody>
              {(statement.data?.entries ?? []).map((e) => (
                <tr key={e.id}>
                  <Td className="whitespace-nowrap tabular-nums">{formatDay(e.occurred_on)}</Td>
                  <Td>
                    {t(`customers.kinds.${e.kind}`)}
                    {e.note ? <span className="block text-xs text-muted">{e.note}</span> : null}
                  </Td>
                  <Td className="text-right tabular-nums">{money(e.amount)}</Td>
                  <Td className="text-right tabular-nums">{money(e.balance)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </div>
    </SheetContent>
  );
}

export default function CustomersPage() {
  const { t } = useTranslation();
  const { can, hasModule } = useSession();
  const workspace = useWorkspace();
  const allowed = hasModule("customers") && can("customers.view");
  const [q, setQ] = useState("");
  const [owing, setOwing] = useState(false);
  const list = useCustomers(q, owing, allowed);
  const [open, setOpen] = useState<Customer | null>(null);
  const [editing, setEditing] = useState<Customer | null | "new">(null);
  const money = (n: number) => formatMoney(n, workspace.currency);
  if (!allowed) return <EmptyState icon={<BookUser />} title={t("common.notAllowed")} />;
  const owed = (list.data ?? []).reduce((n, c) => n + Math.max(0, c.balance), 0);
  return (
    <>
      <PageHeader
        title={t("customers.title")}
        sub={t("customers.sub")}
        actions={
          can("customers.manage") ? (
            <Button variant="primary" onClick={() => setEditing("new")}>
              <Plus aria-hidden="true" />
              {t("customers.new")}
            </Button>
          ) : undefined
        }
      />
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        <div className="flex flex-wrap items-end gap-3">
          <Input className="max-w-xs" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("customers.search")} aria-label={t("customers.search")} />
          <label className="flex items-center gap-2 text-sm">
            <Switch checked={owing} onCheckedChange={setOwing} aria-label={t("customers.onlyOwing")} />
            {t("customers.onlyOwing")}
          </label>
          <span className="ml-auto text-sm text-muted">{t("customers.totalOwed", { amount: money(owed) })}</span>
        </div>
        {list.isPending ? (
          <Spinner />
        ) : !list.data?.length ? (
          <EmptyState icon={<BookUser />} title={t("customers.none")} />
        ) : (
          <ul className="flex flex-col gap-2">
            {list.data.map((c) => (
              <li key={c.id}>
                <button type="button" onClick={() => setOpen(c)} className="flex w-full items-center gap-3 rounded-xl border border-border bg-surface px-4 py-3 text-left hover:border-border-strong">
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="font-medium">{c.name}</span>
                    <span className="text-xs text-muted">{[c.phone, c.last_activity ? t("customers.lastActivity", { date: formatDay(c.last_activity) }) : null].filter(Boolean).join(" · ")}</span>
                  </span>
                  <span className={`tabular-nums ${c.balance > 0 ? "font-semibold" : "text-muted"}`}>{money(c.balance)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <Dialog open={!!open} onOpenChange={(o) => !o && setOpen(null)}>
        {open && (
          <CustomerSheet
            customer={open}
            onEdit={() => {
              setEditing(open);
              setOpen(null);
            }}
          />
        )}
      </Dialog>
      {editing && <CustomerDialog customer={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </>
  );
}
