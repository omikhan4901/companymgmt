"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { LoginResult } from "@/api/types";
import { useSession } from "@/auth/session";
import { AuthLayout } from "@/components/auth-layout";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password";
import { PageLoading } from "@/components/ui/spinner";
import { applyFieldErrors, errorMessage } from "@/lib/errors";

interface Lookup {
  workspace: string;
  workspace_code: string;
  role: string;
}

interface Values {
  name: string;
  username: string;
  password: string;
}

/** Someone opened a join link (or scanned its QR code): they make their own staff account. */
function JoinView() {
  const { t } = useTranslation();
  const token = useSearchParams().get("token") ?? "";
  const { signIn } = useSession();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const lookup = useQuery({ queryKey: ["join", token], queryFn: () => api<Lookup>("/v1/join/lookup", { query: { token } }), retry: false });
  const { register, handleSubmit, setError: setFieldError, formState } = useForm<Values>();
  const join = async (v: Values) => {
    setBusy(true);
    setError(null);
    try {
      const made = await api<{ workspace_code: string; username: string }>("/v1/join", { body: { token, ...v, username: v.username.trim().toLowerCase() } });
      const result = await api<LoginResult>("/v1/auth/login", { body: { workspace: made.workspace_code, username: made.username, password: v.password } });
      if (result.access_token) {
        await signIn({ access_token: result.access_token });
        router.replace("/app");
      } else {
        router.replace(`/login?workspace=${encodeURIComponent(made.workspace_code)}`);
      }
    } catch (e) {
      if (!applyFieldErrors(setFieldError, ["name", "username", "password"], e)) setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  if (lookup.isPending) return <PageLoading />;
  if (lookup.isError) {
    return (
      <AuthLayout title={t("join.invalid")}>
        <Alert tone="error">{errorMessage(lookup.error)}</Alert>
      </AuthLayout>
    );
  }
  return (
    <AuthLayout title={t("join.title", { workspace: lookup.data.workspace })} sub={t("join.sub", { role: lookup.data.role })}>
      {error && (
        <Alert tone="error" className="mb-5">
          {error}
        </Alert>
      )}
      <form onSubmit={handleSubmit((v) => join(v))} className="flex flex-col gap-4" noValidate>
        <Field label={t("signup.yourName")} error={formState.errors.name?.message}>
          <Input autoComplete="name" dir="auto" {...register("name", { required: t("common.required") })} />
        </Field>
        <Field label={t("join.username")} help={t("join.usernameHelp")} error={formState.errors.username?.message}>
          <Input autoComplete="username" autoCapitalize="none" {...register("username", { required: t("common.required"), pattern: { value: /^[a-zA-Z0-9._-]{3,40}$/, message: t("join.usernameHelp") } })} />
        </Field>
        <Field label={t("auth.password")} help={t("auth.passwordHelp")} error={formState.errors.password?.message}>
          <PasswordInput autoComplete="new-password" {...register("password", { required: t("common.required"), minLength: { value: 8, message: t("auth.passwordHelp") } })} />
        </Field>
        <Button type="submit" variant="primary" size="lg" loading={busy} className="w-full">
          {t("join.create")}
        </Button>
        <p className="text-xs text-muted">{t("join.remember", { code: lookup.data.workspace_code })}</p>
      </form>
    </AuthLayout>
  );
}

export default function JoinPage() {
  return (
    <Suspense>
      <JoinView />
    </Suspense>
  );
}
