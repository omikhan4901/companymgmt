import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Form, Input, Modal, Select } from "antd";
import { KeyRound, Laptop, ShieldCheck } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { api, ApiError } from "@/api/client";
import { keys } from "@/api/hooks";
import type { Session } from "@/api/types";
import { useSession } from "@/auth/session";
import { Card, IconTile, PageHeader, Pill } from "@/components/ui";
import { setLanguage, type Lang } from "@/i18n";
import { applyFieldErrors, errorMessage } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";

/** Runs an action; if the server asks to confirm identity first, asks for the password and retries. */
function useStepUp() {
  const { t } = useTranslation();
  const { modal } = App.useApp();
  return async <T,>(action: () => Promise<T>): Promise<T> => {
    try {
      return await action();
    } catch (e) {
      if (!(e instanceof ApiError && e.code === "reauth_required")) throw e;
      let password = "";
      await new Promise<void>((resolve, reject) => {
        modal.confirm({
          title: t("account.confirmIt"),
          icon: null,
          content: (
            <div>
              <p className="mb-2 text-slate-600">{t("account.confirmSub")}</p>
              <Input.Password autoFocus autoComplete="current-password" onChange={(ev) => (password = ev.target.value)} aria-label={t("auth.password")} />
            </div>
          ),
          okText: t("common.continue"),
          cancelText: t("common.cancel"),
          onOk: async () => {
            await api("/v1/auth/reauth", { body: { password } });
            resolve();
          },
          onCancel: () => reject(e),
        });
      });
      return action();
    }
  };
}

function Profile() {
  const { t } = useTranslation();
  const { me, reload } = useSession();
  const { message } = App.useApp();
  const save = useMutation({
    mutationFn: (v: { name: string; locale: Lang }) => api("/v1/auth/me", { method: "PATCH", body: v }),
    onSuccess: async (_, v) => {
      setLanguage(v.locale);
      await reload();
      void message.success(t("common.save"));
    },
    onError: (e) => void message.error(errorMessage(e)),
  });
  if (!me) return null;
  return (
    <Card>
      <h2 className="mb-4 font-display text-lg font-bold text-ink">{t("account.profile")}</h2>
      <Form layout="vertical" requiredMark={false} initialValues={{ name: me.name, locale: me.locale }} onFinish={(v) => save.mutate(v)}>
        <Form.Item name="name" label={t("common.name")} rules={[{ required: true, whitespace: true }]}>
          <Input />
        </Form.Item>
        <p className="-mt-2 mb-4 text-sm text-slate-500">{me.email ?? `@${me.username}`}</p>
        <Form.Item name="locale" label={t("account.language")}>
          <Select options={[{ value: "en", label: "English" }, { value: "bn", label: "বাংলা" }]} />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={save.isPending}>
          {t("common.save")}
        </Button>
      </Form>
    </Card>
  );
}

function PasswordCard() {
  const { t } = useTranslation();
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [form] = Form.useForm();
  const save = useMutation({
    mutationFn: (v: Record<string, string>) => api("/v1/auth/password/change", { body: v }),
    onSuccess: async () => {
      form.resetFields();
      void message.success(t("account.passwordChanged"));
      await queryClient.invalidateQueries({ queryKey: keys.sessions });
    },
    onError: (e) => {
      if (!applyFieldErrors(form, e)) void message.error(errorMessage(e));
    },
  });
  return (
    <Card>
      <h2 className="mb-4 font-display text-lg font-bold text-ink">{t("account.changePassword")}</h2>
      <Form form={form} layout="vertical" requiredMark={false} onFinish={(v) => save.mutate(v)}>
        <Form.Item name="current_password" label={t("auth.currentPassword")} rules={[{ required: true }]}>
          <Input.Password autoComplete="current-password" />
        </Form.Item>
        <Form.Item name="new_password" label={t("auth.newPassword")} extra={t("auth.passwordHelp")} rules={[{ required: true, min: 8 }]}>
          <Input.Password autoComplete="new-password" />
        </Form.Item>
        <Button htmlType="submit" loading={save.isPending}>
          {t("account.changePassword")}
        </Button>
      </Form>
    </Card>
  );
}

function RecoveryCodes({ codes }: { codes: string[] }) {
  const { t } = useTranslation();
  return (
    <div>
      <p className="mb-3 text-slate-600">{t("account.recoverySub")}</p>
      <ul className="grid grid-cols-2 gap-2 rounded-xl bg-slate-50 p-3 font-mono text-sm">
        {codes.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ul>
      <Button className="mt-3" onClick={() => void navigator.clipboard.writeText(codes.join("\n"))}>
        {t("common.copy")}
      </Button>
    </div>
  );
}

function TwoStep() {
  const { t } = useTranslation();
  const { me, reload } = useSession();
  const { message, modal } = App.useApp();
  const stepUp = useStepUp();
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);

  const start = async () => {
    try {
      setSetup(await stepUp(() => api<{ secret: string; otpauth_uri: string }>("/v1/auth/mfa/setup", { method: "POST" })));
    } catch (e) {
      if (!(e instanceof ApiError && e.code === "reauth_required")) void message.error(errorMessage(e));
    }
  };
  const enable = async () => {
    setBusy(true);
    try {
      const r = await api<{ recovery_codes: string[] }>("/v1/auth/mfa/enable", { body: { code: code.trim() } });
      setSetup(null);
      setCode("");
      await reload();
      modal.info({ title: t("account.recoveryTitle"), content: <RecoveryCodes codes={r.recovery_codes} />, width: 480 });
    } catch (e) {
      void message.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  const disable = async () => {
    try {
      await stepUp(() => api("/v1/auth/mfa/disable", { method: "POST" }));
      await reload();
    } catch (e) {
      if (!(e instanceof ApiError && e.code === "reauth_required")) void message.error(errorMessage(e));
    }
  };
  const newCodes = async () => {
    try {
      const r = await stepUp(() => api<{ recovery_codes: string[] }>("/v1/auth/mfa/recovery-codes", { method: "POST" }));
      modal.info({ title: t("account.newCodes"), content: <RecoveryCodes codes={r.recovery_codes} />, width: 480 });
    } catch (e) {
      if (!(e instanceof ApiError && e.code === "reauth_required")) void message.error(errorMessage(e));
    }
  };

  return (
    <Card>
      <div className="flex items-start gap-3">
        <IconTile icon={ShieldCheck} tone={me?.mfa_enabled ? "brand" : "amber"} />
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-lg font-bold text-ink">
            {t("account.mfa")} {me?.mfa_enabled ? <Pill tone="green">{t("account.mfaOn")}</Pill> : null}
          </h2>
          {!me?.mfa_enabled ? <p className="text-sm text-slate-600">{t("account.mfaOff")}</p> : null}
          <div className="mt-3 flex flex-wrap gap-2">
            {me?.mfa_enabled ? (
              <>
                <Button onClick={() => void newCodes()}>{t("account.newCodes")}</Button>
                <Button danger onClick={() => void disable()}>
                  {t("account.turnOff")}
                </Button>
              </>
            ) : (
              <Button type="primary" onClick={() => void start()}>
                {t("account.turnOn")}
              </Button>
            )}
          </div>
        </div>
      </div>
      <Modal open={setup !== null} title={t("account.mfa")} onCancel={() => setSetup(null)} onOk={() => void enable()} okText={t("auth.verify")} cancelText={t("common.cancel")} confirmLoading={busy} okButtonProps={{ disabled: !/^\d{6}$/.test(code.trim()) }}>
        {setup ? (
          <div className="flex flex-col items-center gap-3">
            <p className="text-sm text-slate-600">{t("account.scan")}</p>
            <div className="rounded-xl border border-slate-200 bg-white p-3">
              <QRCodeSVG value={setup.otpauth_uri} size={176} />
            </div>
            <p className="text-xs text-slate-500">
              {t("account.manualKey")} <code className="break-all">{setup.secret}</code>
            </p>
            <Input value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code" maxLength={6} placeholder="123456" className="max-w-40 text-center tracking-widest" aria-label={t("auth.mfaCode")} />
          </div>
        ) : null}
      </Modal>
    </Card>
  );
}

function Sessions() {
  const { t } = useTranslation();
  const { me } = useSession();
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const sessions = useQuery({ queryKey: keys.sessions, queryFn: () => api<Session[]>("/v1/auth/sessions") });
  const tz = me?.workspace?.timezone ?? "UTC";
  const end = useMutation({
    mutationFn: (id?: string) => (id ? api(`/v1/auth/sessions/${id}`, { method: "DELETE" }) : api("/v1/auth/sessions/revoke-others", { method: "POST" })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.sessions }),
    onError: (e) => void message.error(errorMessage(e)),
  });
  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-display text-lg font-bold text-ink">{t("account.sessions")}</h2>
        {(sessions.data?.length ?? 0) > 1 ? (
          <Button size="small" onClick={() => end.mutate(undefined)}>
            {t("account.signOutOthers")}
          </Button>
        ) : null}
      </div>
      <ul className="divide-y divide-slate-100">
        {(sessions.data ?? []).map((s) => (
          <li key={s.id} className="flex items-center gap-3 py-3">
            <Laptop size={18} className="shrink-0 text-slate-400" aria-hidden="true" />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm text-ink">{s.user_agent ?? "—"}</span>
              <span className="text-xs text-slate-500">
                {s.current ? t("account.thisDevice") : t("account.lastActive", { time: formatDateTime(s.last_seen_at, tz) })}
                {s.ip ? ` · ${s.ip}` : ""}
              </span>
            </span>
            {!s.current ? (
              <Button size="small" onClick={() => end.mutate(s.id)}>
                {t("account.signOutDevice")}
              </Button>
            ) : null}
          </li>
        ))}
      </ul>
    </Card>
  );
}

export default function AccountPage() {
  const { t } = useTranslation();
  return (
    <>
      <PageHeader title={t("account.title")} />
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="flex flex-col gap-4">
          <Profile />
          <PasswordCard />
        </div>
        <div className="flex flex-col gap-4">
          <TwoStep />
          <Sessions />
        </div>
      </div>
      <span className="sr-only">
        <KeyRound aria-hidden="true" />
      </span>
    </>
  );
}
