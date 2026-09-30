"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Laptop, Monitor, Moon, Palette, ShieldCheck, Smartphone, Sun } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { RadioGroup } from "radix-ui";
import { useRef, useState, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api, ApiError } from "@/api/client";
import { keys } from "@/api/hooks";
import type { Session } from "@/api/types";
import { useSession } from "@/auth/session";
import { PageHeader } from "@/components/page";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Choice, ChoiceGroup } from "@/components/ui/choice";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password";
import { setLanguage, type Lang } from "@/i18n";
import { cn } from "@/lib/cn";
import { applyFieldErrors, errorMessage } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";
import { ACCENT_SWATCH, ACCENTS, MODES, useTheme, type Accent, type Mode } from "@/lib/theme";

/**
 * Runs an action; if the server asks the person to confirm who they are first, asks for
 * the password, then retries. Returns the runner and the dialog to render.
 */
function useStepUp(): [<T>(action: () => Promise<T>) => Promise<T>, ReactNode] {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const pending = useRef<{ resolve: () => void; reject: (e: unknown) => void } | null>(null);

  const run = async <T,>(action: () => Promise<T>): Promise<T> => {
    try {
      return await action();
    } catch (e) {
      if (!(e instanceof ApiError && e.code === "reauth_required")) throw e;
      await new Promise<void>((resolve, reject) => {
        pending.current = { resolve, reject: () => reject(e) };
        setPassword("");
        setError(null);
        setOpen(true);
      });
      return action();
    }
  };

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await api("/v1/auth/reauth", { body: { password } });
      setOpen(false);
      pending.current?.resolve();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const cancel = () => {
    setOpen(false);
    pending.current?.reject(null);
  };

  const dialog = (
    <Dialog open={open} onOpenChange={(o) => !o && cancel()}>
      <DialogContent
        title={t("account.confirmIt")}
        description={t("account.confirmSub")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={cancel}>{t("common.cancel")}</Button>
            <Button variant="primary" type="submit" form="stepup-form" loading={busy}>
              {t("common.continue")}
            </Button>
          </>
        }
      >
        <form
          id="stepup-form"
          onSubmit={(e) => {
            e.preventDefault();
            void confirm();
          }}
          className="flex flex-col gap-3"
        >
          {error && <Alert tone="error">{error}</Alert>}
          <Field label={t("auth.password")}>
            <PasswordInput autoFocus autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
        </form>
      </DialogContent>
    </Dialog>
  );
  return [run, dialog];
}

function Profile() {
  const { t } = useTranslation();
  const { me, reload } = useSession();
  const { register, handleSubmit, setError, formState } = useForm<{ name: string; locale: Lang }>({
    values: { name: me?.name ?? "", locale: (me?.locale as Lang) ?? "en" },
  });
  const save = useMutation({
    mutationFn: (v: { name: string; locale: Lang }) => api("/v1/auth/me", { method: "PATCH", body: { name: v.name.trim(), locale: v.locale } }),
    onSuccess: async (_, v) => {
      setLanguage(v.locale);
      await reload();
      toast.success(t("common.saved"));
    },
    onError: (e) => {
      if (!applyFieldErrors(setError, ["name", "locale"], e)) toast.error(errorMessage(e));
    },
  });
  if (!me) return null;
  return (
    <Card>
      <CardHeader title={t("account.profile")} sub={me.email ?? `@${me.username}`} />
      <form onSubmit={handleSubmit((v) => save.mutate(v))} className="flex flex-col gap-4 p-5 pt-4" noValidate>
        <Field label={t("common.name")} error={formState.errors.name?.message}>
          <Input dir="auto" {...register("name", { validate: (v) => v.trim().length > 0 || t("common.required") })} />
        </Field>
        <Field label={t("account.language")}>
          <Select {...register("locale")}>
            <option value="en">English</option>
            <option value="bn">বাংলা</option>
          </Select>
        </Field>
        <Button type="submit" variant="primary" loading={save.isPending} className="self-start">
          {t("common.save")}
        </Button>
      </form>
    </Card>
  );
}

const MODE_ICON: Record<Mode, ReactNode> = { light: <Sun aria-hidden="true" />, dark: <Moon aria-hidden="true" />, system: <Monitor aria-hidden="true" /> };

function Appearance() {
  const { t } = useTranslation();
  const { mode, accent, resolved, setMode, setAccent } = useTheme();
  return (
    <Card>
      <CardHeader title={t("appearance.title")} sub={t("appearance.help")} />
      <div className="flex flex-col gap-5 p-5 pt-4">
        <div className="flex flex-col gap-2">
          <span className="text-sm font-medium" id="mode-label">
            {t("appearance.mode")}
          </span>
          <ChoiceGroup value={mode} onValueChange={(v) => setMode(v as Mode)} className="sm:grid-cols-3" aria-labelledby="mode-label">
            {MODES.map((m) => (
              <Choice key={m} value={m} label={t(`appearance.modes.${m}`)} icon={MODE_ICON[m]} />
            ))}
          </ChoiceGroup>
        </div>
        <div className="flex flex-col gap-2">
          <span className="flex items-center gap-1.5 text-sm font-medium" id="accent-label">
            <Palette className="size-4 text-muted" aria-hidden="true" />
            {t("appearance.accent")}
          </span>
          <RadioGroup.Root value={accent} onValueChange={(v) => setAccent(v as Accent)} className="grid grid-cols-2 gap-2 sm:grid-cols-4" aria-labelledby="accent-label">
            {ACCENTS.map((a) => (
              <RadioGroup.Item
                key={a}
                value={a}
                className={cn(
                  "flex items-center gap-2.5 rounded-xl border border-border bg-surface px-3 py-2.5 text-sm font-medium transition-colors hover:border-border-strong",
                  "data-[state=checked]:border-text data-[state=checked]:ring-1 data-[state=checked]:ring-text",
                )}
              >
                <span className="size-6 shrink-0 rounded-full" style={{ background: ACCENT_SWATCH[a][resolved === "dark" ? 1 : 0] }} aria-hidden="true" />
                {t(`appearance.accents.${a}`)}
              </RadioGroup.Item>
            ))}
          </RadioGroup.Root>
        </div>
      </div>
    </Card>
  );
}

function PasswordCard() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { register, handleSubmit, reset, setError, formState } = useForm<{ current_password: string; new_password: string }>({
    defaultValues: { current_password: "", new_password: "" },
  });
  const save = useMutation({
    mutationFn: (v: { current_password: string; new_password: string }) => api("/v1/auth/password/change", { body: v }),
    onSuccess: async () => {
      reset();
      toast.success(t("account.passwordChanged"));
      await queryClient.invalidateQueries({ queryKey: keys.sessions });
    },
    onError: (e) => {
      if (!applyFieldErrors(setError, ["current_password", "new_password"], e)) toast.error(errorMessage(e));
    },
  });
  return (
    <Card>
      <CardHeader title={t("account.changePassword")} />
      <form onSubmit={handleSubmit((v) => save.mutate(v))} className="flex flex-col gap-4 p-5 pt-4" noValidate>
        <Field label={t("auth.currentPassword")} error={formState.errors.current_password?.message}>
          <PasswordInput autoComplete="current-password" {...register("current_password", { required: t("common.required") })} />
        </Field>
        <Field label={t("auth.newPassword")} help={t("auth.passwordHelp")} error={formState.errors.new_password?.message}>
          <PasswordInput autoComplete="new-password" {...register("new_password", { required: t("common.required"), minLength: { value: 8, message: t("auth.passwordHelp") } })} />
        </Field>
        <Button type="submit" loading={save.isPending} className="self-start">
          {t("account.changePassword")}
        </Button>
      </form>
    </Card>
  );
}

function RecoveryCodes({ codes }: { codes: string[] }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-3">
      <ul className="grid grid-cols-2 gap-2 rounded-xl border border-border bg-surface-2 p-3 font-mono text-sm" aria-label={t("account.recoveryTitle")}>
        {codes.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ul>
      <Button className="self-start" onClick={() => void navigator.clipboard.writeText(codes.join("\n")).then(() => toast.success(t("common.copied")))}>
        {t("common.copy")}
      </Button>
    </div>
  );
}

function TwoStep() {
  const { t } = useTranslation();
  const { me, reload } = useSession();
  const [stepUp, stepUpDialog] = useStepUp();
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [codes, setCodes] = useState<{ title: string; codes: string[] } | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const cancelled = (e: unknown) => e === null || (e instanceof ApiError && e.code === "reauth_required");

  const start = async () => {
    try {
      setSetup(await stepUp(() => api<{ secret: string; otpauth_uri: string }>("/v1/auth/mfa/setup", { method: "POST" })));
    } catch (e) {
      if (!cancelled(e)) toast.error(errorMessage(e));
    }
  };
  const enable = async () => {
    setBusy(true);
    try {
      const r = await api<{ recovery_codes: string[] }>("/v1/auth/mfa/enable", { body: { code: code.replace(/\s/g, "") } });
      setSetup(null);
      setCode("");
      await reload();
      setCodes({ title: t("account.recoveryTitle"), codes: r.recovery_codes });
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  const disable = async () => {
    try {
      await stepUp(() => api("/v1/auth/mfa/disable", { method: "POST" }));
      await reload();
    } catch (e) {
      if (!cancelled(e)) toast.error(errorMessage(e));
    }
  };
  const newCodes = async () => {
    try {
      const r = await stepUp(() => api<{ recovery_codes: string[] }>("/v1/auth/mfa/recovery-codes", { method: "POST" }));
      setCodes({ title: t("account.newCodes"), codes: r.recovery_codes });
    } catch (e) {
      if (!cancelled(e)) toast.error(errorMessage(e));
    }
  };

  return (
    <Card className="p-5">
      <div className="flex items-start gap-3">
        <span className={cn("grid size-10 shrink-0 place-items-center rounded-xl", me?.mfa_enabled ? "bg-success-soft text-success-text" : "bg-warn-soft text-warn-text")}>
          <ShieldCheck className="size-5" aria-hidden="true" />
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <h2 className="flex flex-wrap items-center gap-2 text-[17px] font-semibold">
            {t("account.mfa")}
            {me?.mfa_enabled && <Badge tone="success">{t("account.mfaOn")}</Badge>}
          </h2>
          {!me?.mfa_enabled && <p className="text-sm text-muted">{t("account.mfaOff")}</p>}
          <div className="mt-2 flex flex-wrap gap-2">
            {me?.mfa_enabled ? (
              <>
                <Button onClick={() => void newCodes()}>{t("account.newCodes")}</Button>
                <Button variant="ghost" className="text-danger" onClick={() => void disable()}>
                  {t("account.turnOff")}
                </Button>
              </>
            ) : (
              <Button variant="primary" onClick={() => void start()}>
                {t("account.turnOn")}
              </Button>
            )}
          </div>
        </div>
      </div>
      <Dialog open={setup !== null} onOpenChange={(o) => !o && setSetup(null)}>
        {setup && (
          <DialogContent
            title={t("account.mfa")}
            description={t("account.scan")}
            closeLabel={t("common.close")}
            footer={
              <>
                <Button onClick={() => setSetup(null)}>{t("common.cancel")}</Button>
                <Button variant="primary" type="submit" form="mfa-form" loading={busy} disabled={!/^\d{6}$/.test(code.replace(/\s/g, ""))}>
                  {t("auth.verify")}
                </Button>
              </>
            }
          >
            <form
              id="mfa-form"
              onSubmit={(e) => {
                e.preventDefault();
                void enable();
              }}
              className="flex flex-col items-center gap-4"
            >
              <div className="rounded-xl border border-border bg-white p-3">
                <QRCodeSVG value={setup.otpauth_uri} size={176} />
              </div>
              <p className="text-center text-xs text-muted">
                {t("account.manualKey")} <code className="break-all">{setup.secret}</code>
              </p>
              <Field label={t("auth.mfaCode")} className="w-44">
                <Input value={code} onChange={(e) => setCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code" maxLength={7} className="text-center font-display text-lg tracking-[0.3em] tabular-nums" />
              </Field>
            </form>
          </DialogContent>
        )}
      </Dialog>
      <Dialog open={codes !== null} onOpenChange={(o) => !o && setCodes(null)}>
        {codes && (
          <DialogContent title={codes.title} description={t("account.recoverySub")} closeLabel={t("common.close")} footer={<Button variant="primary" onClick={() => setCodes(null)}>{t("common.done")}</Button>}>
            <RecoveryCodes codes={codes.codes} />
          </DialogContent>
        )}
      </Dialog>
      {stepUpDialog}
    </Card>
  );
}

function Sessions() {
  const { t } = useTranslation();
  const { me } = useSession();
  const queryClient = useQueryClient();
  const sessions = useQuery({ queryKey: keys.sessions, queryFn: () => api<Session[]>("/v1/auth/sessions") });
  const tz = me?.workspace?.timezone ?? "UTC";
  const end = useMutation({
    mutationFn: (id?: string) => (id ? api(`/v1/auth/sessions/${id}`, { method: "DELETE" }) : api("/v1/auth/sessions/revoke-others", { method: "POST" })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.sessions }),
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Card>
      <CardHeader
        title={t("account.sessions")}
        action={
          (sessions.data?.length ?? 0) > 1 ? (
            <Button size="sm" onClick={() => end.mutate(undefined)}>
              {t("account.signOutOthers")}
            </Button>
          ) : undefined
        }
      />
      <ul className="divide-y divide-border px-5 pb-3 pt-2">
        {(sessions.data ?? []).map((s) => {
          const phone = /mobile|android|iphone/i.test(s.user_agent ?? "");
          const Icon = phone ? Smartphone : Laptop;
          return (
            <li key={s.id} className="flex items-center gap-3 py-3">
              <Icon className="size-5 shrink-0 text-muted" aria-hidden="true" />
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-sm">{s.user_agent ?? "—"}</span>
                <span className="text-xs text-muted">
                  {s.current ? t("account.thisDevice") : t("account.lastActive", { time: formatDateTime(s.last_seen_at, tz) })}
                  {s.ip ? ` · ${s.ip}` : ""}
                </span>
              </span>
              {s.current ? (
                <Badge tone="accent">{t("account.thisDevice")}</Badge>
              ) : (
                <Button size="sm" onClick={() => end.mutate(s.id)}>
                  {t("account.signOutDevice")}
                </Button>
              )}
            </li>
          );
        })}
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
          <Appearance />
          <PasswordCard />
        </div>
        <div className="flex flex-col gap-4">
          <TwoStep />
          <Sessions />
        </div>
      </div>
    </>
  );
}
