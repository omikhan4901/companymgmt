"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import { useRoles } from "@/api/hooks";
import { useWorkspace } from "@/auth/session";
import { Secret } from "@/components/secret";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Switch } from "@/components/ui/choice";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { errorMessage } from "@/lib/errors";

interface SsoConnection {
  issuer: string;
  client_id: string;
  domains: string[];
  enabled: boolean;
  auto_join: boolean;
  default_role_id: string | null;
  enforce: boolean;
  redirect_uri: string;
  provider_checked_at: string | null;
  version: number;
}

function words(text: string): string[] {
  return text
    .split(/[\s,]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function Upgrade() {
  const { t } = useTranslation();
  return <Alert tone="info">{t("security.enterpriseOnly")}</Alert>;
}

export function CompanySignIn() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const workspace = useWorkspace();
  const roles = useRoles();
  const owner = workspace.role_key === "owner";
  const settings = useQuery({ queryKey: ["sso"], queryFn: () => api<{ redirect_uri: string; connection: SsoConnection | null }>("/v1/sso/settings") });
  const current = settings.data?.connection ?? null;
  const [issuer, setIssuer] = useState("");
  const [clientId, setClientId] = useState("");
  const [secret, setSecret] = useState("");
  const [domains, setDomains] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [autoJoin, setAutoJoin] = useState(false);
  const [roleId, setRoleId] = useState("");
  const [enforce, setEnforce] = useState(false);
  useEffect(() => {
    if (!current) return;
    setIssuer(current.issuer);
    setClientId(current.client_id);
    setDomains(current.domains.join(", "));
    setEnabled(current.enabled);
    setAutoJoin(current.auto_join);
    setRoleId(current.default_role_id ?? "");
    setEnforce(current.enforce);
  }, [current]);
  const save = useMutation({
    mutationFn: () =>
      api<SsoConnection>("/v1/sso/settings", {
        method: "PUT",
        version: current?.version,
        body: {
          issuer: issuer.trim(),
          client_id: clientId.trim(),
          client_secret: secret || null,
          domains: words(domains),
          enabled,
          auto_join: autoJoin,
          default_role_id: roleId || null,
          enforce,
        },
      }),
    onSuccess: () => {
      setSecret("");
      toast.success(t("common.saved"));
      void queryClient.invalidateQueries({ queryKey: ["sso"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: () => api("/v1/sso/settings", { method: "DELETE" }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["sso"] }),
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (!workspace.plan.features.sso) return <Upgrade />;
  return (
    <Card>
      <CardHeader title={t("security.ssoTitle")} sub={t("security.ssoSub")} />
      <div className="flex flex-col gap-4 p-5 pt-4">
        {settings.data && <Secret label={t("security.redirectUri")} value={settings.data.redirect_uri} />}
        {!owner && <Alert tone="info">{t("security.ownerOnly")}</Alert>}
        <fieldset disabled={!owner} className="flex flex-col gap-4">
          <Field label={t("security.issuer")} help={t("security.issuerHelp")}>
            <Input value={issuer} onChange={(e) => setIssuer(e.target.value)} placeholder="https://accounts.google.com" />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("security.clientId")}>
              <Input value={clientId} onChange={(e) => setClientId(e.target.value)} />
            </Field>
            <Field label={t("security.clientSecret")} help={current ? t("security.secretKept") : undefined}>
              <Input type="password" autoComplete="off" value={secret} onChange={(e) => setSecret(e.target.value)} />
            </Field>
          </div>
          <Field label={t("security.domains")} help={t("security.domainsHelp")}>
            <Input value={domains} onChange={(e) => setDomains(e.target.value)} placeholder="example.com" />
          </Field>
          <label className="flex items-center gap-3 text-sm">
            <Switch checked={enabled} onCheckedChange={setEnabled} aria-label={t("security.enabled")} />
            {t("security.enabled")}
          </label>
          <label className="flex items-center gap-3 text-sm">
            <Switch checked={autoJoin} onCheckedChange={setAutoJoin} aria-label={t("security.autoJoin")} />
            {t("security.autoJoin")}
          </label>
          {autoJoin && (
            <Field label={t("security.defaultRole")} className="max-w-xs">
              <Select value={roleId} onChange={(e) => setRoleId(e.target.value)}>
                <option value="">{t("security.employeeDefault")}</option>
                {(roles.data ?? [])
                  .filter((r) => r.key !== "owner")
                  .map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
              </Select>
            </Field>
          )}
          <label className="flex items-start gap-3 text-sm">
            <Switch checked={enforce} onCheckedChange={setEnforce} aria-label={t("security.enforce")} />
            <span className="flex flex-col">
              {t("security.enforce")}
              <span className="text-xs text-muted">{t("security.enforceHelp")}</span>
            </span>
          </label>
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" loading={save.isPending} disabled={!issuer || !clientId || !domains || (!current && !secret)} onClick={() => save.mutate()}>
              {t("security.checkAndSave")}
            </Button>
            {current && (
              <Button variant="ghost" loading={remove.isPending} onClick={() => remove.mutate()}>
                {t("security.removeSso")}
              </Button>
            )}
          </div>
        </fieldset>
      </div>
    </Card>
  );
}

export function NetworkAllowlist() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const workspace = useWorkspace();
  const list = useQuery({ queryKey: ["ip-allowlist"], queryFn: () => api<{ entries: string[]; your_ip: string | null }>("/v1/workspace/ip-allowlist") });
  const [text, setText] = useState("");
  useEffect(() => setText((list.data?.entries ?? []).join("\n")), [list.data]);
  const save = useMutation({
    mutationFn: () => api("/v1/workspace/ip-allowlist", { method: "PUT", body: { entries: words(text) } }),
    onSuccess: () => {
      toast.success(t("common.saved"));
      void queryClient.invalidateQueries({ queryKey: ["ip-allowlist"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (!workspace.plan.features.sso) return null;
  return (
    <Card>
      <CardHeader title={t("security.ipTitle")} sub={t("security.ipSub")} />
      <div className="flex flex-col gap-3 p-5 pt-4">
        {list.data?.your_ip && <p className="text-sm text-muted">{t("security.yourIp", { ip: list.data.your_ip })}</p>}
        <Field label={t("security.networks")} help={t("security.networksHelp")}>
          <Textarea rows={4} value={text} disabled={workspace.role_key !== "owner"} onChange={(e) => setText(e.target.value)} placeholder="203.0.113.0/24" />
        </Field>
        {workspace.role_key === "owner" && (
          <Button className="self-start" loading={save.isPending} onClick={() => save.mutate()}>
            {t("common.save")}
          </Button>
        )}
      </div>
    </Card>
  );
}

export function OwnAIKey() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const workspace = useWorkspace();
  const status = useQuery({ queryKey: ["ai", "status"], queryFn: () => api<{ own_key: boolean; own_key_hint: string | null }>("/v1/ai/status") });
  const [key, setKey] = useState("");
  const done = () => {
    setKey("");
    void queryClient.invalidateQueries({ queryKey: ["ai"] });
  };
  const save = useMutation({
    mutationFn: () => api("/v1/ai/own-key", { method: "PUT", body: { key: key.trim() } }),
    onSuccess: () => {
      toast.success(t("common.saved"));
      done();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const remove = useMutation({ mutationFn: () => api("/v1/ai/own-key", { method: "DELETE" }), onSuccess: done, onError: (e) => toast.error(errorMessage(e)) });
  if (!workspace.plan.features.sso || workspace.role_key !== "owner") return null;
  return (
    <Card>
      <CardHeader title={t("security.aiKeyTitle")} sub={t("security.aiKeySub")} />
      <div className="flex flex-col gap-3 p-5 pt-4">
        {status.data?.own_key ? (
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm">{t("security.aiKeyInUse", { hint: status.data.own_key_hint })}</span>
            <Button variant="ghost" loading={remove.isPending} onClick={() => remove.mutate()}>
              {t("security.aiKeyRemove")}
            </Button>
          </div>
        ) : (
          <div className="flex flex-wrap items-end gap-2">
            <Field label={t("security.aiKey")} className="min-w-64 flex-1">
              <Input type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} />
            </Field>
            <Button loading={save.isPending} disabled={key.trim().length < 20} onClick={() => save.mutate()}>
              {t("common.save")}
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}
