"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ClipboardCheck, Package, PackagePlus, Plus, Settings2, Truck, Wallet } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import { useBranches } from "@/api/hooks";
import type { PurchaseRow, StockCount, StockRow, Supplier } from "@/api/types";
import { useSession, useWorkspace } from "@/auth/session";
import { PageHeader } from "@/components/page";
import { useProducts, useTaxRates } from "@/components/shop/data";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, EmptyState } from "@/components/ui/card";
import { Switch } from "@/components/ui/choice";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Table, Td, Th } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { errorMessage } from "@/lib/errors";
import { formatDay, formatMoney, formatNumber, normalizeDigits } from "@/lib/format";
import { toMinor } from "@/lib/money";
import { useTab } from "@/lib/use-tab";

const qty = (v: string) => normalizeDigits(v).trim();
const validQty = (v: string) => /^\d+(\.\d{1,3})?$/.test(qty(v)) && Number(qty(v)) > 0;

function useMoney() {
  const workspace = useWorkspace();
  return (n: number) => formatMoney(n, workspace.currency);
}

function BranchSelect({ value, onChange, label }: { value: string; onChange: (v: string) => void; label: string }) {
  const { t } = useTranslation();
  const branches = useBranches();
  if (!(branches.data ?? []).length) return null;
  return (
    <Field label={label}>
      <Select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{t("inventory.mainStore")}</option>
        {(branches.data ?? []).map((b) => (
          <option key={b.id} value={b.id}>
            {b.name}
          </option>
        ))}
      </Select>
    </Field>
  );
}

function ItemDialog({ row, onClose }: { row: StockRow | null; onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const products = useProducts(true);
  const [productId, setProductId] = useState(row?.product_id ?? "");
  const [mode, setMode] = useState<"settings" | "opening" | "adjust">(row ? "adjust" : "opening");
  const [quantity, setQuantity] = useState("");
  const [cost, setCost] = useState("");
  const [reason, setReason] = useState("");
  const [branch, setBranch] = useState("");
  const [reorder, setReorder] = useState(row?.reorder_level ? String(Number(row.reorder_level)) : "");
  const [track, setTrack] = useState(row?.track ?? true);
  const save = useMutation({
    mutationFn: () => {
      if (mode === "settings") return api(`/v1/inventory/items/${productId}`, { method: "PUT", body: { track, reorder_level: reorder ? qty(reorder) : null } });
      if (mode === "opening") return api("/v1/inventory/opening", { method: "POST", body: { product_id: productId, branch_id: branch || null, quantity: qty(quantity), unit_cost: String((toMinor(cost) ?? 0)) } });
      return api("/v1/inventory/adjustments", { method: "POST", body: { product_id: productId, branch_id: branch || null, quantity: qty(quantity), reason } });
    },
    onSuccess: () => {
      toast.success(t("common.saved"));
      void queryClient.invalidateQueries({ queryKey: ["inventory"] });
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const ok =
    !!productId &&
    (mode === "settings" ||
      (mode === "opening" && validQty(quantity) && toMinor(cost) !== null) ||
      (mode === "adjust" && /^-?\d+(\.\d{1,3})?$/.test(qty(quantity)) && Number(qty(quantity)) !== 0 && reason.trim()));
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={row ? row.name : t("inventory.startTracking")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" disabled={!ok} loading={save.isPending} onClick={() => save.mutate()}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          {!row && (
            <Field label={t("inventory.item")}>
              <Select value={productId} onChange={(e) => setProductId(e.target.value)}>
                <option value="">–</option>
                {(products.data ?? []).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </Select>
            </Field>
          )}
          <Field label={t("inventory.what")}>
            <Select value={mode} onChange={(e) => setMode(e.target.value as typeof mode)}>
              <option value="opening">{t("inventory.modes.opening")}</option>
              {row && <option value="adjust">{t("inventory.modes.adjust")}</option>}
              {row && <option value="settings">{t("inventory.modes.settings")}</option>}
            </Select>
          </Field>
          {mode === "settings" ? (
            <>
              <label className="flex items-center gap-2 text-sm">
                <Switch checked={track} onCheckedChange={setTrack} aria-label={t("inventory.track")} />
                {t("inventory.track")}
              </label>
              <Field label={t("inventory.reorderLevel")} help={t("inventory.reorderHelp")} optional={t("common.optional")}>
                <Input inputMode="decimal" value={reorder} onChange={(e) => setReorder(e.target.value)} />
              </Field>
            </>
          ) : (
            <>
              <BranchSelect value={branch} onChange={setBranch} label={t("inventory.branch")} />
              <Field label={mode === "adjust" ? t("inventory.change") : t("inventory.quantity")} help={mode === "adjust" ? t("inventory.changeHelp") : undefined}>
                <Input inputMode="decimal" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
              </Field>
              {mode === "opening" ? (
                <Field label={t("inventory.unitCost")}>
                  <Input inputMode="decimal" value={cost} onChange={(e) => setCost(e.target.value)} />
                </Field>
              ) : (
                <Field label={t("inventory.reason")}>
                  <Input value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)} />
                </Field>
              )}
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Stock() {
  const { t } = useTranslation();
  const { can } = useSession();
  const money = useMoney();
  const params = useSearchParams();
  const [low, setLow] = useState(params.get("low") === "1");
  const [editing, setEditing] = useState<StockRow | null | "new">(null);
  const stock = useQuery({ queryKey: ["inventory", "stock", low], queryFn: () => api<StockRow[]>("/v1/inventory/stock", { query: { low } }) });
  const total = (stock.data ?? []).reduce((n, s) => n + s.value, 0);
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm">
          <Switch checked={low} onCheckedChange={setLow} aria-label={t("inventory.onlyLow")} />
          {t("inventory.onlyLow")}
        </label>
        <span className="text-sm text-muted">{t("inventory.totalValue", { value: money(total) })}</span>
        {can("inventory.manage") && (
          <Button className="ml-auto" onClick={() => setEditing("new")}>
            <Plus aria-hidden="true" />
            {t("inventory.startTracking")}
          </Button>
        )}
      </div>
      {stock.isPending ? (
        <Spinner />
      ) : !stock.data?.length ? (
        <EmptyState icon={<Package />} title={t("inventory.none")}>
          {t("inventory.noneHelp")}
        </EmptyState>
      ) : (
        <Card className="overflow-hidden">
          <Table label={t("inventory.tabs.stock")}>
            <thead>
              <tr>
                <Th>{t("inventory.item")}</Th>
                <Th className="text-right">{t("inventory.onHand")}</Th>
                <Th className="hidden text-right sm:table-cell">{t("inventory.avgCost")}</Th>
                <Th className="text-right">{t("inventory.value")}</Th>
                <Th className="w-12">
                  <span className="sr-only">{t("common.edit")}</span>
                </Th>
              </tr>
            </thead>
            <tbody>
              {stock.data.map((s) => (
                <tr key={s.product_id}>
                  <Td>
                    {s.name}
                    {s.low && (
                      <Badge tone="warn" className="ml-2">
                        <AlertTriangle className="mr-1 inline size-3" aria-hidden="true" />
                        {t("inventory.low")}
                      </Badge>
                    )}
                  </Td>
                  <Td className="text-right tabular-nums">
                    {formatNumber(Number(s.quantity))} {s.unit}
                  </Td>
                  <Td className="hidden text-right tabular-nums sm:table-cell">{money(Math.round(Number(s.average_cost)))}</Td>
                  <Td className="text-right tabular-nums">{money(s.value)}</Td>
                  <Td>
                    {can("inventory.manage") && (
                      <Button variant="ghost" size="iconSm" aria-label={t("inventory.manageItem", { name: s.name })} onClick={() => setEditing(s)}>
                        <Settings2 aria-hidden="true" />
                      </Button>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
      {editing && <ItemDialog row={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

interface DraftLine {
  product_id: string;
  quantity: string;
  cost: string;
  tax_rate_id: string;
}

function ReceiveDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const products = useProducts(true);
  const rates = useTaxRates();
  const suppliers = useQuery({ queryKey: ["inventory", "suppliers"], queryFn: () => api<Supplier[]>("/v1/inventory/suppliers") });
  const [supplier, setSupplier] = useState("");
  const [branch, setBranch] = useState("");
  const [reference, setReference] = useState("");
  const [paid, setPaid] = useState("");
  const [paidFrom, setPaidFrom] = useState("drawer");
  const [lines, setLines] = useState<DraftLine[]>([{ product_id: "", quantity: "", cost: "", tax_rate_id: "" }]);
  const set = (i: number, patch: Partial<DraftLine>) => setLines((ls) => ls.map((l, j) => (j === i ? { ...l, ...patch } : l)));
  const ok = lines.every((l) => l.product_id && validQty(l.quantity) && toMinor(l.cost) !== null && l.cost) && toMinor(paid) !== null;
  const save = useMutation({
    mutationFn: () =>
      api<PurchaseRow>("/v1/inventory/purchases", {
        method: "POST",
        body: {
          supplier_id: supplier || null,
          branch_id: branch || null,
          reference: reference || null,
          paid: toMinor(paid) ?? 0,
          paid_from: paidFrom,
          lines: lines.map((l) => ({ product_id: l.product_id, quantity: qty(l.quantity), unit_cost: String(toMinor(l.cost) ?? 0), tax_rate_id: l.tax_rate_id || null })),
        },
      }),
    onSuccess: () => {
      toast.success(t("common.saved"));
      void queryClient.invalidateQueries({ queryKey: ["inventory"] });
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={t("inventory.receive")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" disabled={!ok} loading={save.isPending} onClick={() => save.mutate()}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("inventory.supplier")}>
              <Select value={supplier} onChange={(e) => setSupplier(e.target.value)}>
                <option value="">{t("inventory.noSupplier")}</option>
                {(suppliers.data ?? []).map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("inventory.reference")} optional={t("common.optional")}>
              <Input value={reference} maxLength={60} onChange={(e) => setReference(e.target.value)} />
            </Field>
          </div>
          <BranchSelect value={branch} onChange={setBranch} label={t("inventory.branch")} />
          {lines.map((l, i) => (
            <Card key={i} className="grid gap-2 p-3 sm:grid-cols-4">
              <Field label={t("inventory.item")} className="sm:col-span-4">
                <Select value={l.product_id} onChange={(e) => set(i, { product_id: e.target.value })}>
                  <option value="">–</option>
                  {(products.data ?? []).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label={t("inventory.quantity")}>
                <Input inputMode="decimal" value={l.quantity} onChange={(e) => set(i, { quantity: e.target.value })} />
              </Field>
              <Field label={t("inventory.unitCost")}>
                <Input inputMode="decimal" value={l.cost} onChange={(e) => set(i, { cost: e.target.value })} />
              </Field>
              <Field label={t("inventory.inputTax")} className="sm:col-span-2">
                <Select value={l.tax_rate_id} onChange={(e) => set(i, { tax_rate_id: e.target.value })}>
                  <option value="">{t("inventory.noTax")}</option>
                  {(rates.data ?? []).map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name} {formatNumber(Number(r.percent))}%
                    </option>
                  ))}
                </Select>
              </Field>
            </Card>
          ))}
          <Button size="sm" className="self-start" onClick={() => setLines((ls) => [...ls, { product_id: "", quantity: "", cost: "", tax_rate_id: "" }])}>
            <Plus aria-hidden="true" />
            {t("inventory.addLine")}
          </Button>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("inventory.paidNow")} help={supplier ? t("inventory.paidHelp") : t("inventory.paidAll")}>
              <Input inputMode="decimal" value={paid} onChange={(e) => setPaid(e.target.value)} />
            </Field>
            <Field label={t("expenses.paidFrom")}>
              <Select value={paidFrom} onChange={(e) => setPaidFrom(e.target.value)}>
                {["drawer", "petty_cash", "bank", "other"].map((p) => (
                  <option key={p} value={p}>
                    {t(`expenses.from.${p}`)}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Purchases() {
  const { t } = useTranslation();
  const { can } = useSession();
  const money = useMoney();
  const [receiving, setReceiving] = useState(false);
  const list = useQuery({ queryKey: ["inventory", "purchases"], queryFn: () => api<PurchaseRow[]>("/v1/inventory/purchases") });
  return (
    <div className="flex flex-col gap-4">
      {can("inventory.manage") && (
        <Button variant="primary" className="self-start" onClick={() => setReceiving(true)}>
          <Truck aria-hidden="true" />
          {t("inventory.receive")}
        </Button>
      )}
      {!list.data?.length ? (
        <EmptyState icon={<Truck />} title={t("inventory.noPurchases")} />
      ) : (
        <ul className="flex flex-col gap-2">
          {list.data.map((p) => (
            <li key={p.id}>
              <Card className="flex items-center gap-3 px-4 py-3">
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="font-medium">{p.supplier_name ?? t("inventory.noSupplier")}</span>
                  <span className="text-xs text-muted">{[formatDay(p.received_on), p.reference, t("inventory.lines", { count: p.lines.length })].filter(Boolean).join(" · ")}</span>
                </span>
                <span className="text-right tabular-nums">
                  {money(p.total)}
                  {p.total > p.paid && <span className="block text-xs text-muted">{t("inventory.owed", { amount: money(p.total - p.paid) })}</span>}
                </span>
              </Card>
            </li>
          ))}
        </ul>
      )}
      {receiving && <ReceiveDialog onClose={() => setReceiving(false)} />}
    </div>
  );
}

function Suppliers() {
  const { t } = useTranslation();
  const { can } = useSession();
  const money = useMoney();
  const queryClient = useQueryClient();
  const list = useQuery({ queryKey: ["inventory", "suppliers"], queryFn: () => api<Supplier[]>("/v1/inventory/suppliers") });
  const [name, setName] = useState("");
  const [paying, setPaying] = useState<Supplier | null>(null);
  const [amount, setAmount] = useState("");
  const [from, setFrom] = useState("bank");
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["inventory"] });
  const add = useMutation({
    mutationFn: () => api("/v1/inventory/suppliers", { method: "POST", body: { name: name.trim() } }),
    onSuccess: () => {
      setName("");
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const pay = useMutation({
    mutationFn: () => api(`/v1/inventory/suppliers/${paying?.id}/payments`, { method: "POST", body: { amount: toMinor(amount), paid_from: from } }),
    onSuccess: () => {
      setPaying(null);
      setAmount("");
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <div className="flex flex-col gap-4">
      {can("inventory.manage") && (
        <div className="flex flex-wrap items-end gap-2">
          <Field label={t("inventory.newSupplier")} className="w-64">
            <Input dir="auto" value={name} maxLength={200} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Button disabled={!name.trim()} loading={add.isPending} onClick={() => add.mutate()}>
            <Plus aria-hidden="true" />
            {t("pos.add")}
          </Button>
        </div>
      )}
      <ul className="flex flex-col gap-2">
        {(list.data ?? []).map((s) => (
          <li key={s.id}>
            <Card className="flex items-center gap-3 px-4 py-3">
              <span className="min-w-0 flex-1 font-medium">{s.name}</span>
              <span className="tabular-nums">{t("inventory.weOwe", { amount: money(s.balance) })}</span>
              {can("inventory.manage") && s.balance > 0 && (
                <Button size="sm" onClick={() => setPaying(s)}>
                  <Wallet aria-hidden="true" />
                  {t("inventory.pay")}
                </Button>
              )}
            </Card>
          </li>
        ))}
      </ul>
      {paying && (
        <Dialog open onOpenChange={(o) => !o && setPaying(null)}>
          <DialogContent
            title={t("inventory.payNamed", { name: paying.name })}
            closeLabel={t("common.close")}
            footer={
              <>
                <Button onClick={() => setPaying(null)}>{t("common.cancel")}</Button>
                <Button variant="primary" disabled={!toMinor(amount)} loading={pay.isPending} onClick={() => pay.mutate()}>
                  {t("common.save")}
                </Button>
              </>
            }
          >
            <div className="flex flex-col gap-3">
              <Field label={t("expenses.amount")}>
                <Input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
              </Field>
              <Field label={t("expenses.paidFrom")}>
                <Select value={from} onChange={(e) => setFrom(e.target.value)}>
                  {["bank", "drawer", "petty_cash", "other"].map((p) => (
                    <option key={p} value={p}>
                      {t(`expenses.from.${p}`)}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}

function Count() {
  const { t } = useTranslation();
  const money = useMoney();
  const queryClient = useQueryClient();
  const [branch, setBranch] = useState("");
  const stock = useQuery({ queryKey: ["inventory", "stock", false], queryFn: () => api<StockRow[]>("/v1/inventory/stock") });
  const [counted, setCounted] = useState<Record<string, string>>({});
  const [result, setResult] = useState<StockCount | null>(null);
  const save = useMutation({
    mutationFn: () =>
      api<StockCount>("/v1/inventory/counts", {
        method: "POST",
        body: { branch_id: branch || null, lines: Object.entries(counted).filter(([, v]) => v.trim() !== "").map(([product_id, v]) => ({ product_id, counted: qty(v) })) },
      }),
    onSuccess: (r) => {
      setResult(r);
      setCounted({});
      void queryClient.invalidateQueries({ queryKey: ["inventory"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const entered = Object.values(counted).filter((v) => v.trim() !== "");
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted">{t("inventory.countHelp")}</p>
      <BranchSelect value={branch} onChange={setBranch} label={t("inventory.branch")} />
      {result && <p className="text-sm">{t("inventory.countDone", { value: money(result.value) })}</p>}
      <Card className="overflow-hidden">
        <Table label={t("inventory.tabs.count")}>
          <thead>
            <tr>
              <Th>{t("inventory.item")}</Th>
              <Th className="text-right">{t("inventory.books")}</Th>
              <Th className="w-32">{t("inventory.counted")}</Th>
            </tr>
          </thead>
          <tbody>
            {(stock.data ?? []).map((s) => (
              <tr key={s.product_id}>
                <Td>{s.name}</Td>
                <Td className="text-right tabular-nums">{formatNumber(Number(branch ? (s.levels.find((l) => l.branch_id === branch)?.quantity ?? 0) : s.quantity))}</Td>
                <Td>
                  <Input inputMode="decimal" aria-label={t("inventory.countedFor", { name: s.name })} value={counted[s.product_id] ?? ""} onChange={(e) => setCounted((c) => ({ ...c, [s.product_id]: e.target.value }))} />
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>
      <Button variant="primary" className="self-start" disabled={!entered.length || !entered.every((v) => /^\d+(\.\d{1,3})?$/.test(qty(v)))} loading={save.isPending} onClick={() => save.mutate()}>
        <ClipboardCheck aria-hidden="true" />
        {t("inventory.saveCount")}
      </Button>
    </div>
  );
}

function InventoryView() {
  const { t } = useTranslation();
  const { can, hasModule } = useSession();
  const tabs = [
    { key: "stock", content: <Stock />, show: can("inventory.view") },
    { key: "purchases", content: <Purchases />, show: can("inventory.view") },
    { key: "suppliers", content: <Suppliers />, show: can("inventory.view") },
    { key: "count", content: <Count />, show: can("inventory.manage") },
  ].filter((x) => x.show);
  const [active, setActive] = useTab(tabs.map((x) => x.key));
  if (!hasModule("inventory") || !tabs.length) return <EmptyState icon={<PackagePlus />} title={t("common.notAllowed")} />;
  return (
    <>
      <PageHeader title={t("inventory.title")} sub={t("inventory.sub")} />
      <Tabs value={active} onValueChange={setActive}>
        <TabsList className="mb-5 w-fit max-w-full overflow-x-auto">
          {tabs.map((x) => (
            <TabsTrigger key={x.key} value={x.key}>
              {t(`inventory.tabs.${x.key}`)}
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

export default function InventoryPage() {
  return (
    <Suspense>
      <InventoryView />
    </Suspense>
  );
}
