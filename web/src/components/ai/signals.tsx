"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Info, X } from "lucide-react";
import Link from "next/link";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { Signals } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { errorMessage } from "@/lib/errors";
import { formatDay, formatNumber } from "@/lib/format";

/** "Needs a look": early-warning signals within the viewer's departments. Nothing shows
 * when the workspace hasn't chosen them or there's nothing unusual. */
export function SignalsCard() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const data = useQuery({ queryKey: ["signals"], queryFn: () => api<Signals>("/v1/reports/signals"), staleTime: 300_000 });
  const dismiss = useMutation({
    mutationFn: (key: string) => api("/v1/reports/signals/dismiss", { method: "POST", body: { key } }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["signals"] }),
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (!data.data?.on || !data.data.items.length) return null;
  return (
    <Card className="mb-5 pb-4">
      <CardHeader title={t("signals.title")} sub={t("signals.sub")} />
      <ul className="mt-3 flex flex-col gap-2 px-5">
        {data.data.items.map((s) => {
          const v = s.values as Record<string, string | number>;
          const values = Object.fromEntries(
            Object.entries(v).map(([k, x]) => [k, k === "due" ? formatDay(String(x)) : typeof x === "number" ? formatNumber(x) : x]),
          );
          const Icon = s.severity === "warning" ? AlertTriangle : Info;
          return (
            <li key={s.key} className="flex items-start gap-3 rounded-xl border border-border p-3">
              <Icon className={s.severity === "warning" ? "mt-0.5 size-4 shrink-0 text-warn-text" : "mt-0.5 size-4 shrink-0 text-muted"} aria-hidden="true" />
              <span className="min-w-0 flex-1 text-sm">
                {s.link ? (
                  <Link href={s.link} className="font-medium underline-offset-4 hover:underline">
                    {s.subject}
                  </Link>
                ) : (
                  <span className="font-medium">{s.subject}</span>
                )}
                {": "}
                {t(`signals.kinds.${s.kind}`, values)}
              </span>
              <Button variant="ghost" size="iconSm" aria-label={t("signals.dismiss", { subject: s.subject })} onClick={() => dismiss.mutate(s.key)}>
                <X aria-hidden="true" />
              </Button>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 px-5 text-xs text-muted">{t("signals.note")}</p>
    </Card>
  );
}
