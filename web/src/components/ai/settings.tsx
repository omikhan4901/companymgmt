"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api, ApiError } from "@/api/client";
import type { AIAllowance, AIStatus } from "@/api/types";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/choice";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Table, Td, Th } from "@/components/ui/table";
import { errorMessage } from "@/lib/errors";
import { normalizeDigits } from "@/lib/format";

import { aiKeys, UsageLine, useAIStatus } from "./ai";

const FEATURES = ["ask", "documents", "brief", "actions", "writing", "automations", "signals"] as const;

interface Change {
  enabled: boolean;
  features: string[];
  accept_terms?: boolean;
  signal_people?: boolean;
}

/** Workspace admins switch the assistant on and choose which features it helps with. */
export function AISettings() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const status = useAIStatus();
  const [terms, setTerms] = useState<Change | null>(null);
  const save = useMutation({
    mutationFn: (body: Change) => api<AIStatus>("/v1/ai/settings", { method: "PUT", body }),
    onSuccess: (s) => {
      queryClient.setQueryData(aiKeys.status, s);
      setTerms(null);
      toast.success(t("common.saved"));
    },
    onError: (e, body) => {
      if (e instanceof ApiError && e.code === "ai_terms_needed") setTerms(body);
      else toast.error(errorMessage(e));
    },
  });
  const s = status.data;
  if (!s) return null;
  const change = (patch: Partial<Change>) => save.mutate({ enabled: s.enabled, features: s.features, ...patch });
  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <p className="text-sm text-muted">{t("ai.settingsSub")}</p>
      {!s.available && <Alert tone="warn">{t("ai.notSetUpBody")}</Alert>}
      {s.allowance === 0 && <Alert tone="info">{t("ai.notInPlan")}</Alert>}
      <Card className="flex items-center gap-3 px-4 py-3">
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="font-medium">{t("ai.switch")}</span>
          <span className="text-xs text-muted">
            <UsageLine status={s} />
          </span>
        </span>
        <Switch checked={s.enabled} disabled={save.isPending} onCheckedChange={(on) => change({ enabled: on, features: on && !s.features.length ? ["ask"] : s.features })} aria-label={t("ai.switch")} />
      </Card>
      <fieldset className="flex flex-col gap-2" disabled={!s.enabled || save.isPending}>
        <legend className="mb-2 text-sm font-medium">{t("ai.featuresTitle")}</legend>
        {FEATURES.map((f) => (
          <Card key={f} className="flex items-center gap-3 px-4 py-3">
            <span className="flex min-w-0 flex-1 flex-col gap-0.5">
              <span className="font-medium">{t(`ai.features.${f}`)}</span>
              <span className="text-xs text-muted">{t(`ai.featureHints.${f}`)}</span>
            </span>
            <Switch
              checked={s.features.includes(f)}
              disabled={!s.enabled || save.isPending}
              onCheckedChange={(on) => change({ features: on ? [...s.features, f] : s.features.filter((x) => x !== f) })}
              aria-label={t(`ai.features.${f}`)}
            />
          </Card>
        ))}
      </fieldset>
      {s.features.includes("signals") && (
        <Card className="flex items-center gap-3 px-4 py-3">
          <span className="flex min-w-0 flex-1 flex-col gap-0.5">
            <span className="font-medium">{t("ai.signalPeople")}</span>
            <span className="text-xs text-muted">{t("ai.signalPeopleHint")}</span>
          </span>
          <Switch checked={s.signal_people ?? false} disabled={!s.enabled || save.isPending} onCheckedChange={(on) => change({ signal_people: on })} aria-label={t("ai.signalPeople")} />
        </Card>
      )}
      <p className="text-xs text-muted">{t("ai.privacy")}</p>
      <Dialog open={!!terms} onOpenChange={(o) => !o && setTerms(null)}>
        <DialogContent
          title={t("ai.termsTitle")}
          closeLabel={t("common.close")}
          footer={
            <>
              <Button onClick={() => setTerms(null)}>{t("common.cancel")}</Button>
              <Button variant="primary" loading={save.isPending} onClick={() => terms && save.mutate({ ...terms, accept_terms: true })}>
                {t("ai.termsAccept")}
              </Button>
            </>
          }
        >
          <ul className="flex list-disc flex-col gap-2 pl-5 text-sm text-muted">
            <li>{t("ai.terms.provider")}</li>
            <li>{t("ai.terms.scope")}</li>
            <li>{t("ai.terms.check")}</li>
            <li>{t("ai.terms.owner")}</li>
          </ul>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export function useIsOperator() {
  return useQuery({ queryKey: ["operator", "me"], queryFn: () => api<{ operator: boolean }>("/v1/operator/me"), staleTime: 3_600_000 });
}

/** Platform operators set how many questions each plan includes; workspaces are told. */
export function AIAllowances() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const list = useQuery({ queryKey: ["operator", "ai-allowances"], queryFn: () => api<AIAllowance[]>("/v1/operator/ai-allowances") });
  const [values, setValues] = useState<Record<string, string>>({});
  useEffect(() => {
    if (list.data) setValues(Object.fromEntries(list.data.map((a) => [a.plan_key, a.questions_per_month === null ? "" : String(a.questions_per_month)])));
  }, [list.data]);
  const save = useMutation({
    mutationFn: () =>
      api<AIAllowance[]>("/v1/operator/ai-allowances", {
        method: "PUT",
        body: {
          allowances: Object.entries(values).map(([plan_key, v]) => ({ plan_key, questions_per_month: v.trim() === "" ? null : Number(normalizeDigits(v)) })),
        },
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(["operator", "ai-allowances"], data);
      void queryClient.invalidateQueries({ queryKey: aiKeys.status });
      toast.success(t("ai.allowancesSaved"));
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (list.error) return <Alert tone="error">{errorMessage(list.error)}</Alert>;
  if (!list.data) return null;
  const invalid = Object.values(values).some((v) => v.trim() !== "" && !/^\d+$/.test(normalizeDigits(v.trim())));
  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <p className="text-sm text-muted">{t("ai.allowancesSub")}</p>
      <Card className="overflow-hidden">
        <Table label={t("ai.allowancesTitle")}>
          <thead>
            <tr>
              <Th>{t("ai.plan")}</Th>
              <Th>{t("ai.questionsPerMonth")}</Th>
            </tr>
          </thead>
          <tbody>
            {list.data.map((a) => (
              <tr key={a.plan_key}>
                <Td>{a.plan_name}</Td>
                <Td>
                  <Input
                    inputMode="numeric"
                    aria-label={t("ai.questionsFor", { plan: a.plan_name })}
                    placeholder={t("ai.unlimited")}
                    value={values[a.plan_key] ?? ""}
                    onChange={(e) => setValues((v) => ({ ...v, [a.plan_key]: e.target.value }))}
                    className="max-w-40"
                  />
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>
      {invalid && <p className="text-sm text-danger-text">{t("ai.wholeNumber")}</p>}
      <Button variant="primary" className="self-start" loading={save.isPending} disabled={invalid} onClick={() => save.mutate()}>
        {t("common.save")}
      </Button>
    </div>
  );
}
