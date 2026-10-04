"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Printer } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { Receipt } from "@/api/types";
import { useWorkspace } from "@/auth/session";
import { Button, buttonVariants } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { formatDateTime, formatMoney, formatNumber } from "@/lib/format";

/** A till receipt, sized for an 80 mm roll, printed by the browser. */
function ReceiptView() {
  const { t } = useTranslation();
  const workspace = useWorkspace();
  const id = useSearchParams().get("id");
  const receipt = useQuery({ queryKey: ["shop", "receipt", id], queryFn: () => api<Receipt>(`/v1/sales/${id}/receipt`), enabled: !!id });
  if (!receipt.data) return <div className="grid place-items-center py-16">{receipt.isError ? t("errors.notFound") : <Spinner />}</div>;
  const r = receipt.data;
  const s = r.sale;
  const money = (n: number) => formatMoney(n, r.currency);
  return (
    <div className="flex flex-col items-center gap-4">
      <div className="flex gap-2 print:hidden">
        <Link href="/app/pos" className={buttonVariants({})}>
          <ArrowLeft aria-hidden="true" />
          {t("receipt.back")}
        </Link>
        <Button variant="primary" onClick={() => window.print()}>
          <Printer aria-hidden="true" />
          {t("receipt.print")}
        </Button>
      </div>
      <article className="w-[80mm] max-w-full bg-white p-4 font-mono text-[12px] leading-snug text-black shadow print:shadow-none" aria-label={t("receipt.title", { number: s.number })}>
        <header className="mb-2 text-center">
          <p className="text-[14px] font-bold">{r.shop_name}</p>
          {r.branch_name && <p>{r.branch_name}</p>}
          {r.branch_address && <p className="whitespace-pre-line">{r.branch_address}</p>}
          {r.tax_id && <p>{(r.tax_id_label ?? t("receipt.taxId")) + ": " + r.tax_id}</p>}
          {r.header && <p className="mt-1 whitespace-pre-line">{r.header}</p>}
        </header>
        <p className="text-center font-bold">{s.kind === "return" ? t("receipt.return") : t("receipt.sale")} #{s.number}</p>
        {s.status === "voided" && <p className="text-center font-bold">{t("receipt.void")}</p>}
        <p className="text-center">{formatDateTime(s.sold_at, workspace.timezone)}</p>
        {s.sold_by_name && <p className="text-center">{t("receipt.servedBy", { name: s.sold_by_name })}</p>}
        {s.customer_name && <p className="text-center">{t("receipt.customer", { name: s.customer_name })}</p>}
        <hr className="my-2 border-dashed border-black" />
        <table className="w-full">
          <tbody>
            {s.lines.map((l) => (
              <tr key={l.id} className="align-top">
                <td className="pr-1">
                  {l.name}
                  <br />
                  <span>
                    {formatNumber(Number(l.quantity))} × {money(l.unit_price)}
                    {l.discount ? ` −${money(Math.abs(l.discount))}` : ""}
                  </span>
                </td>
                <td className="text-right tabular-nums">{money(l.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <hr className="my-2 border-dashed border-black" />
        <dl className="grid grid-cols-[1fr_auto] gap-x-2">
          {!s.prices_include_tax && (
            <>
              <dt>{t("receipt.net")}</dt>
              <dd className="text-right tabular-nums">{money(s.net)}</dd>
            </>
          )}
          {r.taxes.map((tx) => (
            <div key={tx.id} className="contents">
              <dt>
                {tx.name} {formatNumber(Number(tx.percent))}%{s.prices_include_tax ? ` (${t("receipt.included")})` : ""}
              </dt>
              <dd className="text-right tabular-nums">{money(tx.amount)}</dd>
            </div>
          ))}
          {s.rounding !== 0 && (
            <>
              <dt>{t("receipt.rounding")}</dt>
              <dd className="text-right tabular-nums">{money(s.rounding)}</dd>
            </>
          )}
          <dt className="text-[14px] font-bold">{t("receipt.total")}</dt>
          <dd className="text-right text-[14px] font-bold tabular-nums">{money(s.total)}</dd>
          {s.paid_cash !== 0 && (
            <>
              <dt>{t("receipt.cash")}</dt>
              <dd className="text-right tabular-nums">{money(s.paid_cash)}</dd>
            </>
          )}
          {s.change !== 0 && (
            <>
              <dt>{t("receipt.change")}</dt>
              <dd className="text-right tabular-nums">{money(s.change)}</dd>
            </>
          )}
          {s.on_account !== 0 && (
            <>
              <dt>{t("receipt.onAccount")}</dt>
              <dd className="text-right tabular-nums">{money(s.on_account)}</dd>
            </>
          )}
        </dl>
        {r.footer && <p className="mt-3 whitespace-pre-line text-center">{r.footer}</p>}
      </article>
    </div>
  );
}

export default function ReceiptPage() {
  return (
    <Suspense>
      <ReceiptView />
    </Suspense>
  );
}
