"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

/** The active tab, kept in `?tab=` so links and reloads land on the same tab. */
export function useTab(allowed: string[]): [string, (tab: string) => void] {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const wanted = params.get("tab");
  const active = wanted && allowed.includes(wanted) ? wanted : (allowed[0] ?? "");
  const set = useCallback(
    (tab: string) => {
      const next = new URLSearchParams(params);
      next.set("tab", tab);
      router.replace(`${pathname}?${next.toString()}`, { scroll: false });
    },
    [params, router, pathname],
  );
  return [active, set];
}
