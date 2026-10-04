"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CloudOff, Minus, PackagePlus, Plus, Printer, ShoppingBasket, Trash2, Wallet } from "lucide-react";
import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { DrawerSession, Product, Sale } from "@/api/types";
import { useSession, useWorkspace } from "@/auth/session";
import { PageHeader } from "@/components/page";
import { shopKeys, shownPrice, submitSale, useCustomers, useDrawer, useOfflineQueue, useProductCategories, useProducts, useShopSettings, useTaxRates } from "@/components/shop/data";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, EmptyState } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/cn";
import { errorMessage } from "@/lib/errors";
import { formatMoney, formatNumber } from "@/lib/format";
import { fromMinor, toMinor } from "@/lib/money";

interface CartLine {
  key: string;
  product?: Product;
  name: string;
  price: number;
  quantity: number;
}

function OpenDrawer() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [float, setFloat] = useState("");
  const open = useMutation({
    mutationFn: () => api<DrawerSession>("/v1/sales/drawer/open", { method: "POST", body: { opening_float: toMinor(float) ?? 0 } }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: shopKeys.drawer }),
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Card className="mx-auto flex max-w-md flex-col gap-4 p-5">
      <p className="font-display text-lg font-semibold">{t("pos.openTitle")}</p>
      <p className="text-sm text-muted">{t("pos.openHelp")}</p>
      <Field label={t("pos.float")}>
        <Input inputMode="decimal" value={float} onChange={(e) => setFloat(e.target.value)} placeholder="0" />
      </Field>
      <Button variant="primary" loading={open.isPending} disabled={toMinor(float) === null} onClick={() => open.mutate()}>
        <Wallet aria-hidden="true" />
        {t("pos.open")}
      </Button>
    </Card>
  );
}

function CloseDrawer({ drawer, onClose }: { drawer: DrawerSession; onClose: () => void }) {
  const { t } = useTranslation();
  const workspace = useWorkspace();
  const queryClient = useQueryClient();
  const [counted, setCounted] = useState("");
  const [result, setResult] = useState<DrawerSession | null>(null);
  const money = (n: number) => formatMoney(n, workspace.currency);
  const close = useMutation({
    mutationFn: () => api<DrawerSession>("/v1/sales/drawer/close", { method: "POST", body: { counted_cash: toMinor(counted) ?? 0 } }),
    onSuccess: (r) => {
      setResult(r);
      void queryClient.invalidateQueries({ queryKey: shopKeys.drawer });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={t("pos.closeTitle")}
        closeLabel={t("common.close")}
        footer={
          result ? (
            <Button variant="primary" onClick={onClose}>
              {t("common.done")}
            </Button>
          ) : (
            <>
              <Button onClick={onClose}>{t("common.cancel")}</Button>
              <Button variant="primary" loading={close.isPending} disabled={toMinor(counted) === null || !counted} onClick={() => close.mutate()}>
                {t("pos.close")}
              </Button>
            </>
          )
        }
      >
        {result ? (
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-muted">{t("pos.expected")}</dt>
            <dd className="text-right tabular-nums">{money(result.expected_cash)}</dd>
            <dt className="text-muted">{t("pos.counted")}</dt>
            <dd className="text-right tabular-nums">{money(result.counted_cash ?? 0)}</dd>
            <dt className="font-medium">{t("pos.difference")}</dt>
            <dd className={cn("text-right font-semibold tabular-nums", (result.difference ?? 0) < 0 && "text-danger-text")}>{money(result.difference ?? 0)}</dd>
          </dl>
        ) : (
          <div className="flex flex-col gap-3 text-sm">
            <p className="text-muted">{t("pos.closeHelp", { count: drawer.sales_count, formatted: formatNumber(drawer.sales_count) })}</p>
            <Field label={t("pos.countedCash")}>
              <Input inputMode="decimal" value={counted} onChange={(e) => setCounted(e.target.value)} autoFocus />
            </Field>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function CustomItem({ onAdd, onClose }: { onAdd: (name: string, price: number) => void; onClose: () => void }) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const amount = toMinor(price);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={t("pos.customItem")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" disabled={!name.trim() || !amount} onClick={() => amount && onAdd(name.trim(), amount)}>
              {t("pos.add")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <Field label={t("pos.itemName")}>
            <Input dir="auto" value={name} maxLength={120} onChange={(e) => setName(e.target.value)} autoFocus />
          </Field>
          <Field label={t("pos.price")}>
            <Input inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} />
          </Field>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function PosPage() {
  const { t } = useTranslation();
  const { can, hasModule } = useSession();
  const workspace = useWorkspace();
  const queryClient = useQueryClient();
  const allowed = hasModule("sales") && can("sales.sell");
  const drawer = useDrawer();
  const products = useProducts();
  const categories = useProductCategories();
  const settings = useShopSettings();
  const rates = useTaxRates();
  const credit = hasModule("customers") && can("customers.view");
  const [customerQ, setCustomerQ] = useState("");
  const customers = useCustomers(customerQ, false, credit);
  const [category, setCategory] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [cart, setCart] = useState<CartLine[]>([]);
  const [cash, setCash] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [last, setLast] = useState<{ sale: Sale | null; change: number } | null>(null);
  const [closing, setClosing] = useState(false);
  const [custom, setCustom] = useState(false);
  const synced = useCallback(() => void queryClient.invalidateQueries({ queryKey: ["shop"] }), [queryClient]);
  const pending = useOfflineQueue(synced);
  const money = (n: number) => formatMoney(n, workspace.currency);

  const shown = useMemo(() => {
    const list = (products.data ?? []).filter((p) => (!category || p.category_id === category) && (!q || p.name.toLowerCase().includes(q.toLowerCase()) || (p.code ?? "").toLowerCase() === q.toLowerCase()));
    return list.slice(0, 120);
  }, [products.data, category, q]);
  const total = cart.reduce((sum, l) => sum + Math.round(l.price * l.quantity), 0);
  const paid = toMinor(cash);
  const change = paid !== null && paid >= total ? paid - total : null;

  const add = (product: Product) => {
    const price = shownPrice(product, settings.data, rates.data);
    setCart((c) => {
      const found = c.find((l) => l.product?.id === product.id);
      if (found) return c.map((l) => (l === found ? { ...l, quantity: l.quantity + 1 } : l));
      return [...c, { key: product.id, product, name: product.name, price, quantity: 1 }];
    });
  };
  const step = (key: string, by: number) => setCart((c) => c.flatMap((l) => (l.key !== key ? [l] : l.quantity + by <= 0 ? [] : [{ ...l, quantity: Math.round((l.quantity + by) * 1000) / 1000 }])));
  const complete = useMutation({
    mutationFn: async () => {
      const body = {
        client_id: crypto.randomUUID(),
        lines: cart.map((l) => (l.product ? { product_id: l.product.id, quantity: String(l.quantity) } : { name: l.name, unit_price: l.price, quantity: String(l.quantity) })),
        customer_id: customerId || null,
        paid_cash: paid ?? 0,
        sold_at: new Date().toISOString(),
      };
      return { sale: await submitSale(body), change: Math.max(0, (paid ?? 0) - total) };
    },
    onSuccess: (r) => {
      setLast(r);
      setCart([]);
      setCash("");
      setCustomerId("");
      if (!r.sale) toast.message(t("pos.savedOffline"));
      void queryClient.invalidateQueries({ queryKey: shopKeys.drawer });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (!allowed) return <EmptyState icon={<ShoppingBasket />} title={t("common.notAllowed")} />;
  if (drawer.isPending) return <div className="grid place-items-center py-16"><Spinner /></div>;
  const canPay = cart.length > 0 && paid !== null && (customerId ? true : paid >= total) && !complete.isPending;

  return (
    <>
      <PageHeader
        title={t("pos.title")}
        actions={
          drawer.data ? (
            <div className="flex flex-wrap items-center gap-2">
              {pending > 0 && (
                <Badge tone="warn">
                  <CloudOff className="mr-1 inline size-3.5" aria-hidden="true" />
                  {t("pos.pending", { count: pending, formatted: formatNumber(pending) })}
                </Badge>
              )}
              <Button onClick={() => setClosing(true)}>
                <Wallet aria-hidden="true" />
                {t("pos.closeTitle")}
              </Button>
            </div>
          ) : undefined
        }
      />
      {!drawer.data ? (
        <OpenDrawer />
      ) : (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_24rem]">
          <section aria-label={t("pos.items")} className="flex min-w-0 flex-col gap-3">
            <div className="flex flex-wrap gap-2">
              <Input className="max-w-xs" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("pos.search")} aria-label={t("pos.search")} />
              <Button onClick={() => setCustom(true)}>
                <PackagePlus aria-hidden="true" />
                {t("pos.customItem")}
              </Button>
            </div>
            {(categories.data ?? []).length > 0 && (
              <div className="flex flex-wrap gap-2" role="group" aria-label={t("pos.categories")}>
                <Button size="sm" variant={category === null ? "primary" : "secondary"} aria-pressed={category === null} onClick={() => setCategory(null)}>
                  {t("pos.all")}
                </Button>
                {(categories.data ?? []).map((c) => (
                  <Button key={c.id} size="sm" variant={category === c.id ? "primary" : "secondary"} aria-pressed={category === c.id} onClick={() => setCategory(c.id)}>
                    {c.name}
                  </Button>
                ))}
              </div>
            )}
            {products.isPending ? (
              <Spinner />
            ) : !shown.length ? (
              <EmptyState icon={<ShoppingBasket />} title={t("pos.noItems")}>
                {can("sales.manage") ? (
                  <Link href="/app/sales?tab=products" className="underline">
                    {t("pos.addItems")}
                  </Link>
                ) : null}
              </EmptyState>
            ) : (
              <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-4">
                {shown.map((p) => (
                  <li key={p.id}>
                    <button
                      type="button"
                      onClick={() => add(p)}
                      className="flex h-24 w-full flex-col items-start justify-between rounded-xl border border-border bg-surface p-3 text-left transition-colors hover:border-accent active:scale-[0.98]"
                    >
                      <span className="line-clamp-2 text-sm font-medium">{p.name}</span>
                      <span className="text-sm tabular-nums text-muted">{money(shownPrice(p, settings.data, rates.data))}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <Card className="flex h-fit flex-col gap-4 p-4 lg:sticky lg:top-20" aria-label={t("pos.cart")}>
            {last && (
              <Alert tone="success" title={t("pos.done", { change: money(last.sale?.change ?? last.change) })}>
                {last.sale ? (
                  <Link href={`/app/sales/receipt?id=${last.sale.id}`} className={buttonVariants({ size: "sm" })}>
                    <Printer aria-hidden="true" />
                    {t("pos.printReceipt", { number: last.sale.number })}
                  </Link>
                ) : (
                  t("pos.savedOffline")
                )}
              </Alert>
            )}
            {cart.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted">{t("pos.empty")}</p>
            ) : (
              <ul className="flex flex-col divide-y divide-border">
                {cart.map((l) => (
                  <li key={l.key} className="flex items-center gap-2 py-2">
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{l.name}</span>
                      <span className="text-xs tabular-nums text-muted">{money(Math.round(l.price * l.quantity))}</span>
                    </span>
                    <Button variant="ghost" size="iconSm" aria-label={t("pos.less", { name: l.name })} onClick={() => step(l.key, -1)}>
                      {l.quantity <= 1 ? <Trash2 aria-hidden="true" /> : <Minus aria-hidden="true" />}
                    </Button>
                    <span className="w-8 text-center text-sm tabular-nums">{formatNumber(l.quantity)}</span>
                    <Button variant="ghost" size="iconSm" aria-label={t("pos.more", { name: l.name })} onClick={() => step(l.key, 1)}>
                      <Plus aria-hidden="true" />
                    </Button>
                  </li>
                ))}
              </ul>
            )}
            <div className="flex items-baseline justify-between border-t border-border pt-3">
              <span className="text-sm text-muted">{t("pos.total")}</span>
              <span className="font-display text-2xl font-semibold tabular-nums">{money(total)}</span>
            </div>
            {credit && (
              <Field label={t("pos.customer")} optional={t("common.optional")}>
                <div className="flex flex-col gap-2">
                  <Input value={customerQ} onChange={(e) => setCustomerQ(e.target.value)} placeholder={t("pos.findCustomer")} aria-label={t("pos.findCustomer")} />
                  <Select value={customerId} onChange={(e) => setCustomerId(e.target.value)} aria-label={t("pos.customer")}>
                    <option value="">{t("pos.walkIn")}</option>
                    {(customers.data ?? []).map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                        {c.balance > 0 ? ` (${t("pos.owes", { amount: money(c.balance) })})` : ""}
                      </option>
                    ))}
                  </Select>
                </div>
              </Field>
            )}
            <Field label={customerId ? t("pos.paidNow") : t("pos.cashGiven")}>
              <Input inputMode="decimal" value={cash} onChange={(e) => setCash(e.target.value)} placeholder={fromMinor(total)} />
            </Field>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={() => setCash(fromMinor(total))} disabled={!total}>
                {t("pos.exact")}
              </Button>
              {[50000, 100000, 50000 * 4].map((n) =>
                n > total ? (
                  <Button key={n} size="sm" onClick={() => setCash(fromMinor(n))}>
                    {money(n)}
                  </Button>
                ) : null,
              )}
            </div>
            {customerId && paid !== null && paid < total ? (
              <p className="text-sm">{t("pos.onAccount", { amount: money(total - paid) })}</p>
            ) : change !== null && cart.length > 0 ? (
              <p className="text-sm">
                {t("pos.change")}: <span className="font-semibold tabular-nums">{money(change)}</span>
              </p>
            ) : null}
            <Button variant="primary" size="lg" disabled={!canPay} loading={complete.isPending} onClick={() => complete.mutate()}>
              {t("pos.complete")}
            </Button>
            <p className="text-xs text-muted">{t("pos.estimate")}</p>
          </Card>
        </div>
      )}
      {closing && drawer.data && <CloseDrawer drawer={drawer.data} onClose={() => setClosing(false)} />}
      {custom && (
        <CustomItem
          onClose={() => setCustom(false)}
          onAdd={(name, price) => {
            setCart((c) => [...c, { key: crypto.randomUUID(), name, price, quantity: 1 }]);
            setCustom(false);
          }}
        />
      )}
    </>
  );
}
