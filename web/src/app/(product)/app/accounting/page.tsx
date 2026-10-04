"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Calculator, Plus, Printer, RotateCcw, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { BalanceSheet, BooksSettings, JournalEntry, Ledger, LedgerAccount, ProfitLoss, ReportRow, TaxReturn, TaxTemplate, TrialBalance } from "@/api/types";
import { useSession, useWorkspace } from "@/auth/session";
import { PageHeader } from "@/components/page";
import { useExpenseCategories, useTaxRates } from "@/components/shop/data";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, EmptyState } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Table, Td, Th } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { errorMessage } from "@/lib/errors";
import { formatDay, formatMoney, todayIn } from "@/lib/format";
import { toMinor } from "@/lib/money";
import { useTab } from "@/lib/use-tab";

const TYPES = ["asset", "liability", "equity", "income", "expense"] as const;

function useMoney() {
  const workspace = useWorkspace();
  return (n: number) => formatMoney(n, workspace.currency);
}

function useAccounts() {
  return useQuery({ queryKey: ["books", "accounts"], queryFn: () => api<LedgerAccount[]>("/v1/accounting/accounts"), staleTime: 60_000 });
}

function Period({ start, end, onChange }: { start: string; end: string; onChange: (s: string, e: string) => void }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-wrap items-end gap-3 print:hidden">
      <Field label={t("sales.from")} className="w-44">
        <Input type="date" value={start} onChange={(e) => onChange(e.target.value, end)} />
      </Field>
      <Field label={t("sales.to")} className="w-44">
        <Input type="date" value={end} onChange={(e) => onChange(start, e.target.value)} />
      </Field>
      <Button onClick={() => window.print()}>
        <Printer aria-hidden="true" />
        {t("receipt.print")}
      </Button>
    </div>
  );
}

function Rows({ rows, label }: { rows: ReportRow[]; label: string }) {
  const money = useMoney();
  return (
    <>
      <tr>
        <Th colSpan={2} className="bg-surface-2">
          {label}
        </Th>
      </tr>
      {rows.map((r) => (
        <tr key={r.account_id}>
          <Td>
            <span className="text-muted">{r.code}</span> {r.name}
          </Td>
          <Td className="text-right tabular-nums">{money(r.amount)}</Td>
        </tr>
      ))}
    </>
  );
}

function Reports() {
  const { t } = useTranslation();
  const workspace = useWorkspace();
  const money = useMoney();
  const today = todayIn(workspace.timezone);
  const [start, setStart] = useState(`${today.slice(0, 7)}-01`);
  const [end, setEnd] = useState(today);
  const [report, setReport] = useState<"pl" | "bs" | "tb">("pl");
  const pl = useQuery({ queryKey: ["books", "pl", start, end], queryFn: () => api<ProfitLoss>("/v1/accounting/profit-and-loss", { query: { from: start, to: end } }), enabled: report === "pl" });
  const bs = useQuery({ queryKey: ["books", "bs", end], queryFn: () => api<BalanceSheet>("/v1/accounting/balance-sheet", { query: { as_of: end } }), enabled: report === "bs" });
  const tb = useQuery({ queryKey: ["books", "tb", end], queryFn: () => api<TrialBalance>("/v1/accounting/trial-balance", { query: { as_of: end } }), enabled: report === "tb" });
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-2 print:hidden" role="group" aria-label={t("books.report")}>
        {(["pl", "bs", "tb"] as const).map((r) => (
          <Button key={r} size="sm" variant={report === r ? "primary" : "secondary"} aria-pressed={report === r} onClick={() => setReport(r)}>
            {t(`books.reports.${r}`)}
          </Button>
        ))}
      </div>
      <Period
        start={start}
        end={end}
        onChange={(s, e) => {
          setStart(s);
          setEnd(e);
        }}
      />
      <p className="hidden text-sm print:block">
        {workspace.name}: {t(`books.reports.${report}`)}, {report === "pl" ? `${formatDay(start)} – ${formatDay(end)}` : formatDay(end)}
      </p>
      <Card className="overflow-hidden">
        {report === "pl" && pl.data && (
          <Table label={t("books.reports.pl")}>
            <tbody>
              <Rows rows={pl.data.income} label={t("books.income")} />
              <tr>
                <Td className="font-semibold">{t("books.totalIncome")}</Td>
                <Td className="text-right font-semibold tabular-nums">{money(pl.data.total_income)}</Td>
              </tr>
              <Rows rows={pl.data.expenses} label={t("books.expenses")} />
              <tr>
                <Td className="font-semibold">{t("books.totalExpenses")}</Td>
                <Td className="text-right font-semibold tabular-nums">{money(pl.data.total_expenses)}</Td>
              </tr>
              <tr>
                <Td className="text-base font-bold">{pl.data.profit >= 0 ? t("books.profit") : t("books.loss")}</Td>
                <Td className="text-right text-base font-bold tabular-nums">{money(Math.abs(pl.data.profit))}</Td>
              </tr>
            </tbody>
          </Table>
        )}
        {report === "bs" && bs.data && (
          <Table label={t("books.reports.bs")}>
            <tbody>
              <Rows rows={bs.data.assets} label={t("books.assets")} />
              <tr>
                <Td className="font-semibold">{t("books.totalAssets")}</Td>
                <Td className="text-right font-semibold tabular-nums">{money(bs.data.total_assets)}</Td>
              </tr>
              <Rows rows={bs.data.liabilities} label={t("books.liabilities")} />
              <Rows rows={bs.data.equity} label={t("books.equity")} />
              <tr>
                <Td>{t("books.earnings")}</Td>
                <Td className="text-right tabular-nums">{money(bs.data.earnings)}</Td>
              </tr>
              <tr>
                <Td className="font-semibold">{t("books.totalLiabEquity")}</Td>
                <Td className="text-right font-semibold tabular-nums">{money(bs.data.total_liabilities + bs.data.total_equity)}</Td>
              </tr>
            </tbody>
          </Table>
        )}
        {report === "tb" && tb.data && (
          <Table label={t("books.reports.tb")}>
            <thead>
              <tr>
                <Th>{t("books.account")}</Th>
                <Th className="text-right">{t("books.debit")}</Th>
                <Th className="text-right">{t("books.credit")}</Th>
              </tr>
            </thead>
            <tbody>
              {tb.data.rows.map((r) => (
                <tr key={r.account_id}>
                  <Td>
                    <span className="text-muted">{r.code}</span> {r.name}
                  </Td>
                  <Td className="text-right tabular-nums">{r.debit ? money(r.debit) : ""}</Td>
                  <Td className="text-right tabular-nums">{r.credit ? money(r.credit) : ""}</Td>
                </tr>
              ))}
              <tr>
                <Td className="font-semibold">{t("books.total")}</Td>
                <Td className="text-right font-semibold tabular-nums">{money(tb.data.debit)}</Td>
                <Td className="text-right font-semibold tabular-nums">{money(tb.data.credit)}</Td>
              </tr>
            </tbody>
          </Table>
        )}
        {(pl.isPending && report === "pl") || (bs.isPending && report === "bs") || (tb.isPending && report === "tb") ? (
          <div className="p-6">
            <Spinner />
          </div>
        ) : null}
      </Card>
      {report === "bs" && bs.data && !bs.data.balanced && <p className="text-sm text-danger-text">{t("books.notBalanced")}</p>}
    </div>
  );
}

function NewEntry({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const workspace = useWorkspace();
  const money = useMoney();
  const queryClient = useQueryClient();
  const accounts = useAccounts();
  const [date, setDate] = useState(todayIn(workspace.timezone));
  const [memo, setMemo] = useState("");
  const [lines, setLines] = useState([
    { account_id: "", debit: "", credit: "" },
    { account_id: "", debit: "", credit: "" },
  ]);
  const set = (i: number, patch: Partial<(typeof lines)[number]>) => setLines((ls) => ls.map((l, j) => (j === i ? { ...l, ...patch } : l)));
  const debit = lines.reduce((n, l) => n + (toMinor(l.debit) ?? 0), 0);
  const credit = lines.reduce((n, l) => n + (toMinor(l.credit) ?? 0), 0);
  const ok = memo.trim() && debit > 0 && debit === credit && lines.every((l) => l.account_id && (!!toMinor(l.debit) !== !!toMinor(l.credit)));
  const save = useMutation({
    mutationFn: () =>
      api("/v1/accounting/entries", {
        method: "POST",
        body: { entry_date: date, memo, lines: lines.map((l) => ({ account_id: l.account_id, debit: toMinor(l.debit) ?? 0, credit: toMinor(l.credit) ?? 0 })) },
      }),
    onSuccess: () => {
      toast.success(t("common.saved"));
      void queryClient.invalidateQueries({ queryKey: ["books"] });
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={t("books.newEntry")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" disabled={!ok} loading={save.isPending} onClick={() => save.mutate()}>
              {t("books.post")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label={t("common.date")}>
              <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </Field>
            <Field label={t("books.memo")} className="sm:col-span-2">
              <Input value={memo} maxLength={300} onChange={(e) => setMemo(e.target.value)} />
            </Field>
          </div>
          {lines.map((l, i) => (
            <div key={i} className="grid grid-cols-[1fr_6rem_6rem_auto] items-end gap-2">
              <Field label={t("books.account")} hideLabel={i > 0}>
                <Select value={l.account_id} onChange={(e) => set(i, { account_id: e.target.value })}>
                  <option value="">–</option>
                  {(accounts.data ?? []).filter((a) => a.active).map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} {a.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label={t("books.debit")} hideLabel={i > 0}>
                <Input inputMode="decimal" value={l.debit} onChange={(e) => set(i, { debit: e.target.value, credit: "" })} />
              </Field>
              <Field label={t("books.credit")} hideLabel={i > 0}>
                <Input inputMode="decimal" value={l.credit} onChange={(e) => set(i, { credit: e.target.value, debit: "" })} />
              </Field>
              <Button variant="ghost" size="icon" aria-label={t("books.removeLine")} disabled={lines.length <= 2} onClick={() => setLines((ls) => ls.filter((_, j) => j !== i))}>
                <Trash2 aria-hidden="true" />
              </Button>
            </div>
          ))}
          <Button size="sm" className="self-start" onClick={() => setLines((ls) => [...ls, { account_id: "", debit: "", credit: "" }])}>
            <Plus aria-hidden="true" />
            {t("inventory.addLine")}
          </Button>
          <p className={`text-sm ${debit === credit ? "text-muted" : "text-danger-text"}`}>{t("books.totals", { debit: money(debit), credit: money(credit) })}</p>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Journal() {
  const { t } = useTranslation();
  const { can } = useSession();
  const money = useMoney();
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const entries = useQuery({ queryKey: ["books", "entries"], queryFn: () => api<JournalEntry[]>("/v1/accounting/entries") });
  const reverse = useMutation({
    mutationFn: (id: string) => api(`/v1/accounting/entries/${id}/reverse`, { method: "POST" }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["books"] }),
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <div className="flex flex-col gap-4">
      {can("accounting.manage") && (
        <Button variant="primary" className="self-start" onClick={() => setAdding(true)}>
          <Plus aria-hidden="true" />
          {t("books.newEntry")}
        </Button>
      )}
      {entries.isPending ? (
        <Spinner />
      ) : !entries.data?.length ? (
        <EmptyState icon={<BookOpen />} title={t("books.noEntries")} />
      ) : (
        <ul className="flex flex-col gap-2">
          {entries.data.map((e) => (
            <li key={e.id}>
              <Card className="flex flex-col gap-2 p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">#{e.number}</span>
                  <span className="text-muted">{formatDay(e.entry_date)}</span>
                  <span className="min-w-0 flex-1 truncate">{e.memo}</span>
                  {e.source_type && <Badge>{t(`books.sources.${e.source_type}`, { defaultValue: e.source_type })}</Badge>}
                  {e.reversed_by && <Badge tone="warn">{t("books.reversed")}</Badge>}
                  {can("accounting.manage") && !e.reversed_by && !e.source_type && (
                    <Button size="sm" variant="ghost" loading={reverse.isPending && reverse.variables === e.id} onClick={() => reverse.mutate(e.id)}>
                      <RotateCcw aria-hidden="true" />
                      {t("books.reverse")}
                    </Button>
                  )}
                </div>
                <table className="w-full text-xs">
                  <tbody>
                    {e.lines.map((l, i) => (
                      <tr key={i}>
                        <td className={l.credit ? "pl-6" : ""}>
                          {l.account_code} {l.account_name}
                        </td>
                        <td className="w-28 text-right tabular-nums">{l.debit ? money(l.debit) : ""}</td>
                        <td className="w-28 text-right tabular-nums">{l.credit ? money(l.credit) : ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            </li>
          ))}
        </ul>
      )}
      {adding && <NewEntry onClose={() => setAdding(false)} />}
    </div>
  );
}

function Accounts() {
  const { t } = useTranslation();
  const { can } = useSession();
  const workspace = useWorkspace();
  const money = useMoney();
  const queryClient = useQueryClient();
  const accounts = useAccounts();
  const [form, setForm] = useState<{ id: string | null; code: string; name: string; type: (typeof TYPES)[number]; active: boolean } | null>(null);
  const [ledgerOf, setLedgerOf] = useState<LedgerAccount | null>(null);
  const today = todayIn(workspace.timezone);
  const ledger = useQuery({
    queryKey: ["books", "ledger", ledgerOf?.id],
    queryFn: () => api<Ledger>(`/v1/accounting/ledger/${ledgerOf?.id}`, { query: { from: `${today.slice(0, 4)}-01-01`, to: today } }),
    enabled: !!ledgerOf,
  });
  const save = useMutation({
    mutationFn: () => {
      if (!form) throw new Error("no form");
      const body = { code: form.code.trim(), name: form.name.trim(), type: form.type, active: form.active };
      return form.id ? api(`/v1/accounting/accounts/${form.id}`, { method: "PUT", body }) : api("/v1/accounting/accounts", { method: "POST", body });
    },
    onSuccess: () => {
      setForm(null);
      void queryClient.invalidateQueries({ queryKey: ["books", "accounts"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <div className="flex flex-col gap-4">
      <p className="max-w-2xl text-sm text-muted">{t("books.chartIntro")}</p>
      {can("accounting.manage") && (
        <Button className="self-start" onClick={() => setForm({ id: null, code: "", name: "", type: "expense", active: true })}>
          <Plus aria-hidden="true" />
          {t("books.newAccount")}
        </Button>
      )}
      <Card className="overflow-hidden">
        <Table label={t("books.tabs.accounts")}>
          <thead>
            <tr>
              <Th>{t("books.code")}</Th>
              <Th>{t("common.name")}</Th>
              <Th className="hidden sm:table-cell">{t("books.type")}</Th>
              <Th className="w-24">
                <span className="sr-only">{t("common.edit")}</span>
              </Th>
            </tr>
          </thead>
          <tbody>
            {(accounts.data ?? []).map((a) => (
              <tr key={a.id} className={a.active ? "" : "opacity-60"}>
                <Td className="tabular-nums">{a.code}</Td>
                <Td>
                  <button type="button" className="underline-offset-4 hover:underline" onClick={() => setLedgerOf(a)}>
                    {a.name}
                  </button>
                  {a.role && <Badge className="ml-2">{t("books.automatic")}</Badge>}
                </Td>
                <Td className="hidden sm:table-cell">{t(`books.types.${a.type}`)}</Td>
                <Td>
                  {can("accounting.manage") && (
                    <Button size="sm" variant="ghost" onClick={() => setForm({ id: a.id, code: a.code, name: a.name, type: a.type, active: a.active })}>
                      {t("common.edit")}
                    </Button>
                  )}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>
      {form && (
        <Dialog open onOpenChange={(o) => !o && setForm(null)}>
          <DialogContent
            title={form.id ? t("books.editAccount") : t("books.newAccount")}
            closeLabel={t("common.close")}
            footer={
              <>
                <Button onClick={() => setForm(null)}>{t("common.cancel")}</Button>
                <Button variant="primary" disabled={!form.code.trim() || !form.name.trim()} loading={save.isPending} onClick={() => save.mutate()}>
                  {t("common.save")}
                </Button>
              </>
            }
          >
            <div className="flex flex-col gap-3">
              <div className="grid gap-3 sm:grid-cols-3">
                <Field label={t("books.code")}>
                  <Input value={form.code} maxLength={20} onChange={(e) => setForm({ ...form, code: e.target.value })} />
                </Field>
                <Field label={t("common.name")} className="sm:col-span-2">
                  <Input value={form.name} maxLength={120} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                </Field>
              </div>
              <Field label={t("books.type")}>
                <Select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value as (typeof TYPES)[number] })}>
                  {TYPES.map((ty) => (
                    <option key={ty} value={ty}>
                      {t(`books.types.${ty}`)}
                    </option>
                  ))}
                </Select>
              </Field>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })} />
                {t("sales.inUse")}
              </label>
            </div>
          </DialogContent>
        </Dialog>
      )}
      {ledgerOf && (
        <Dialog open onOpenChange={(o) => !o && setLedgerOf(null)}>
          <DialogContent title={`${ledgerOf.code} ${ledgerOf.name}`} closeLabel={t("common.close")}>
            {!ledger.data ? (
              <Spinner />
            ) : (
              <Table label={t("books.ledger")}>
                <thead>
                  <tr>
                    <Th>{t("common.date")}</Th>
                    <Th>{t("books.memo")}</Th>
                    <Th className="text-right">{t("customers.balance")}</Th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <Td colSpan={2} className="text-muted">
                      {t("books.opening")}
                    </Td>
                    <Td className="text-right tabular-nums">{money(ledger.data.opening)}</Td>
                  </tr>
                  {ledger.data.rows.map((r) => (
                    <tr key={`${r.entry_id}-${r.balance}`}>
                      <Td className="whitespace-nowrap tabular-nums">{formatDay(r.entry_date)}</Td>
                      <Td className="max-w-56 truncate">{r.memo}</Td>
                      <Td className="text-right tabular-nums">{money(r.balance)}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}

function CashBook() {
  const { t } = useTranslation();
  const workspace = useWorkspace();
  const money = useMoney();
  const today = todayIn(workspace.timezone);
  const [start, setStart] = useState(`${today.slice(0, 7)}-01`);
  const [end, setEnd] = useState(today);
  const book = useQuery({ queryKey: ["books", "cash", start, end], queryFn: () => api<Ledger>("/v1/accounting/cash-book", { query: { from: start, to: end } }) });
  return (
    <div className="flex flex-col gap-4">
      <Period
        start={start}
        end={end}
        onChange={(s, e) => {
          setStart(s);
          setEnd(e);
        }}
      />
      {!book.data ? (
        <Spinner />
      ) : (
        <Card className="overflow-hidden">
          <Table label={t("books.tabs.cash")}>
            <thead>
              <tr>
                <Th>{t("common.date")}</Th>
                <Th>{t("books.memo")}</Th>
                <Th className="text-right">{t("books.in")}</Th>
                <Th className="text-right">{t("books.out")}</Th>
                <Th className="text-right">{t("customers.balance")}</Th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <Td colSpan={4} className="text-muted">
                  {t("books.opening")}
                </Td>
                <Td className="text-right tabular-nums">{money(book.data.opening)}</Td>
              </tr>
              {book.data.rows.map((r, i) => (
                <tr key={`${r.entry_id}-${i}`}>
                  <Td className="whitespace-nowrap tabular-nums">{formatDay(r.entry_date)}</Td>
                  <Td className="max-w-64 truncate">{r.memo}</Td>
                  <Td className="text-right tabular-nums">{r.debit ? money(r.debit) : ""}</Td>
                  <Td className="text-right tabular-nums">{r.credit ? money(r.credit) : ""}</Td>
                  <Td className="text-right tabular-nums">{money(r.balance)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
    </div>
  );
}

interface BoxDraft {
  code: string;
  label: string;
  sources: { kind: "tax_amount" | "tax_base" | "account" | "boxes"; ids: string[]; side: "output" | "input"; sign: 1 | -1 }[];
}

function TemplateEditor({ template, onClose }: { template: TaxTemplate | null; onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const rates = useTaxRates();
  const accounts = useAccounts();
  const [name, setName] = useState(template?.name ?? "");
  const [boxes, setBoxes] = useState<BoxDraft[]>((template?.boxes as BoxDraft[] | undefined) ?? [{ code: "1", label: "", sources: [] }]);
  const setBox = (i: number, patch: Partial<BoxDraft>) => setBoxes((bs) => bs.map((b, j) => (j === i ? { ...b, ...patch } : b)));
  const save = useMutation({
    mutationFn: () => {
      const body = { name: name.trim(), boxes };
      return template ? api(`/v1/accounting/tax-returns/${template.id}`, { method: "PUT", body }) : api("/v1/accounting/tax-returns", { method: "POST", body });
    },
    onSuccess: () => {
      toast.success(t("common.saved"));
      void queryClient.invalidateQueries({ queryKey: ["books", "templates"] });
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const options = (kind: BoxDraft["sources"][number]["kind"], index: number) =>
    kind === "account"
      ? (accounts.data ?? []).map((a) => ({ value: a.id, label: `${a.code} ${a.name}` }))
      : kind === "boxes"
        ? boxes.slice(0, index).map((b) => ({ value: b.code, label: `${b.code} ${b.label}` }))
        : (rates.data ?? []).map((r) => ({ value: r.id, label: `${r.name} ${Number(r.percent)}%` }));
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={template ? t("books.editReturn") : t("books.newReturn")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" disabled={!name.trim() || boxes.some((b) => !b.code || !b.label)} loading={save.isPending} onClick={() => save.mutate()}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted">{t("books.returnIntro")}</p>
          <Field label={t("common.name")}>
            <Input value={name} maxLength={120} onChange={(e) => setName(e.target.value)} />
          </Field>
          {boxes.map((b, i) => (
            <Card key={i} className="flex flex-col gap-2 p-3">
              <div className="grid grid-cols-[5rem_1fr_auto] items-end gap-2">
                <Field label={t("books.box")}>
                  <Input value={b.code} maxLength={20} onChange={(e) => setBox(i, { code: e.target.value })} />
                </Field>
                <Field label={t("books.boxLabel")}>
                  <Input value={b.label} maxLength={200} onChange={(e) => setBox(i, { label: e.target.value })} />
                </Field>
                <Button variant="ghost" size="icon" aria-label={t("books.removeBox")} onClick={() => setBoxes((bs) => bs.filter((_, j) => j !== i))}>
                  <Trash2 aria-hidden="true" />
                </Button>
              </div>
              {b.sources.map((s, k) => (
                <div key={k} className="grid gap-2 sm:grid-cols-[1fr_1fr_5rem_auto] sm:items-end">
                  <Field label={t("books.from")}>
                    <Select
                      value={`${s.kind}:${s.side}`}
                      onChange={(e) => {
                        const [kind, side] = e.target.value.split(":") as [BoxDraft["sources"][number]["kind"], "output" | "input"];
                        setBox(i, { sources: b.sources.map((x, j) => (j === k ? { ...x, kind, side, ids: [] } : x)) });
                      }}
                    >
                      {["tax_base:output", "tax_amount:output", "tax_base:input", "tax_amount:input", "account:output", "boxes:output"].map((v) => (
                        <option key={v} value={v}>
                          {t(`books.sourceKinds.${v.replace(":", "_")}`)}
                        </option>
                      ))}
                    </Select>
                  </Field>
                  <Field label={t("books.which")}>
                    <Select value={s.ids[0] ?? ""} onChange={(e) => setBox(i, { sources: b.sources.map((x, j) => (j === k ? { ...x, ids: e.target.value ? [e.target.value] : [] } : x)) })}>
                      <option value="">–</option>
                      {options(s.kind, i).map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </Select>
                  </Field>
                  <Field label={t("books.sign")}>
                    <Select value={String(s.sign)} onChange={(e) => setBox(i, { sources: b.sources.map((x, j) => (j === k ? { ...x, sign: Number(e.target.value) as 1 | -1 } : x)) })}>
                      <option value="1">+</option>
                      <option value="-1">−</option>
                    </Select>
                  </Field>
                  <Button variant="ghost" size="icon" aria-label={t("books.removeSource")} onClick={() => setBox(i, { sources: b.sources.filter((_, j) => j !== k) })}>
                    <Trash2 aria-hidden="true" />
                  </Button>
                </div>
              ))}
              <Button size="sm" className="self-start" onClick={() => setBox(i, { sources: [...b.sources, { kind: "tax_base", ids: [], side: "output", sign: 1 }] })}>
                <Plus aria-hidden="true" />
                {t("books.addSource")}
              </Button>
            </Card>
          ))}
          <Button size="sm" className="self-start" onClick={() => setBoxes((bs) => [...bs, { code: String(bs.length + 1), label: "", sources: [] }])}>
            <Plus aria-hidden="true" />
            {t("books.addBox")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function TaxReturns() {
  const { t } = useTranslation();
  const { can } = useSession();
  const workspace = useWorkspace();
  const money = useMoney();
  const today = todayIn(workspace.timezone);
  const [start, setStart] = useState(`${today.slice(0, 7)}-01`);
  const [end, setEnd] = useState(today);
  const [editing, setEditing] = useState<TaxTemplate | null | "new">(null);
  const [chosen, setChosen] = useState("");
  const templates = useQuery({ queryKey: ["books", "templates"], queryFn: () => api<TaxTemplate[]>("/v1/accounting/tax-returns") });
  const filled = useQuery({
    queryKey: ["books", "return", chosen, start, end],
    queryFn: () => api<TaxReturn>(`/v1/accounting/tax-returns/${chosen}/fill`, { query: { from: start, to: end } }),
    enabled: !!chosen,
  });
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3 print:hidden">
        <Field label={t("books.returnTemplate")} className="w-64">
          <Select value={chosen} onChange={(e) => setChosen(e.target.value)}>
            <option value="">–</option>
            {(templates.data ?? []).map((tpl) => (
              <option key={tpl.id} value={tpl.id}>
                {tpl.name}
              </option>
            ))}
          </Select>
        </Field>
        {can("accounting.manage") && (
          <>
            <Button onClick={() => setEditing("new")}>
              <Plus aria-hidden="true" />
              {t("books.newReturn")}
            </Button>
            {chosen && (
              <Button onClick={() => setEditing((templates.data ?? []).find((x) => x.id === chosen) ?? null)}>
                {t("common.edit")}
              </Button>
            )}
          </>
        )}
      </div>
      {chosen && (
        <>
          <Period
            start={start}
            end={end}
            onChange={(s, e) => {
              setStart(s);
              setEnd(e);
            }}
          />
          {filled.data && (
            <Card className="overflow-hidden">
              <Table label={filled.data.name}>
                <caption className="px-4 pt-3 text-left text-sm font-semibold">
                  {filled.data.name}: {formatDay(filled.data.start)} – {formatDay(filled.data.end)}
                </caption>
                <tbody>
                  {filled.data.boxes.map((b) => (
                    <tr key={b.code}>
                      <Td className="w-16 tabular-nums">{b.code}</Td>
                      <Td>{b.label}</Td>
                      <Td className="text-right tabular-nums">{money(b.amount)}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Card>
          )}
        </>
      )}
      {!templates.data?.length && <EmptyState icon={<Calculator />} title={t("books.noReturns")}>{t("books.noReturnsHelp")}</EmptyState>}
      {editing && <TemplateEditor template={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function BooksSettingsForm() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["books", "settings"], queryFn: () => api<BooksSettings>("/v1/accounting/settings") });
  const accounts = useAccounts();
  const rates = useTaxRates();
  const categories = useExpenseCategories();
  const [draft, setDraft] = useState<BooksSettings | null>(null);
  const current = draft ?? settings.data;
  const save = useMutation({
    mutationFn: () => api<BooksSettings>("/v1/accounting/settings", { method: "PUT", body: { locked_until: current?.locked_until || null, tax_accounts: current?.tax_accounts ?? {}, expense_accounts: current?.expense_accounts ?? {} } }),
    onSuccess: () => {
      toast.success(t("common.saved"));
      setDraft(null);
      void queryClient.invalidateQueries({ queryKey: ["books"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const backfill = useMutation({
    mutationFn: () => api<{ entries: number }>("/v1/accounting/backfill", { method: "POST" }),
    onSuccess: (r) => {
      toast.success(t("books.backfilled", { count: r.entries }));
      void queryClient.invalidateQueries({ queryKey: ["books"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (!current) return <Spinner />;
  const accountOptions = (type: string) => (accounts.data ?? []).filter((a) => a.type === type && a.active);
  return (
    <div className="flex max-w-2xl flex-col gap-5">
      <Card className="flex flex-col gap-3 p-4">
        <Field label={t("books.lockedUntil")} help={t("books.lockedHelp")}>
          <Input type="date" value={current.locked_until ?? ""} onChange={(e) => setDraft({ ...current, locked_until: e.target.value || null })} />
        </Field>
      </Card>
      {(rates.data ?? []).length > 0 && (
        <Card className="flex flex-col gap-3 p-4">
          <p className="font-semibold">{t("books.taxAccounts")}</p>
          {(rates.data ?? []).map((r) => (
            <div key={r.id} className="grid gap-2 sm:grid-cols-[1fr_1fr_1fr] sm:items-end">
              <span className="text-sm">
                {r.name} {Number(r.percent)}%
              </span>
              {(["output", "input"] as const).map((side) => (
                <Field key={side} label={t(`books.${side}Tax`)}>
                  <Select
                    value={current.tax_accounts[r.id]?.[side] ?? ""}
                    onChange={(e) => setDraft({ ...current, tax_accounts: { ...current.tax_accounts, [r.id]: { ...(current.tax_accounts[r.id] ?? {}), [side]: e.target.value } } })}
                  >
                    <option value="">{t("books.defaultAccount")}</option>
                    {accountOptions(side === "output" ? "liability" : "asset").map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.code} {a.name}
                      </option>
                    ))}
                  </Select>
                </Field>
              ))}
            </div>
          ))}
        </Card>
      )}
      {(categories.data ?? []).length > 0 && (
        <Card className="flex flex-col gap-3 p-4">
          <p className="font-semibold">{t("books.expenseAccounts")}</p>
          {(categories.data ?? []).map((c) => (
            <div key={c.id} className="grid gap-2 sm:grid-cols-2 sm:items-center">
              <span className="text-sm">{c.name}</span>
              <Select
                aria-label={t("books.accountFor", { name: c.name })}
                value={current.expense_accounts[c.id] ?? ""}
                onChange={(e) => setDraft({ ...current, expense_accounts: { ...current.expense_accounts, [c.id]: e.target.value } })}
              >
                <option value="">{t("books.defaultAccount")}</option>
                {accountOptions("expense").map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code} {a.name}
                  </option>
                ))}
              </Select>
            </div>
          ))}
        </Card>
      )}
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" disabled={!draft} loading={save.isPending} onClick={() => save.mutate()}>
          {t("common.save")}
        </Button>
        <Button loading={backfill.isPending} onClick={() => backfill.mutate()}>
          {t("books.backfill")}
        </Button>
      </div>
    </div>
  );
}

export default function AccountingPage() {
  const { t } = useTranslation();
  const { can, hasModule } = useSession();
  const tabs = [
    { key: "reports", content: <Reports />, show: can("accounting.view") },
    { key: "journal", content: <Journal />, show: can("accounting.view") },
    { key: "cash", content: <CashBook />, show: can("accounting.view") },
    { key: "accounts", content: <Accounts />, show: can("accounting.view") },
    { key: "returns", content: <TaxReturns />, show: can("accounting.view") },
    { key: "settings", content: <BooksSettingsForm />, show: can("accounting.manage") },
  ].filter((x) => x.show);
  const [active, setActive] = useTab(tabs.map((x) => x.key));
  if (!hasModule("accounting") || !tabs.length) return <EmptyState icon={<BookOpen />} title={t("common.notAllowed")} />;
  return (
    <>
      <PageHeader title={t("books.title")} sub={t("books.sub")} />
      <Tabs value={active} onValueChange={setActive}>
        <TabsList className="mb-5 w-fit max-w-full overflow-x-auto print:hidden">
          {tabs.map((x) => (
            <TabsTrigger key={x.key} value={x.key}>
              {t(`books.tabs.${x.key}`)}
            </TabsTrigger>
          ))}
        </TabsList>
        {tabs.map((x) => (
          <TabsContent key={x.key} value={x.key}>
            {active === x.key && x.content}
          </TabsContent>
        ))}
      </Tabs>
    </>
  );
}
