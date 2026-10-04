"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, Pencil, Plus, Printer, Receipt as ReceiptIcon, RotateCcw, Store } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { DrawerSession, Product, Sale, SalesSummary, ShopSettings, TaxRate } from "@/api/types";
import { useSession, useWorkspace } from "@/auth/session";
import { PageHeader } from "@/components/page";
import { shopKeys, useProductCategories, useProducts, useShopSettings, useTaxRates } from "@/components/shop/data";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, EmptyState } from "@/components/ui/card";
import { Switch } from "@/components/ui/choice";
import { Dialog, DialogContent, SheetContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Table, Td, Th } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { errorMessage } from "@/lib/errors";
import { formatDateTime, formatDay, formatMoney, formatNumber, todayIn } from "@/lib/format";
import { fromMinor, toMinor } from "@/lib/money";
import { useTab } from "@/lib/use-tab";

function useMoney() {
  const workspace = useWorkspace();
  return (n: number) => formatMoney(n, workspace.currency);
}

function SaleSheet({ sale, onClose }: { sale: Sale; onClose: () => void }) {
  const { t } = useTranslation();
  const { can } = useSession();
  const workspace = useWorkspace();
  const money = useMoney();
  const queryClient = useQueryClient();
  const [returning, setReturning] = useState<Record<string, string>>({});
  const [toAccount, setToAccount] = useState(false);
  const [reason, setReason] = useState("");
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["shop"] });
  const back = useMutation({
    mutationFn: () =>
      api<Sale>(`/v1/sales/${sale.id}/returns`, {
        method: "POST",
        body: {
          client_id: crypto.randomUUID(),
          to_account: toAccount,
          lines: Object.entries(returning)
            .filter(([, q]) => Number(q) > 0)
            .map(([line_id, quantity]) => ({ line_id, quantity })),
        },
      }),
    onSuccess: () => {
      toast.success(t("sales.returned"));
      refresh();
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const voiding = useMutation({
    mutationFn: () => api<Sale>(`/v1/sales/${sale.id}/void`, { method: "POST", body: { reason } }),
    onSuccess: () => {
      toast.success(t("sales.voided"));
      refresh();
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const manage = can("sales.manage") && sale.status === "completed";
  return (
    <SheetContent title={t("sales.saleTitle", { number: sale.number })} closeLabel={t("common.close")}>
      <div className="flex flex-col gap-4 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={sale.status === "voided" ? "danger" : sale.kind === "return" ? "warn" : "success"}>{t(`sales.kinds.${sale.status === "voided" ? "voided" : sale.kind}`)}</Badge>
          <span className="text-muted">{formatDateTime(sale.sold_at, workspace.timezone)}</span>
          {sale.sold_by_name && <span className="text-muted">· {sale.sold_by_name}</span>}
          {sale.customer_name && <span className="text-muted">· {sale.customer_name}</span>}
        </div>
        <ul className="flex flex-col divide-y divide-border">
          {sale.lines.map((l) => (
            <li key={l.id} className="flex items-center gap-3 py-2">
              <span className="min-w-0 flex-1">
                {l.name}
                <span className="block text-xs text-muted">
                  {formatNumber(Number(l.quantity))} × {money(l.unit_price)}
                  {Number(l.returned) > 0 ? ` · ${t("sales.returnedQty", { qty: formatNumber(Number(l.returned)) })}` : ""}
                </span>
              </span>
              {manage && sale.kind === "sale" && Number(l.quantity) - Number(l.returned) > 0 && (
                <Input
                  className="w-20"
                  inputMode="decimal"
                  aria-label={t("sales.returnQty", { name: l.name })}
                  placeholder="0"
                  value={returning[l.id] ?? ""}
                  onChange={(e) => setReturning((r) => ({ ...r, [l.id]: e.target.value }))}
                />
              )}
              <span className="w-24 text-right tabular-nums">{money(l.total)}</span>
            </li>
          ))}
        </ul>
        <dl className="grid grid-cols-2 gap-1">
          <dt className="text-muted">{t("sales.tax")}</dt>
          <dd className="text-right tabular-nums">{money(sale.tax)}</dd>
          <dt className="font-semibold">{t("sales.total")}</dt>
          <dd className="text-right font-semibold tabular-nums">{money(sale.total)}</dd>
          {sale.on_account !== 0 && (
            <>
              <dt className="text-muted">{t("sales.onAccount")}</dt>
              <dd className="text-right tabular-nums">{money(sale.on_account)}</dd>
            </>
          )}
        </dl>
        {sale.void_reason && <p className="text-danger-text">{t("sales.voidReason", { reason: sale.void_reason })}</p>}
        <Link href={`/app/sales/receipt?id=${sale.id}`} className={buttonVariants({ className: "self-start" })}>
          <Printer aria-hidden="true" />
          {t("sales.receipt")}
        </Link>
        {manage && sale.kind === "sale" && Object.values(returning).some((q) => Number(q) > 0) && (
          <Card className="flex flex-col gap-3 p-3">
            {sale.customer_id && (
              <label className="flex items-center gap-2">
                <Switch checked={toAccount} onCheckedChange={setToAccount} aria-label={t("sales.toAccount")} />
                {t("sales.toAccount")}
              </label>
            )}
            <Button variant="primary" loading={back.isPending} onClick={() => back.mutate()}>
              <RotateCcw aria-hidden="true" />
              {t("sales.takeBack")}
            </Button>
          </Card>
        )}
        {manage && (
          <Card className="flex flex-col gap-2 p-3">
            <Field label={t("sales.voidWhy")}>
              <Textarea rows={2} value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)} />
            </Field>
            <Button variant="danger" className="self-start" disabled={!reason.trim()} loading={voiding.isPending} onClick={() => voiding.mutate()}>
              <Ban aria-hidden="true" />
              {t("sales.void")}
            </Button>
          </Card>
        )}
      </div>
    </SheetContent>
  );
}

function SalesList() {
  const { t } = useTranslation();
  const workspace = useWorkspace();
  const money = useMoney();
  const [day, setDay] = useState(todayIn(workspace.timezone));
  const [open, setOpen] = useState<Sale | null>(null);
  const sales = useQuery({ queryKey: shopKeys.sales(day), queryFn: () => api<Sale[]>("/v1/sales", { query: { day } }) });
  const done = (sales.data ?? []).filter((s) => s.status === "completed");
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <Field label={t("sales.day")} className="w-48">
          <Input type="date" value={day} onChange={(e) => setDay(e.target.value)} />
        </Field>
        <p className="text-sm text-muted">{t("sales.dayTotal", { count: done.filter((s) => s.kind === "sale").length, total: money(done.reduce((n, s) => n + s.total, 0)) })}</p>
      </div>
      {sales.isPending ? (
        <Spinner />
      ) : !sales.data?.length ? (
        <EmptyState icon={<ReceiptIcon />} title={t("sales.none")} />
      ) : (
        <Card className="overflow-hidden">
          <Table label={t("sales.tabs.sales")}>
            <thead>
              <tr>
                <Th>#</Th>
                <Th>{t("sales.time")}</Th>
                <Th className="hidden sm:table-cell">{t("sales.by")}</Th>
                <Th className="text-right">{t("sales.total")}</Th>
              </tr>
            </thead>
            <tbody>
              {sales.data.map((s) => (
                <tr key={s.id} className="cursor-pointer hover:bg-surface-2" onClick={() => setOpen(s)}>
                  <Td>
                    <button type="button" className="font-medium underline-offset-4 hover:underline" onClick={() => setOpen(s)}>
                      {s.number}
                    </button>
                    {s.kind === "return" && <Badge tone="warn" className="ml-2">{t("sales.kinds.return")}</Badge>}
                    {s.status === "voided" && <Badge tone="danger" className="ml-2">{t("sales.kinds.voided")}</Badge>}
                  </Td>
                  <Td className="tabular-nums">{formatDateTime(s.sold_at, workspace.timezone)}</Td>
                  <Td className="hidden sm:table-cell">{s.sold_by_name}</Td>
                  <Td className="text-right tabular-nums">{money(s.total)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
      <Dialog open={!!open} onOpenChange={(o) => !o && setOpen(null)}>
        {open && <SaleSheet sale={open} onClose={() => setOpen(null)} />}
      </Dialog>
    </div>
  );
}

function Summary() {
  const { t } = useTranslation();
  const workspace = useWorkspace();
  const money = useMoney();
  const today = todayIn(workspace.timezone);
  const [start, setStart] = useState(`${today.slice(0, 7)}-01`);
  const [end, setEnd] = useState(today);
  const data = useQuery({ queryKey: ["shop", "summary", start, end], queryFn: () => api<SalesSummary>("/v1/sales/summary", { query: { from: start, to: end } }) });
  const s = data.data;
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3 print:hidden">
        <Field label={t("sales.from")} className="w-44">
          <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </Field>
        <Field label={t("sales.to")} className="w-44">
          <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </Field>
        <Button onClick={() => window.print()}>
          <Printer aria-hidden="true" />
          {t("receipt.print")}
        </Button>
      </div>
      {!s ? (
        <Spinner />
      ) : (
        <>
          <p className="hidden text-sm print:block">
            {workspace.name}: {formatDay(s.start)} – {formatDay(s.end)}
          </p>
          <div className="grid gap-3 sm:grid-cols-4">
            {(
              [
                ["sales", formatNumber(s.count)],
                ["total", money(s.total)],
                ["cash", money(s.cash)],
                ["credit", money(s.on_account)],
              ] as const
            ).map(([k, v]) => (
              <Card key={k} className="p-4">
                <p className="text-xs text-muted">{t(`sales.figures.${k}`)}</p>
                <p className="font-display text-xl font-semibold tabular-nums">{v}</p>
              </Card>
            ))}
          </div>
          <Card className="overflow-hidden">
            <Table label={t("sales.taxTable")}>
              <caption className="px-4 pt-3 text-left text-sm font-semibold">{t("sales.taxTable")}</caption>
              <thead>
                <tr>
                  <Th>{t("sales.taxName")}</Th>
                  <Th>{t("sales.code")}</Th>
                  <Th className="text-right">{t("sales.rate")}</Th>
                  <Th className="text-right">{t("sales.taxable")}</Th>
                  <Th className="text-right">{t("sales.tax")}</Th>
                </tr>
              </thead>
              <tbody>
                {s.taxes.map((x) => (
                  <tr key={x.id}>
                    <Td>{x.name}</Td>
                    <Td>{x.code ?? "–"}</Td>
                    <Td className="text-right tabular-nums">{formatNumber(Number(x.percent))}%</Td>
                    <Td className="text-right tabular-nums">{money(x.taxable)}</Td>
                    <Td className="text-right tabular-nums">{money(x.amount)}</Td>
                  </tr>
                ))}
                {!s.taxes.length && (
                  <tr>
                    <Td colSpan={5} className="text-muted">
                      {t("sales.noTax")}
                    </Td>
                  </tr>
                )}
              </tbody>
            </Table>
          </Card>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="overflow-hidden">
              <Table label={t("sales.bestSellers")}>
                <caption className="px-4 pt-3 text-left text-sm font-semibold">{t("sales.bestSellers")}</caption>
                <tbody>
                  {s.products.map((p) => (
                    <tr key={p.name}>
                      <Td>{p.name}</Td>
                      <Td className="text-right tabular-nums">{formatNumber(Number(p.quantity))}</Td>
                      <Td className="text-right tabular-nums">{money(p.total)}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Card>
            <Card className="overflow-hidden">
              <Table label={t("sales.bySeller")}>
                <caption className="px-4 pt-3 text-left text-sm font-semibold">{t("sales.bySeller")}</caption>
                <tbody>
                  {s.sellers.map((p) => (
                    <tr key={p.name}>
                      <Td>{p.name}</Td>
                      <Td className="text-right tabular-nums">{formatNumber(p.count)}</Td>
                      <Td className="text-right tabular-nums">{money(p.total)}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Card>
          </div>
          {s.returns > 0 && <p className="text-sm text-muted">{t("sales.returnsTotal", { amount: money(s.returns) })}</p>}
        </>
      )}
    </div>
  );
}

function ProductDialog({ product, onClose }: { product: Product | null; onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const categories = useProductCategories();
  const rates = useTaxRates();
  const [name, setName] = useState(product?.name ?? "");
  const [code, setCode] = useState(product?.code ?? "");
  const [price, setPrice] = useState(fromMinor(product?.price));
  const [category, setCategory] = useState(product?.category_id ?? "");
  const [unit, setUnit] = useState(product?.unit ?? "pcs");
  const [taxes, setTaxes] = useState<string[] | null>(product ? product.tax_rate_ids : null);
  const [favorite, setFavorite] = useState(product?.favorite ?? false);
  const [active, setActive] = useState(product?.active ?? true);
  const amount = toMinor(price);
  const save = useMutation({
    mutationFn: () => {
      const body = { name: name.trim(), code: code.trim() || null, price: amount ?? 0, category_id: category || null, unit, tax_rate_ids: taxes, favorite, active };
      return product ? api<Product>(`/v1/sales/products/${product.id}`, { method: "PATCH", body }) : api<Product>("/v1/sales/products", { method: "POST", body });
    },
    onSuccess: () => {
      toast.success(t("common.saved"));
      void queryClient.invalidateQueries({ queryKey: shopKeys.products });
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const chosen = taxes ?? (rates.data ?? []).filter((r) => r.default && r.active).map((r) => r.id);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={product ? t("sales.editProduct") : t("sales.newProduct")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" loading={save.isPending} disabled={!name.trim() || amount === null} onClick={() => save.mutate()}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <Field label={t("sales.productName")}>
            <Input dir="auto" value={name} maxLength={200} onChange={(e) => setName(e.target.value)} />
          </Field>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label={t("sales.price")}>
              <Input inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} />
            </Field>
            <Field label={t("sales.unit")}>
              <Input value={unit} maxLength={10} onChange={(e) => setUnit(e.target.value)} />
            </Field>
            <Field label={t("sales.code")} optional={t("common.optional")}>
              <Input value={code} maxLength={40} onChange={(e) => setCode(e.target.value)} />
            </Field>
          </div>
          <Field label={t("sales.category")}>
            <Select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">–</option>
              {(categories.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </Field>
          <fieldset className="flex flex-col gap-1">
            <legend className="mb-1 text-sm font-medium">{t("sales.taxes")}</legend>
            {(rates.data ?? []).filter((r) => r.active).map((r) => (
              <label key={r.id} className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={chosen.includes(r.id)} onChange={(e) => setTaxes(e.target.checked ? [...chosen, r.id] : chosen.filter((x) => x !== r.id))} />
                {r.name} ({formatNumber(Number(r.percent))}%{r.compound ? `, ${t("sales.compound")}` : ""})
              </label>
            ))}
            {!(rates.data ?? []).length && <p className="text-xs text-muted">{t("sales.noRates")}</p>}
          </fieldset>
          <label className="flex items-center gap-2 text-sm">
            <Switch checked={favorite} onCheckedChange={setFavorite} aria-label={t("sales.favorite")} />
            {t("sales.favorite")}
          </label>
          <label className="flex items-center gap-2 text-sm">
            <Switch checked={active} onCheckedChange={setActive} aria-label={t("sales.forSale")} />
            {t("sales.forSale")}
          </label>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Products() {
  const { t } = useTranslation();
  const money = useMoney();
  const products = useProducts(true);
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Product | null | "new">(null);
  const [category, setCategory] = useState("");
  const addCategory = useMutation({
    mutationFn: () => api("/v1/sales/categories", { method: "POST", body: { name: category.trim() } }),
    onSuccess: () => {
      setCategory("");
      void queryClient.invalidateQueries({ queryKey: shopKeys.categories });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-2">
        <Button variant="primary" onClick={() => setEditing("new")}>
          <Plus aria-hidden="true" />
          {t("sales.newProduct")}
        </Button>
        <Field label={t("sales.newCategory")} className="w-56">
          <Input value={category} maxLength={80} onChange={(e) => setCategory(e.target.value)} />
        </Field>
        <Button disabled={!category.trim()} loading={addCategory.isPending} onClick={() => addCategory.mutate()}>
          {t("sales.addCategory")}
        </Button>
      </div>
      <Card className="overflow-hidden">
        <Table label={t("sales.tabs.products")}>
          <thead>
            <tr>
              <Th>{t("sales.productName")}</Th>
              <Th className="text-right">{t("sales.price")}</Th>
              <Th className="w-12">
                <span className="sr-only">{t("common.edit")}</span>
              </Th>
            </tr>
          </thead>
          <tbody>
            {(products.data ?? []).map((p) => (
              <tr key={p.id}>
                <Td>
                  {p.name}
                  {!p.active && <Badge className="ml-2">{t("sales.notForSale")}</Badge>}
                </Td>
                <Td className="text-right tabular-nums">{money(p.price)}</Td>
                <Td>
                  <Button variant="ghost" size="iconSm" aria-label={t("sales.editNamed", { name: p.name })} onClick={() => setEditing(p)}>
                    <Pencil aria-hidden="true" />
                  </Button>
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>
      {editing && <ProductDialog product={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function RateDialog({ rate, onClose }: { rate: TaxRate | null; onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    name: rate?.name ?? "",
    code: rate?.code ?? "",
    percent: rate ? String(Number(rate.percent)) : "",
    compound: rate?.compound ?? false,
    position: rate?.position ?? 0,
    active: rate?.active ?? true,
    default: rate?.default ?? false,
  });
  const valid = form.name.trim() && /^\d{1,3}(\.\d{1,4})?$/.test(form.percent) && Number(form.percent) <= 100;
  const save = useMutation({
    mutationFn: () => {
      const body = { ...form, name: form.name.trim(), code: form.code.trim() || null };
      return rate ? api<TaxRate>(`/v1/sales/tax-rates/${rate.id}`, { method: "PUT", body }) : api<TaxRate>("/v1/sales/tax-rates", { method: "POST", body });
    },
    onSuccess: () => {
      toast.success(t("common.saved"));
      void queryClient.invalidateQueries({ queryKey: shopKeys.taxes });
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={rate ? t("sales.editRate") : t("sales.newRate")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" disabled={!valid} loading={save.isPending} onClick={() => save.mutate()}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label={t("sales.taxName")} className="sm:col-span-2">
              <Input value={form.name} maxLength={60} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Field>
            <Field label={t("sales.code")} optional={t("common.optional")}>
              <Input value={form.code} maxLength={20} onChange={(e) => setForm({ ...form, code: e.target.value })} />
            </Field>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("sales.percent")}>
              <Input inputMode="decimal" value={form.percent} onChange={(e) => setForm({ ...form, percent: e.target.value })} />
            </Field>
            <Field label={t("sales.order")} help={t("sales.orderHelp")}>
              <Input type="number" min={0} max={1000} value={form.position} onChange={(e) => setForm({ ...form, position: Number(e.target.value) })} />
            </Field>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <Switch checked={form.compound} onCheckedChange={(v) => setForm({ ...form, compound: v })} aria-label={t("sales.compound")} />
            {t("sales.compoundHelp")}
          </label>
          <label className="flex items-center gap-2 text-sm">
            <Switch checked={form.default} onCheckedChange={(v) => setForm({ ...form, default: v })} aria-label={t("sales.defaultRate")} />
            {t("sales.defaultRate")}
          </label>
          <label className="flex items-center gap-2 text-sm">
            <Switch checked={form.active} onCheckedChange={(v) => setForm({ ...form, active: v })} aria-label={t("sales.inUse")} />
            {t("sales.inUse")}
          </label>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function SettingsForm({ current }: { current: ShopSettings }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ ...current, cash_rounding: String(current.cash_rounding) });
  const save = useMutation({
    mutationFn: () =>
      api<ShopSettings>("/v1/sales/settings", {
        method: "PUT",
        body: {
          prices_include_tax: form.prices_include_tax,
          cash_rounding: Number(form.cash_rounding) || 1,
          tax_id_label: form.tax_id_label || null,
          tax_id: form.tax_id || null,
          receipt_header: form.receipt_header || null,
          receipt_footer: form.receipt_footer || null,
        },
      }),
    onSuccess: () => {
      toast.success(t("common.saved"));
      void queryClient.invalidateQueries({ queryKey: shopKeys.settings });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Card className="flex max-w-2xl flex-col gap-3 p-5">
      <p className="font-semibold">{t("sales.receiptSettings")}</p>
      <label className="flex items-center gap-2 text-sm">
        <Switch checked={form.prices_include_tax} onCheckedChange={(v) => setForm({ ...form, prices_include_tax: v })} aria-label={t("sales.pricesInclude")} />
        {t("sales.pricesInclude")}
      </label>
      <Field label={t("sales.cashRounding")} help={t("sales.cashRoundingHelp")}>
        <Select value={form.cash_rounding} onChange={(e) => setForm({ ...form, cash_rounding: e.target.value })}>
          {["1", "50", "100", "500", "1000"].map((v) => (
            <option key={v} value={v}>
              {t(`sales.rounding.${v}`)}
            </option>
          ))}
        </Select>
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("sales.taxIdLabel")} help={t("sales.taxIdLabelHelp")}>
          <Input value={form.tax_id_label ?? ""} maxLength={40} onChange={(e) => setForm({ ...form, tax_id_label: e.target.value })} />
        </Field>
        <Field label={t("sales.taxId")}>
          <Input value={form.tax_id ?? ""} maxLength={60} onChange={(e) => setForm({ ...form, tax_id: e.target.value })} />
        </Field>
      </div>
      <Field label={t("sales.header")}>
        <Textarea dir="auto" rows={2} maxLength={1000} value={form.receipt_header ?? ""} onChange={(e) => setForm({ ...form, receipt_header: e.target.value })} />
      </Field>
      <Field label={t("sales.footer")}>
        <Textarea dir="auto" rows={2} maxLength={1000} value={form.receipt_footer ?? ""} onChange={(e) => setForm({ ...form, receipt_footer: e.target.value })} />
      </Field>
      <Button variant="primary" className="self-start" loading={save.isPending} onClick={() => save.mutate()}>
        {t("common.save")}
      </Button>
    </Card>
  );
}

function Taxes() {
  const { t } = useTranslation();
  const rates = useTaxRates();
  const settings = useShopSettings();
  const [editing, setEditing] = useState<TaxRate | null | "new">(null);
  return (
    <div className="flex flex-col gap-5">
      <p className="max-w-2xl text-sm text-muted">{t("sales.taxIntro")}</p>
      <div className="flex flex-col gap-2">
        {(rates.data ?? []).map((r) => (
          <Card key={r.id} className="flex items-center gap-3 px-4 py-3">
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="font-medium">
                {r.name} {r.code ? <span className="text-muted">({r.code})</span> : null}
              </span>
              <span className="text-xs text-muted">
                {formatNumber(Number(r.percent))}%{r.compound ? ` · ${t("sales.compound")}` : ""}
                {r.default ? ` · ${t("sales.defaultShort")}` : ""}
                {!r.active ? ` · ${t("sales.notInUse")}` : ""}
              </span>
            </span>
            <Button variant="ghost" size="iconSm" aria-label={t("sales.editNamed", { name: r.name })} onClick={() => setEditing(r)}>
              <Pencil aria-hidden="true" />
            </Button>
          </Card>
        ))}
        <Button className="self-start" onClick={() => setEditing("new")}>
          <Plus aria-hidden="true" />
          {t("sales.newRate")}
        </Button>
      </div>
      {settings.data && <SettingsForm key={settings.data.version} current={settings.data} />}
      {editing && <RateDialog rate={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function Drawers() {
  const { t } = useTranslation();
  const workspace = useWorkspace();
  const money = useMoney();
  const drawers = useQuery({ queryKey: ["shop", "drawers"], queryFn: () => api<DrawerSession[]>("/v1/sales/drawers") });
  return (
    <Card className="overflow-hidden">
      <Table label={t("sales.tabs.drawers")}>
        <thead>
          <tr>
            <Th>{t("sales.opened")}</Th>
            <Th className="hidden sm:table-cell">{t("sales.by")}</Th>
            <Th className="text-right">{t("pos.expected")}</Th>
            <Th className="text-right">{t("pos.counted")}</Th>
            <Th className="text-right">{t("pos.difference")}</Th>
          </tr>
        </thead>
        <tbody>
          {(drawers.data ?? []).map((d) => (
            <tr key={d.id}>
              <Td className="tabular-nums">
                {formatDateTime(d.opened_at, workspace.timezone)}
                {!d.closed_at && <Badge tone="accent" className="ml-2">{t("sales.openNow")}</Badge>}
              </Td>
              <Td className="hidden sm:table-cell">{d.opened_by_name}</Td>
              <Td className="text-right tabular-nums">{money(d.expected_cash)}</Td>
              <Td className="text-right tabular-nums">{d.counted_cash === null ? "–" : money(d.counted_cash)}</Td>
              <Td className={`text-right tabular-nums ${(d.difference ?? 0) < 0 ? "text-danger-text" : ""}`}>{d.difference === null ? "–" : money(d.difference)}</Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </Card>
  );
}

export default function SalesPage() {
  const { t } = useTranslation();
  const { can, hasModule } = useSession();
  const tabs = [
    { key: "sales", content: <SalesList />, show: can("sales.sell") },
    { key: "summary", content: <Summary />, show: can("sales.view") },
    { key: "products", content: <Products />, show: can("sales.manage") },
    { key: "taxes", content: <Taxes />, show: can("sales.manage") },
    { key: "drawers", content: <Drawers />, show: can("sales.view") },
  ].filter((x) => x.show);
  const [active, setActive] = useTab(tabs.map((x) => x.key));
  if (!hasModule("sales") || !tabs.length) return <EmptyState icon={<Store />} title={t("common.notAllowed")} />;
  return (
    <>
      <PageHeader title={t("sales.title")} actions={can("sales.sell") ? <Link href="/app/pos" className={buttonVariants({ variant: "primary" })}>{t("sales.openTill")}</Link> : undefined} />
      <Tabs value={active} onValueChange={setActive}>
        <TabsList className="mb-5 w-fit max-w-full overflow-x-auto print:hidden">
          {tabs.map((x) => (
            <TabsTrigger key={x.key} value={x.key}>
              {t(`sales.tabs.${x.key}`)}
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
