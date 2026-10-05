"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, FlaskConical, KeyRound, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import { useSession, useWorkspace } from "@/auth/session";
import { Secret } from "@/components/secret";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, EmptyState } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { errorMessage } from "@/lib/errors";
import { formatDateTime, formatDay, formatNumber } from "@/lib/format";

interface ApiKey {
  id: string;
  name: string;
  hint: string;
  permissions: string[];
  rate_per_minute: number;
  allowed_ips: string[];
  member_name: string;
  expires_at: string | null;
  previous_expires_at: string | null;
  last_used_at: string | null;
  last_used_ip: string | null;
  created_at: string;
  revoked: boolean;
  token: string | null;
}

interface Grantable {
  key: string;
  label: string;
  module: string;
}

interface UsageDay {
  day: string;
  requests: number;
  writes: number;
}

function splitLines(text: string): string[] {
  return text
    .split(/[\s,]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function NewKey({ onClose, onMade }: { onClose: () => void; onMade: (key: ApiKey) => void }) {
  const { t } = useTranslation();
  const grantable = useQuery({ queryKey: ["api-keys", "permissions"], queryFn: () => api<Grantable[]>("/v1/api-keys/permissions") });
  const [name, setName] = useState("");
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [rate, setRate] = useState("120");
  const [days, setDays] = useState("365");
  const [ips, setIps] = useState("");
  const groups = useMemo(() => {
    const byModule = new Map<string, Grantable[]>();
    for (const p of grantable.data ?? []) byModule.set(p.module, [...(byModule.get(p.module) ?? []), p]);
    return [...byModule.entries()];
  }, [grantable.data]);
  const create = useMutation({
    mutationFn: () =>
      api<ApiKey>("/v1/api-keys", {
        method: "POST",
        body: {
          name: name.trim(),
          permissions: [...chosen],
          rate_per_minute: Number(rate),
          expires_in_days: days === "never" ? null : Number(days),
          allowed_ips: splitLines(ips),
        },
      }),
    onSuccess: onMade,
    onError: (e) => toast.error(errorMessage(e)),
  });
  const toggle = (key: string, on: boolean) =>
    setChosen((prev) => {
      const next = new Set(prev);
      if (on) next.add(key);
      else next.delete(key);
      return next;
    });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={t("developers.newKey")}
        description={t("developers.newKeySub")}
        closeLabel={t("common.close")}
        className="max-w-2xl"
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" disabled={!name.trim() || chosen.size === 0} loading={create.isPending} onClick={() => create.mutate()}>
              {t("developers.makeKey")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <Field label={t("developers.keyName")} help={t("developers.keyNameHelp")}>
            <Input value={name} maxLength={120} onChange={(e) => setName(e.target.value)} />
          </Field>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 text-sm font-medium">{t("developers.permissions")}</legend>
            <p className="text-[13px] text-muted">{t("developers.permissionsHelp")}</p>
            <div className="max-h-64 overflow-y-auto rounded-xl border border-border p-3">
              {groups.map(([module, perms]) => (
                <div key={module} className="mb-3 last:mb-0">
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">{module}</p>
                  <ul className="grid gap-1 sm:grid-cols-2">
                    {perms.map((p) => (
                      <li key={p.key}>
                        <label className="flex items-start gap-2 text-sm">
                          <input type="checkbox" className="mt-1" checked={chosen.has(p.key)} onChange={(e) => toggle(p.key, e.target.checked)} />
                          <span>
                            {p.label} <code className="text-xs text-muted">{p.key}</code>
                          </span>
                        </label>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </fieldset>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("developers.rate")} help={t("developers.rateHelp")}>
              <Input type="number" min={10} max={1200} value={rate} onChange={(e) => setRate(e.target.value)} />
            </Field>
            <Field label={t("developers.expires")}>
              <Select value={days} onChange={(e) => setDays(e.target.value)}>
                {["30", "90", "365", "730"].map((d) => (
                  <option key={d} value={d}>
                    {t("developers.days", { count: Number(d), formatted: formatNumber(Number(d)) })}
                  </option>
                ))}
                <option value="never">{t("developers.never")}</option>
              </Select>
            </Field>
          </div>
          <Field label={t("developers.allowedIps")} optional={t("common.optional")} help={t("developers.allowedIpsHelp")}>
            <Textarea rows={2} value={ips} onChange={(e) => setIps(e.target.value)} placeholder="203.0.113.0/24" />
          </Field>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ShowToken({ apiKey, onClose }: { apiKey: ApiKey; onClose: () => void }) {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={t("developers.keyReady")} description={t("developers.keyOnce")} closeLabel={t("common.close")} footer={<Button onClick={onClose}>{t("common.done")}</Button>}>
        <Secret label={apiKey.name} value={apiKey.token ?? ""} testId="api-key-token" />
        {apiKey.previous_expires_at && (
          <p className="mt-3 text-sm text-muted">{t("developers.oldStillWorks", { date: formatDateTime(apiKey.previous_expires_at, timezone) })}</p>
        )}
      </DialogContent>
    </Dialog>
  );
}

function Usage({ apiKey, onClose }: { apiKey: ApiKey; onClose: () => void }) {
  const { t } = useTranslation();
  const usage = useQuery({ queryKey: ["api-keys", apiKey.id, "usage"], queryFn: () => api<UsageDay[]>(`/v1/api-keys/${apiKey.id}/usage`, { query: { days: 30 } }) });
  const max = Math.max(1, ...(usage.data ?? []).map((d) => d.requests));
  const total = (usage.data ?? []).reduce((sum, d) => sum + d.requests, 0);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={t("developers.usageTitle", { name: apiKey.name })} description={t("developers.usageSub", { total: formatNumber(total) })} closeLabel={t("common.close")}>
        {!usage.data?.length ? (
          <p className="text-sm text-muted">{t("developers.noUsage")}</p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {usage.data.map((d) => (
              <li key={d.day} className="grid grid-cols-[6rem_1fr_4rem] items-center gap-2 text-sm">
                <span className="tabular-nums text-muted">{formatDay(d.day)}</span>
                <span className="h-2.5 rounded-full bg-accent" style={{ width: `${Math.max(2, (d.requests / max) * 100)}%` }} aria-hidden="true" />
                <span className="text-right tabular-nums">{formatNumber(d.requests)}</span>
              </li>
            ))}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function ApiKeys() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const workspace = useWorkspace();
  const keys = useQuery({ queryKey: ["api-keys"], queryFn: () => api<ApiKey[]>("/v1/api-keys") });
  const [creating, setCreating] = useState(false);
  const [shown, setShown] = useState<ApiKey | null>(null);
  const [usage, setUsage] = useState<ApiKey | null>(null);
  const [revoking, setRevoking] = useState<ApiKey | null>(null);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["api-keys"] });
  const rotate = useMutation({
    mutationFn: (key: ApiKey) => api<ApiKey>(`/v1/api-keys/${key.id}/rotate`, { method: "POST", body: { grace_hours: 24 } }),
    onSuccess: (key) => {
      setShown(key);
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const revoke = useMutation({
    mutationFn: (key: ApiKey) => api(`/v1/api-keys/${key.id}`, { method: "DELETE" }),
    onSuccess: () => {
      setRevoking(null);
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Card>
      <CardHeader
        title={t("developers.keysTitle")}
        sub={t("developers.keysSub")}
        action={
          <Button variant="primary" onClick={() => setCreating(true)}>
            <Plus aria-hidden="true" />
            {t("developers.newKey")}
          </Button>
        }
      />
      <div className="flex flex-col gap-2 p-5 pt-4">
        {!keys.data?.length ? (
          <EmptyState icon={<KeyRound />} title={t("developers.noKeys")} />
        ) : (
          <ul className="flex flex-col gap-2">
            {keys.data.map((k) => (
              <li key={k.id}>
                <Card className="flex flex-wrap items-center gap-3 px-4 py-3">
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="flex flex-wrap items-center gap-2 font-medium">
                      {k.name}
                      <code className="text-xs text-muted">cmk_…{k.hint}…</code>
                      {k.revoked && <Badge>{t("developers.revoked")}</Badge>}
                    </span>
                    <span className="text-xs text-muted">
                      {t("developers.keyLine", { member: k.member_name, count: k.permissions.length, rate: formatNumber(k.rate_per_minute) })}
                      {" · "}
                      {k.last_used_at ? t("developers.lastUsed", { when: formatDateTime(k.last_used_at, workspace.timezone) }) : t("developers.neverUsed")}
                      {k.expires_at && ` · ${t("developers.expiresOn", { date: formatDay(k.expires_at.slice(0, 10)) })}`}
                    </span>
                  </span>
                  <Button variant="ghost" size="iconSm" aria-label={`${t("developers.usage")}: ${k.name}`} onClick={() => setUsage(k)}>
                    <BarChart3 aria-hidden="true" />
                  </Button>
                  {!k.revoked && (
                    <>
                      <Button variant="ghost" size="iconSm" aria-label={`${t("developers.rotate")}: ${k.name}`} onClick={() => rotate.mutate(k)}>
                        <RefreshCw aria-hidden="true" />
                      </Button>
                      <Button variant="ghost" size="iconSm" aria-label={`${t("developers.revoke")}: ${k.name}`} onClick={() => setRevoking(k)}>
                        <Trash2 aria-hidden="true" />
                      </Button>
                    </>
                  )}
                </Card>
              </li>
            ))}
          </ul>
        )}
      </div>
      {creating && (
        <NewKey
          onClose={() => setCreating(false)}
          onMade={(key) => {
            setCreating(false);
            setShown(key);
            refresh();
          }}
        />
      )}
      {shown && <ShowToken apiKey={shown} onClose={() => setShown(null)} />}
      {usage && <Usage apiKey={usage} onClose={() => setUsage(null)} />}
      <ConfirmDialog
        open={revoking !== null}
        title={t("developers.revokeTitle", { name: revoking?.name ?? "" })}
        confirmLabel={t("developers.revoke")}
        busy={revoke.isPending}
        onConfirm={() => revoking && revoke.mutate(revoking)}
        onClose={() => setRevoking(null)}
      >
        {t("developers.revokeBody")}
      </ConfirmDialog>
    </Card>
  );
}

export function Sandbox() {
  const { t } = useTranslation();
  const workspace = useWorkspace();
  const { switchWorkspace } = useSession();
  const make = useMutation({
    mutationFn: () => api<{ id: string; name: string }>("/v1/workspace/sandbox", { method: "POST" }),
    onSuccess: (sandbox) => {
      toast.success(t("developers.sandboxMade", { name: sandbox.name }));
      void switchWorkspace(sandbox.id);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (workspace.sandbox) return <Alert tone="info" title={t("developers.inSandbox")}>{t("developers.inSandboxSub")}</Alert>;
  if (workspace.role_key !== "owner") return null;
  return (
    <Card>
      <CardHeader title={t("developers.sandboxTitle")} sub={t("developers.sandboxSub")} />
      <div className="p-5 pt-4">
        <Button onClick={() => make.mutate()} loading={make.isPending}>
          <FlaskConical aria-hidden="true" />
          {t("developers.makeSandbox")}
        </Button>
      </div>
    </Card>
  );
}
