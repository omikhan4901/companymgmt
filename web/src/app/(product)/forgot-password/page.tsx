"use client";

import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import { AuthLayout } from "@/components/auth-layout";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { errorMessage } from "@/lib/errors";

export default function ForgotPage() {
  const { t } = useTranslation();
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState } = useForm<{ email: string }>({ defaultValues: { email: "" } });

  const submit = handleSubmit(async ({ email }) => {
    setError(null);
    try {
      await api("/v1/auth/password/forgot", { body: { email: email.trim() } });
      setSent(true);
    } catch (e) {
      setError(errorMessage(e));
    }
  });

  return (
    <AuthLayout
      title={t("auth.forgotTitle")}
      sub={t("auth.forgotSub")}
      footer={
        <Link href="/login" className="font-semibold text-accent-soft-text hover:underline">
          {t("auth.signIn")}
        </Link>
      }
    >
      {sent ? (
        <Alert tone="success">{t("auth.linkSent")}</Alert>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          {error && <Alert tone="error">{error}</Alert>}
          <Field label={t("auth.email")} error={formState.errors.email?.message}>
            <Input type="email" autoComplete="email" inputMode="email" autoFocus {...register("email", { required: t("common.required") })} />
          </Field>
          <Button type="submit" variant="primary" size="lg" loading={formState.isSubmitting} className="w-full">
            {t("auth.sendLink")}
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
