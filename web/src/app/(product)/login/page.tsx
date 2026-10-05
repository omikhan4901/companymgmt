"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { ToggleGroup } from "radix-ui";
import { useCallback, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { api, ApiError } from "@/api/client";
import type { LoginResult, Token } from "@/api/types";
import { PublicOnly } from "@/auth/guards";
import { useSession } from "@/auth/session";
import { AuthLayout } from "@/components/auth-layout";
import { captchaAvailable, Turnstile } from "@/components/turnstile";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password";
import { currentLang } from "@/i18n";
import { errorMessage } from "@/lib/errors";
import { slugFromHost } from "@/lib/address";
import { safeNext } from "@/lib/nav";
import { PasskeySignIn } from "@/components/passkeys";

interface Credentials {
  email: string;
  workspace: string;
  username: string;
  password: string;
}

function LoginForm() {
  const { t } = useTranslation();
  const { signIn } = useSession();
  const router = useRouter();
  const params = useSearchParams();
  // Opened on a workspace's own address (<slug>.companymgmt.app): staff sign in without the code.
  const [hostSlug] = useState(() => (typeof window === "undefined" ? null : slugFromHost(window.location.host)));
  const place = useQuery({
    queryKey: ["public-workspace", hostSlug],
    queryFn: () =>
      api<{ name: string; slug: string; moved_to: string | null; sso: boolean; sso_required: boolean }>("/v1/public/workspace", { query: { slug: hostSlug ?? "" } }),
    enabled: !!hostSlug,
    retry: false,
  });
  const [mode, setMode] = useState<"email" | "staff">(params.get("workspace") || hostSlug ? "staff" : "email");
  const [challenge, setChallenge] = useState<string | null>(null);
  const [needCaptcha, setNeedCaptcha] = useState(false);
  const [captchaToken, setCaptchaToken] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);
  const onToken = useCallback((token: string) => setCaptchaToken(token), []);
  const { register, handleSubmit, formState } = useForm<Credentials>({
    defaultValues: { email: "", workspace: params.get("workspace") ?? hostSlug ?? "", username: "", password: "" },
  });
  const required = { required: t("common.required") };

  const done = async (token: { access_token: string | null }) => {
    await signIn({ access_token: token.access_token ?? "" });
    router.replace(safeNext(params.get("next")));
  };

  const submit = handleSubmit(async (values) => {
    setError(null);
    try {
      const body =
        mode === "email"
          ? { email: values.email.trim(), password: values.password }
          : { workspace: values.workspace.trim().toLowerCase(), username: values.username.trim(), password: values.password };
      const result = await api<LoginResult>("/v1/auth/login", { body: { ...body, captcha_token: captchaToken } });
      if (result.mfa_required) setChallenge(result.challenge);
      else await done(result);
    } catch (e) {
      if (e instanceof ApiError && e.code === "captcha_required") {
        setNeedCaptcha(true);
        setError(captchaAvailable ? t("auth.captcha") : errorMessage(e));
      } else setError(errorMessage(e));
    }
  });

  if (challenge) return <SecondStep challenge={challenge} onExpired={() => setChallenge(null)} onDone={done} />;

  return (
    <AuthLayout
      title={t("auth.signInTitle")}
      sub={t("auth.signInSub")}
      footer={
        <>
          {t("auth.noAccount")}{" "}
          <Link href="/signup" className="font-semibold text-accent-soft-text hover:underline">
            {t("auth.signUp")}
          </Link>
        </>
      }
    >
      <ToggleGroup.Root
        type="single"
        value={mode}
        onValueChange={(v) => v && setMode(v as "email" | "staff")}
        className="mb-6 grid grid-cols-2 gap-1 rounded-xl border border-border bg-surface p-1"
        aria-label={t("auth.signIn")}
      >
        {(["email", "staff"] as const).map((m) => (
          <ToggleGroup.Item
            key={m}
            value={m}
            className="h-9 rounded-lg px-2 text-sm font-medium text-muted data-[state=on]:bg-accent-soft data-[state=on]:text-accent-soft-text"
          >
            {m === "email" ? t("auth.withEmail") : t("auth.withUsername")}
          </ToggleGroup.Item>
        ))}
      </ToggleGroup.Root>
      {error && <Alert tone="error" className="mb-5">{error}</Alert>}
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        {mode === "email" ? (
          <Field label={t("auth.email")} error={formState.errors.email?.message}>
            <Input type="email" autoComplete="email" inputMode="email" autoFocus {...register("email", required)} />
          </Field>
        ) : (
          <>
            {hostSlug ? (
              <p className="text-sm text-muted">{t("auth.signingInTo", { name: place.data?.name ?? hostSlug })}</p>
            ) : (
              <Field label={t("auth.workspaceCode")} help={t("auth.workspaceCodeHelp")} error={formState.errors.workspace?.message}>
                <Input autoComplete="organization" autoCapitalize="none" {...register("workspace", required)} />
              </Field>
            )}
            <Field label={t("auth.username")} error={formState.errors.username?.message}>
              <Input autoComplete="username" autoCapitalize="none" {...register("username", required)} />
            </Field>
          </>
        )}
        <Field label={t("auth.password")} error={formState.errors.password?.message}>
          <PasswordInput autoComplete="current-password" {...register("password", required)} />
        </Field>
        {needCaptcha && captchaAvailable && <Turnstile onToken={onToken} language={currentLang()} />}
        <Button type="submit" variant="primary" size="lg" loading={formState.isSubmitting} className="mt-1 w-full">
          {t("auth.signIn")}
        </Button>
      </form>
      {mode === "email" && (
        <Link href="/forgot-password" className="mt-4 inline-block text-sm font-medium text-accent-soft-text hover:underline">
          {t("auth.forgot")}
        </Link>
      )}
      <PasskeySignIn onToken={done} workspace={hostSlug} />
      <CompanyAccount slug={hostSlug} offered={place.data?.sso ?? false} next={params.get("next")} />
    </AuthLayout>
  );
}

/** "Sign in with your company account" (SSO). On a workspace's own address it's one
 * button; elsewhere people type the workspace code first. */
function CompanyAccount({ slug, offered, next }: { slug: string | null; offered: boolean; next: string | null }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (slug && !offered) return null;
  const go = async (workspace: string) => {
    setBusy(true);
    setError(null);
    try {
      const { url } = await api<{ url: string }>("/v1/sso/start", { body: { workspace, next: next && next.startsWith("/") ? next : null } });
      window.location.assign(url);
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  };
  return (
    <div className="mt-6 border-t border-border pt-5">
      {error && <Alert tone="error" className="mb-3">{error}</Alert>}
      {slug ? (
        <Button className="w-full" loading={busy} onClick={() => void go(slug)}>
          {t("sso.button")}
        </Button>
      ) : open ? (
        <form
          className="flex items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (code.trim()) void go(code.trim().toLowerCase());
          }}
        >
          <Field label={t("auth.workspaceCode")} className="flex-1">
            <Input autoCapitalize="none" value={code} onChange={(e) => setCode(e.target.value)} />
          </Field>
          <Button type="submit" loading={busy}>
            {t("sso.continue")}
          </Button>
        </form>
      ) : (
        <Button variant="link" onClick={() => setOpen(true)}>
          {t("sso.button")}
        </Button>
      )}
    </div>
  );
}

function SecondStep({ challenge, onExpired, onDone }: { challenge: string; onExpired: () => void; onDone: (token: Token) => Promise<void> }) {
  const { t } = useTranslation();
  const [useRecovery, setUseRecovery] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState } = useForm<{ code: string; recovery_code: string }>();

  const verify = handleSubmit(async (values) => {
    setError(null);
    try {
      const body = useRecovery ? { recovery_code: values.recovery_code.trim() } : { code: values.code.replace(/\s/g, "") };
      await onDone(await api<Token>("/v1/auth/mfa/verify", { body: { challenge, ...body } }));
    } catch (e) {
      if (e instanceof ApiError && e.code === "challenge_expired") onExpired();
      setError(errorMessage(e));
    }
  });

  return (
    <AuthLayout title={t("auth.mfaTitle")} sub={t("auth.mfaSub")}>
      {error && <Alert tone="error" className="mb-5">{error}</Alert>}
      <form onSubmit={verify} className="flex flex-col gap-4" noValidate>
        {useRecovery ? (
          <Field label={t("auth.recoveryCode")} error={formState.errors.recovery_code?.message}>
            <Input autoFocus autoComplete="off" {...register("recovery_code", { required: t("common.required") })} />
          </Field>
        ) : (
          <Field label={t("auth.mfaCode")} error={formState.errors.code?.message}>
            <Input
              autoFocus
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={7}
              className="font-display text-lg tracking-[0.3em] tabular-nums"
              {...register("code", { required: t("common.required"), pattern: { value: /^\s*\d{3}\s?\d{3}\s*$/, message: t("common.required") } })}
            />
          </Field>
        )}
        <Button type="submit" variant="primary" size="lg" loading={formState.isSubmitting} className="w-full">
          {t("auth.verify")}
        </Button>
      </form>
      <Button variant="link" className="mt-4" onClick={() => setUseRecovery((v) => !v)}>
        {useRecovery ? t("auth.useCode") : t("auth.useRecovery")}
      </Button>
    </AuthLayout>
  );
}

export default function LoginPage() {
  return (
    <PublicOnly>
      <LoginForm />
    </PublicOnly>
  );
}
