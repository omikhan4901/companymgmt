"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import { RequireSession } from "@/auth/guards";
import { useSession } from "@/auth/session";
import { AuthLayout } from "@/components/auth-layout";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { PasswordInput } from "@/components/ui/password";
import { applyFieldErrors, errorMessage } from "@/lib/errors";

interface Values {
  current_password: string;
  new_password: string;
}

function ChangePasswordForm() {
  const { t } = useTranslation();
  const { reload } = useSession();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, setError: setFieldError, formState } = useForm<Values>({ defaultValues: { current_password: "", new_password: "" } });

  const submit = handleSubmit(async (values) => {
    setError(null);
    try {
      await api("/v1/auth/password/change", { body: values });
      await reload();
      router.replace("/app");
    } catch (e) {
      if (!applyFieldErrors(setFieldError, ["current_password", "new_password"], e)) setError(errorMessage(e));
    }
  });

  return (
    <AuthLayout title={t("auth.mustChangeTitle")} sub={t("auth.mustChangeSub")}>
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        {error && <Alert tone="error">{error}</Alert>}
        <Field label={t("auth.currentPassword")} error={formState.errors.current_password?.message}>
          <PasswordInput autoComplete="current-password" {...register("current_password", { required: t("common.required") })} />
        </Field>
        <Field label={t("auth.newPassword")} help={t("auth.passwordHelp")} error={formState.errors.new_password?.message}>
          <PasswordInput
            autoComplete="new-password"
            {...register("new_password", { required: t("common.required"), minLength: { value: 8, message: t("auth.passwordHelp") } })}
          />
        </Field>
        <Button type="submit" variant="primary" size="lg" loading={formState.isSubmitting} className="w-full">
          {t("common.save")}
        </Button>
      </form>
    </AuthLayout>
  );
}

export default function ChangePasswordPage() {
  return (
    <RequireSession>
      <ChangePasswordForm />
    </RequireSession>
  );
}
