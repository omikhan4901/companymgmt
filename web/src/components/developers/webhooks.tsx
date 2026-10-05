"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, ListChecks, Plus, Send, Trash2, Webhook } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import { useWorkspace } from "@/auth/session";
import { Secret } from "@/components/secret";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, EmptyState } from "@/components/ui/card";
import { Switch } from "@/components/ui/choice";
import { ConfirmDialog } from "@/components/ui/confirm";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Table, Td, Th } from "@/components/ui/table";
import { errorMessage } from "@/lib/errors";
import { formatDateTime, formatNumber } from "@/lib/format";

interface Endpoint {
  id: string;
  url: string;
  description: string | null;
  events: string[];
  active: boolean;
  disabled_reason: string | null;
  failures: number;
  created_at: string;
  version: number;
  secret: string | null;
}

interface EventInfo {
  name: string;
  description: string;
  fields: string[];
}

interface Delivery {
  id: string;
  event_id: string;
  event: string;
  status: "pending" | "succeeded" | "failed";
  attempts: number;
  next_attempt_at: string | null;
  response_status: number | null;
  response_ms: number | null;
  error: string | null;
  created_at: string;
}

const TONE = { pending: "warn", succeeded: "success", failed: "danger" } as const;

function Editor({ endpoint, onClose, onSaved }: { endpoint: Endpoint | null; onClose: () => void; onSaved: (e: Endpoint) => void }) {
  const { t } = useTranslation();
  const catalogue = useQuery({ queryKey: ["webhooks", "events"], queryFn: () => api<EventInfo[]>("/v1/webhooks/events"), staleTime: 3_600_000 });
  const [url, setUrl] = useState(endpoint?.url ?? "https://");
  const [description, setDescription] = useState(endpoint?.description ?? "");
  const [all, setAll] = useState(endpoint ? endpoint.events.includes("*") : false);
  const [events, setEvents] = useState<Set<string>>(new Set(endpoint?.events.filter((e) => e !== "*") ?? []));
  const [active, setActive] = useState(endpoint?.active ?? true);
  const save = useMutation({
    mutationFn: () => {
      const body = { url: url.trim(), description: description.trim() || null, events: all ? ["*"] : [...events], active };
      return endpoint
        ? api<Endpoint>(`/v1/webhooks/${endpoint.id}`, { method: "PUT", body, version: endpoint.version })
        : api<Endpoint>("/v1/webhooks", { method: "POST", body });
    },
    onSuccess: onSaved,
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={endpoint ? t("webhooks.edit") : t("webhooks.add")}
        description={t("webhooks.editorSub")}
        closeLabel={t("common.close")}
        className="max-w-2xl"
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" disabled={!url.startsWith("https://") || (!all && events.size === 0)} loading={save.isPending} onClick={() => save.mutate()}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <Field label={t("webhooks.url")} help={t("webhooks.urlHelp")}>
            <Input type="url" value={url} maxLength={500} onChange={(e) => setUrl(e.target.value)} />
          </Field>
          <Field label={t("webhooks.description")} optional={t("common.optional")}>
            <Input value={description} maxLength={200} onChange={(e) => setDescription(e.target.value)} />
          </Field>
          <label className="flex items-center gap-3 text-sm">
            <Switch checked={all} onCheckedChange={setAll} aria-label={t("webhooks.allEvents")} />
            {t("webhooks.allEvents")}
          </label>
          {!all && (
            <ul className="grid max-h-64 gap-1.5 overflow-y-auto rounded-xl border border-border p-3 sm:grid-cols-2">
              {(catalogue.data ?? []).map((e) => (
                <li key={e.name}>
                  <label className="flex items-start gap-2 text-sm">
                    <input
                      type="checkbox"
                      className="mt-1"
                      checked={events.has(e.name)}
                      onChange={(ev) =>
                        setEvents((prev) => {
                          const next = new Set(prev);
                          if (ev.target.checked) next.add(e.name);
                          else next.delete(e.name);
                          return next;
                        })
                      }
                    />
                    <span className="flex flex-col">
                      <code className="text-xs">{e.name}</code>
                      <span className="text-xs text-muted">{e.description}</span>
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          )}
          <label className="flex items-center gap-3 text-sm">
            <Switch checked={active} onCheckedChange={setActive} aria-label={t("webhooks.active")} />
            {t("webhooks.active")}
          </label>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Deliveries({ endpoint, onClose }: { endpoint: Endpoint; onClose: () => void }) {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const queryClient = useQueryClient();
  const deliveries = useQuery({ queryKey: ["webhooks", endpoint.id, "deliveries"], queryFn: () => api<Delivery[]>(`/v1/webhooks/${endpoint.id}/deliveries`, { query: { limit: 50 } }) });
  const resend = useMutation({
    mutationFn: (d: Delivery) => api<Delivery>(`/v1/webhooks/deliveries/${d.id}/resend`, { method: "POST" }),
    onSuccess: (d) => {
      toast[d.status === "succeeded" ? "success" : "error"](d.status === "succeeded" ? t("webhooks.sent") : d.error ?? t("webhooks.failed"));
      void queryClient.invalidateQueries({ queryKey: ["webhooks", endpoint.id, "deliveries"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={t("webhooks.log")} description={endpoint.url} closeLabel={t("common.close")} className="max-w-3xl">
        {!deliveries.data?.length ? (
          <p className="text-sm text-muted">{t("webhooks.noDeliveries")}</p>
        ) : (
          <Table label={t("webhooks.log")}>
            <thead>
              <tr>
                <Th>{t("common.date")}</Th>
                <Th>{t("webhooks.event")}</Th>
                <Th>{t("common.status")}</Th>
                <Th className="hidden sm:table-cell">{t("webhooks.response")}</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {deliveries.data.map((d) => (
                <tr key={d.id}>
                  <Td className="whitespace-nowrap tabular-nums">{formatDateTime(d.created_at, timezone)}</Td>
                  <Td>
                    <code className="text-xs">{d.event}</code>
                  </Td>
                  <Td>
                    <Badge tone={TONE[d.status]}>{t(`webhooks.status.${d.status}`)}</Badge>
                    {d.attempts > 1 && <span className="ml-1 text-xs text-muted">×{formatNumber(d.attempts)}</span>}
                  </Td>
                  <Td className="hidden max-w-56 truncate text-xs text-muted sm:table-cell" title={d.error ?? undefined}>
                    {d.response_status ?? "–"}
                    {d.response_ms !== null && ` · ${formatNumber(d.response_ms)} ms`}
                    {d.error && ` · ${d.error}`}
                  </Td>
                  <Td>
                    <Button size="sm" variant="ghost" onClick={() => resend.mutate(d)} loading={resend.isPending && resend.variables?.id === d.id}>
                      {t("webhooks.resend")}
                    </Button>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function Webhooks() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const endpoints = useQuery({ queryKey: ["webhooks"], queryFn: () => api<Endpoint[]>("/v1/webhooks") });
  const [editing, setEditing] = useState<Endpoint | "new" | null>(null);
  const [secret, setSecret] = useState<string | null>(null);
  const [log, setLog] = useState<Endpoint | null>(null);
  const [removing, setRemoving] = useState<Endpoint | null>(null);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["webhooks"] });
  const test = useMutation({
    mutationFn: (e: Endpoint) => api<Delivery>(`/v1/webhooks/${e.id}/test`, { method: "POST" }),
    onSuccess: (d) => (d.status === "succeeded" ? toast.success(t("webhooks.testOk", { status: d.response_status })) : toast.error(d.error ?? t("webhooks.failed"))),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const roll = useMutation({
    mutationFn: (e: Endpoint) => api<Endpoint>(`/v1/webhooks/${e.id}/secret`, { method: "POST" }),
    onSuccess: (e) => setSecret(e.secret),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: (e: Endpoint) => api(`/v1/webhooks/${e.id}`, { method: "DELETE" }),
    onSuccess: () => {
      setRemoving(null);
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Card>
      <CardHeader
        title={t("webhooks.title")}
        sub={t("webhooks.sub")}
        action={
          <Button variant="primary" onClick={() => setEditing("new")}>
            <Plus aria-hidden="true" />
            {t("webhooks.add")}
          </Button>
        }
      />
      <div className="flex flex-col gap-2 p-5 pt-4">
        {!endpoints.data?.length ? (
          <EmptyState icon={<Webhook />} title={t("webhooks.none")} />
        ) : (
          <ul className="flex flex-col gap-2">
            {endpoints.data.map((e) => (
              <li key={e.id}>
                <Card className="flex flex-wrap items-center gap-3 px-4 py-3">
                  <button type="button" className="flex min-w-0 flex-1 flex-col text-left" onClick={() => setEditing(e)}>
                    <span className="flex flex-wrap items-center gap-2 font-medium">
                      <span className="truncate">{e.description || e.url}</span>
                      {!e.active && <Badge tone="warn">{t(e.disabled_reason === "failing" ? "webhooks.offFailing" : "webhooks.off")}</Badge>}
                    </span>
                    <span className="truncate text-xs text-muted">
                      {e.url} · {e.events.includes("*") ? t("webhooks.allEvents") : t("webhooks.eventCount", { count: e.events.length })}
                    </span>
                  </button>
                  <Button variant="ghost" size="iconSm" aria-label={`${t("webhooks.test")}: ${e.url}`} onClick={() => test.mutate(e)}>
                    <Send aria-hidden="true" />
                  </Button>
                  <Button variant="ghost" size="iconSm" aria-label={`${t("webhooks.log")}: ${e.url}`} onClick={() => setLog(e)}>
                    <ListChecks aria-hidden="true" />
                  </Button>
                  <Button variant="ghost" size="iconSm" aria-label={`${t("webhooks.rollSecret")}: ${e.url}`} onClick={() => roll.mutate(e)}>
                    <KeyRound aria-hidden="true" />
                  </Button>
                  <Button variant="ghost" size="iconSm" aria-label={`${t("common.delete")}: ${e.url}`} onClick={() => setRemoving(e)}>
                    <Trash2 aria-hidden="true" />
                  </Button>
                </Card>
              </li>
            ))}
          </ul>
        )}
        <p className="text-xs text-muted">{t("webhooks.verifyHint")}</p>
      </div>
      {editing && (
        <Editor
          endpoint={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(e) => {
            setEditing(null);
            if (e.secret) setSecret(e.secret);
            refresh();
          }}
        />
      )}
      {secret && (
        <Dialog open onOpenChange={(o) => !o && setSecret(null)}>
          <DialogContent title={t("webhooks.secretTitle")} description={t("webhooks.secretOnce")} closeLabel={t("common.close")} footer={<Button onClick={() => setSecret(null)}>{t("common.done")}</Button>}>
            <Secret label={t("webhooks.signingSecret")} value={secret} />
          </DialogContent>
        </Dialog>
      )}
      {log && <Deliveries endpoint={log} onClose={() => setLog(null)} />}
      <ConfirmDialog
        open={removing !== null}
        title={t("webhooks.removeTitle")}
        confirmLabel={t("common.delete")}
        busy={remove.isPending}
        onConfirm={() => removing && remove.mutate(removing)}
        onClose={() => setRemoving(null)}
      >
        {removing?.url}
      </ConfirmDialog>
    </Card>
  );
}
