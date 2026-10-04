"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/api/client";
import type { Customer, DrawerSession, ExpenseCategory, Product, ProductCategory, Sale, ShopSettings, TaxRate } from "@/api/types";

export const shopKeys = {
  products: ["shop", "products"] as const,
  categories: ["shop", "categories"] as const,
  taxes: ["shop", "taxes"] as const,
  settings: ["shop", "settings"] as const,
  drawer: ["shop", "drawer"] as const,
  sales: (day: string) => ["shop", "sales", day] as const,
  customers: (q: string, owing: boolean) => ["customers", q, owing] as const,
  expenseCategories: ["expenses", "categories"] as const,
};

export function useProducts(includeInactive = false) {
  return useQuery({
    queryKey: [...shopKeys.products, includeInactive],
    queryFn: () => api<Product[]>("/v1/sales/products", { query: { include_inactive: includeInactive } }),
    staleTime: 60_000,
  });
}

export function useProductCategories() {
  return useQuery({ queryKey: shopKeys.categories, queryFn: () => api<ProductCategory[]>("/v1/sales/categories"), staleTime: 60_000 });
}

export function useTaxRates() {
  return useQuery({ queryKey: shopKeys.taxes, queryFn: () => api<TaxRate[]>("/v1/sales/tax-rates"), staleTime: 60_000 });
}

export function useShopSettings() {
  return useQuery({ queryKey: shopKeys.settings, queryFn: () => api<ShopSettings>("/v1/sales/settings"), staleTime: 60_000 });
}

export function useDrawer() {
  return useQuery({ queryKey: shopKeys.drawer, queryFn: () => api<DrawerSession | null>("/v1/sales/drawer") });
}

export function useCustomers(q = "", owing = false, enabled = true) {
  return useQuery({
    queryKey: shopKeys.customers(q, owing),
    queryFn: () => api<Customer[]>("/v1/customers", { query: { q: q || undefined, owing } }),
    enabled,
  });
}

export function useExpenseCategories() {
  return useQuery({ queryKey: shopKeys.expenseCategories, queryFn: () => api<ExpenseCategory[]>("/v1/expenses/categories"), staleTime: 300_000 });
}

/** Today's tax-inclusive price shown on a button, from the catalogue price. */
export function shownPrice(product: Product, settings: ShopSettings | undefined, rates: TaxRate[] | undefined): number {
  if (!settings || settings.prices_include_tax || !rates) return product.price;
  const chosen = rates.filter((r) => product.tax_rate_ids.includes(r.id)).sort((a, b) => a.position - b.position);
  let taxed = 0;
  for (const r of chosen) taxed += ((r.compound ? product.price + taxed : product.price) * Number(r.percent)) / 100;
  return Math.round(product.price + taxed);
}

// ---- Offline queue -----------------------------------------------------------------

export interface QueuedSale {
  client_id: string;
  lines: { product_id?: string; name?: string; quantity: string; unit_price?: number; discount?: number }[];
  customer_id?: string | null;
  paid_cash: number;
  note?: string | null;
  sold_at: string;
}

const QUEUE = "companymgmt.pos.queue";

function read(): QueuedSale[] {
  try {
    return JSON.parse(localStorage.getItem(QUEUE) ?? "[]") as QueuedSale[];
  } catch {
    return [];
  }
}

function write(items: QueuedSale[]) {
  try {
    localStorage.setItem(QUEUE, JSON.stringify(items));
  } catch {
    // Storage full or blocked: the sale stays in memory for this page only.
  }
}

/** Send a sale; if the connection is down, keep it to send later (the server keeps a
 * sale sent twice only once, by its client_id). */
export async function submitSale(sale: QueuedSale): Promise<Sale | null> {
  try {
    return await api<Sale>("/v1/sales", { method: "POST", body: sale });
  } catch (e) {
    if (e instanceof ApiError) throw e;
    write([...read(), sale]);
    return null;
  }
}

/** Sales waiting to be sent, and a function that tries to send them. */
export function useOfflineQueue(onSynced: () => void) {
  const [pending, setPending] = useState(0);
  useEffect(() => {
    let busy = false;
    const flush = async () => {
      const items = read();
      setPending(items.length);
      if (busy || !items.length || !navigator.onLine) return;
      busy = true;
      const left: QueuedSale[] = [];
      for (const item of items) {
        try {
          await api<Sale>("/v1/sales", { method: "POST", body: item });
        } catch (e) {
          // Still offline: keep it. Refused by the server: keep it too, for a person to see.
          left.push(item);
          if (!(e instanceof ApiError)) break;
        }
      }
      const rest = [...left, ...read().filter((i) => !items.some((x) => x.client_id === i.client_id))];
      write(rest);
      setPending(rest.length);
      busy = false;
      if (rest.length < items.length) onSynced();
    };
    void flush();
    const timer = window.setInterval(() => void flush(), 15_000);
    window.addEventListener("online", flush);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("online", flush);
    };
  }, [onSynced]);
  return pending;
}
