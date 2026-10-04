"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Circle, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import { useSession } from "@/auth/session";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { errorMessage } from "@/lib/errors";

interface Checklist {
  items: { key: string; done: boolean; link: string }[];
  dismissed: boolean;
  sample_data: boolean;
}

/** The owner's first-day checklist, until it's done or hidden, with sample data to try. */
export function FirstDay() {
  const { t } = useTranslation();
  const { can } = useSession();
  const queryClient = useQueryClient();
  const allowed = can("workspace.manage");
  const list = useQuery({ queryKey: ["welcome"], queryFn: () => api<Checklist>("/v1/welcome/checklist"), enabled: allowed });
  const refresh = () => void queryClient.invalidateQueries();
  const hide = useMutation({
    mutationFn: () => api("/v1/welcome/checklist", { method: "PUT", body: { hidden: true } }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["welcome"] }),
  });
  const sample = useMutation({
    mutationFn: (add: boolean) => api("/v1/welcome/sample-data", { method: add ? "POST" : "DELETE" }),
    onSuccess: (_, add) => {
      toast.success(add ? t("welcome.sampleAdded") : t("welcome.sampleRemoved"));
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const data = list.data;
  if (!allowed || !data || data.dismissed) return null;
  const done = data.items.filter((i) => i.done).length;
  if (done === data.items.length && !data.sample_data) return null;
  return (
    <Card className="mb-5 pb-4">
      <CardHeader
        title={t("welcome.title")}
        sub={t("welcome.progress", { done, total: data.items.length })}
        action={
          <Button variant="ghost" size="iconSm" aria-label={t("welcome.hide")} onClick={() => hide.mutate()}>
            <X aria-hidden="true" />
          </Button>
        }
      />
      <ul className="mt-3 grid gap-1 px-5 sm:grid-cols-2">
        {data.items.map((i) => (
          <li key={i.key}>
            <Link href={i.link} className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-surface-2">
              {i.done ? <CheckCircle2 className="size-4 text-success-text" aria-hidden="true" /> : <Circle className="size-4 text-muted" aria-hidden="true" />}
              <span className={i.done ? "text-muted line-through" : ""}>{t(`welcome.items.${i.key}`)}</span>
              <span className="sr-only">{i.done ? t("welcome.doneSr") : t("welcome.todoSr")}</span>
            </Link>
          </li>
        ))}
      </ul>
      <div className="mt-3 flex flex-wrap items-center gap-2 px-5">
        <Sparkles className="size-4 text-accent-soft-text" aria-hidden="true" />
        <span className="text-sm text-muted">{data.sample_data ? t("welcome.sampleHere") : t("welcome.sampleOffer")}</span>
        <Button size="sm" loading={sample.isPending} onClick={() => sample.mutate(!data.sample_data)}>
          {data.sample_data ? t("welcome.removeSample") : t("welcome.addSample")}
        </Button>
      </div>
    </Card>
  );
}
