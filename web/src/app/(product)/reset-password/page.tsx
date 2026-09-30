"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import { AuthLayout } from "@/components/auth-layout";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { PasswordInput } from "@/components/ui/password";
import { applyFieldErrors, errorMessage } from "@/lib/errors";

export default function ResetPage() {
  const { t } = useTranslation();
  const params = useSearchParams();
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, setError: setFieldError, formState } = useForm<{ password: string }>({ defaultValues: { password: "" } });

  const submit = handleSubmit(async ({ password }) => {
    setError(null);
    try {
      await api("/v1/auth/password/reset", { body: { token: params.get("token") ?? "", password } });
      setDone(true);
    } catch (e) {
      if (!applyFieldErrors(setFieldError, ["password"], e)) setError(errorMessage(e));
    }
  });

  return (
    <AuthLayout title={t("auth.resetTitle")}>
      {done ? (
        <div className="flex flex-col gap-4">
          <Alert tone="success">{t("auth.passwordUpdated")}</Alert>
          <Button asChild variant="primary" size="lg">
            <Link href="/login">{t("auth.signIn")}</Link>
          </Button>
        </div>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          {error && (
            <Alert
              tone="error"
              action={
                <Link href="/forgot-password" className="shrink-0 font-semibold underline">
                  {t("auth.sendLink")}
                </Link>
              }
            >
              {error}
            </Alert>
          )}
          <Field label={t("auth.newPassword")} help={t("auth.passwordHelp")} error={formState.errors.password?.message}>
            <PasswordInput
              autoComplete="new-password"
              autoFocus
              {...register("password", { required: t("common.required"), minLength: { value: 8, message: t("auth.passwordHelp") } })}
            />
          </Field>
          <Button type="submit" variant="primary" size="lg" loading={formState.isSubmitting} className="w-full">
            {t("common.save")}
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
