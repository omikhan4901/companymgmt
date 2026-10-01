"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { Token } from "@/api/types";
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
  email: string;
  name: string | null;
  account_exists: boolean;
}

export default function InvitePage() {
  const { t } = useTranslation();
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const { signedIn, me, signIn } = useSession();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const lookup = useQuery({
    queryKey: ["invite", token],
    queryFn: () => api<Lookup>("/v1/invites/lookup", { query: { token } }),
    retry: false,
  });
  const { register, handleSubmit, setError: setFieldError, formState } = useForm<{ name: string; password: string }>({
    values: { name: lookup.data?.name ?? "", password: "" },
    // Data that arrives late fills the form without wiping what the person already typed.
    resetOptions: { keepDirtyValues: true },
  });

  const accept = async (values?: { name: string; password: string }) => {
    setBusy(true);
    setError(null);
    try {
      await signIn(await api<Token>("/v1/invites/accept", { body: { token, ...(values ?? {}) } }));
      router.replace("/app");
    } catch (e) {
      if (!applyFieldErrors(setFieldError, ["name", "password"], e)) setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  if (lookup.isPending) return <PageLoading />;
  if (lookup.isError) {
    return (
      <AuthLayout title={t("errors.notFound")}>
        <Alert tone="error">{errorMessage(lookup.error)}</Alert>
      </AuthLayout>
    );
  }
  const invite = lookup.data;
  const sameUser = signedIn && me?.email?.toLowerCase() === invite.email.toLowerCase();

  return (
    <AuthLayout title={invite.workspace} sub={invite.email}>
      {error && <Alert tone="error" className="mb-5">{error}</Alert>}
      {invite.account_exists ? (
        sameUser ? (
          <Button variant="primary" size="lg" className="w-full" loading={busy} onClick={() => void accept()}>
            {t("common.continue")}
          </Button>
        ) : (
          <Button asChild variant="primary" size="lg" className="w-full">
            <Link href={`/login?next=${encodeURIComponent(`/invite?token=${token}`)}`}>{t("auth.signIn")}</Link>
          </Button>
        )
      ) : (
        <form onSubmit={handleSubmit((v) => accept(v))} className="flex flex-col gap-4" noValidate>
          <Field label={t("signup.yourName")} error={formState.errors.name?.message}>
            <Input autoComplete="name" {...register("name", { required: t("common.required") })} />
          </Field>
          <Field label={t("auth.password")} help={t("auth.passwordHelp")} error={formState.errors.password?.message}>
            <PasswordInput
              autoComplete="new-password"
              {...register("password", { required: t("common.required"), minLength: { value: 8, message: t("auth.passwordHelp") } })}
            />
          </Field>
          <Button type="submit" variant="primary" size="lg" loading={busy} className="w-full">
            {t("common.continue")}
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
