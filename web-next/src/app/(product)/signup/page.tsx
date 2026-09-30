"use client";

import { Briefcase, Coffee, Factory, HelpCircle, Store, UtensilsCrossed, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { api, ApiError } from "@/api/client";
import type { Token } from "@/api/types";
import { PublicOnly } from "@/auth/guards";
import { useSession } from "@/auth/session";
import { AuthLayout } from "@/components/auth-layout";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Choice, ChoiceGroup } from "@/components/ui/choice";
import { Field } from "@/components/ui/field";
import { Input, Select } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password";
import { currentLang, setLanguage, type Lang } from "@/i18n";
import { cn } from "@/lib/cn";
import { applyFieldErrors, errorMessage } from "@/lib/errors";
import { browserTimezone, countryOptions, guessCountry, timezoneOptions } from "@/lib/places";

const TYPES: { key: string; icon: LucideIcon }[] = [
  { key: "shop", icon: Coffee },
  { key: "restaurant", icon: UtensilsCrossed },
  { key: "retail", icon: Store },
  { key: "office", icon: Briefcase },
  { key: "factory", icon: Factory },
  { key: "other", icon: HelpCircle },
];
const SIZES = ["1", "2-5", "6-20", "21-100", "100+"];
const ACCOUNT_FIELDS = ["name", "email", "password"] as const;
const ALL_FIELDS = [...ACCOUNT_FIELDS, "business_name", "business_type", "team_size", "country", "timezone"] as const;

interface Values {
  name: string;
  email: string;
  password: string;
  business_name: string;
  business_type: string;
  team_size: string;
  country: string;
  timezone: string;
}

function Steps({ step }: { step: number }) {
  const { t } = useTranslation();
  const labels = [t("signup.stepLanguage"), t("signup.stepAccount"), t("signup.stepBusiness")];
  return (
    <ol className="mb-7 grid grid-cols-3 gap-2" aria-label={t("signup.steps")}>
      {labels.map((label, i) => (
        <li key={label} className="flex flex-col gap-1.5" aria-current={i === step ? "step" : undefined}>
          <span className={cn("h-1 rounded-full", i <= step ? "bg-accent" : "bg-border")} />
          <span className={cn("text-xs font-medium", i === step ? "text-text" : "text-muted")}>{label}</span>
        </li>
      ))}
    </ol>
  );
}

function SignupForm() {
  const { t } = useTranslation();
  const { signIn } = useSession();
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const { register, control, handleSubmit, trigger, setError: setFieldError, formState } = useForm<Values>({
    defaultValues: {
      name: "",
      email: "",
      password: "",
      business_name: "",
      business_type: "",
      team_size: "2-5",
      country: guessCountry() ?? "",
      timezone: browserTimezone(),
    },
  });
  const errors = formState.errors;
  const required = { required: t("common.required") };

  const chooseLanguage = (lang: Lang) => {
    setLanguage(lang);
    setStep(1);
  };

  const next = async () => {
    if (await trigger([...ACCOUNT_FIELDS])) setStep(2);
  };

  const submit = handleSubmit(async (values) => {
    setError(null);
    try {
      const body = { ...values, country: values.country || null, locale: currentLang() };
      await signIn(await api<Token>("/v1/auth/signup", { body }));
      router.replace("/app");
    } catch (e) {
      if (applyFieldErrors(setFieldError, ALL_FIELDS, e)) {
        const bad = e instanceof ApiError ? e.errors.map((x) => x.field) : [];
        if (bad.some((f) => (ACCOUNT_FIELDS as readonly string[]).includes(f))) setStep(1);
      } else setError(errorMessage(e));
    }
  });

  return (
    <AuthLayout
      title={t("auth.signUp")}
      footer={
        <>
          {t("auth.haveAccount")}{" "}
          <Link href="/login" className="font-semibold text-accent-soft-text hover:underline">
            {t("auth.signIn")}
          </Link>
        </>
      }
    >
      <Steps step={step} />
      {error && <Alert tone="error" className="mb-5">{error}</Alert>}

      {step === 0 && (
        <div>
          <p className="mb-4 font-medium">{t("signup.chooseLanguage")}</p>
          <div className="grid grid-cols-2 gap-3">
            {(
              [
                ["bn", "বাংলা"],
                ["en", "English"],
              ] as [Lang, string][]
            ).map(([lang, label]) => (
              <button
                key={lang}
                type="button"
                lang={lang}
                onClick={() => chooseLanguage(lang)}
                className="rounded-2xl border border-border bg-surface px-4 py-7 font-display text-xl font-semibold transition-colors hover:border-accent hover:bg-accent-soft/60"
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      )}

      <form onSubmit={submit} noValidate className={cn(step === 0 && "hidden")}>
        <div className={cn("flex flex-col gap-4", step !== 1 && "hidden")}>
          <Field label={t("signup.yourName")} error={errors.name?.message}>
            <Input autoComplete="name" {...register("name", { ...required, maxLength: 120, validate: (v) => v.trim().length > 0 || t("common.required") })} />
          </Field>
          <Field label={t("auth.email")} error={errors.email?.message}>
            <Input
              type="email"
              autoComplete="email"
              inputMode="email"
              {...register("email", { ...required, pattern: { value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/, message: t("common.invalidEmail") } })}
            />
          </Field>
          <Field label={t("auth.password")} help={t("auth.passwordHelp")} error={errors.password?.message}>
            <PasswordInput autoComplete="new-password" {...register("password", { ...required, minLength: { value: 8, message: t("auth.passwordHelp") }, maxLength: 128 })} />
          </Field>
          <div className="mt-2 flex gap-2">
            <Button size="lg" onClick={() => setStep(0)}>
              {t("common.back")}
            </Button>
            <Button variant="primary" size="lg" className="flex-1" onClick={() => void next()}>
              {t("common.next")}
            </Button>
          </div>
        </div>

        <div className={cn("flex flex-col gap-5", step !== 2 && "hidden")}>
          <Field label={t("signup.businessName")} error={errors.business_name?.message}>
            <Input autoComplete="organization" {...register("business_name", { validate: (v) => step !== 2 || v.trim().length > 0 || t("common.required") })} />
          </Field>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1.5 text-sm font-medium">{t("signup.businessType")}</legend>
            <Controller
              name="business_type"
              control={control}
              rules={{ validate: (v) => step !== 2 || Boolean(v) || t("common.required") }}
              render={({ field }) => (
                <ChoiceGroup value={field.value} onValueChange={field.onChange} className="grid-cols-1 sm:grid-cols-2" aria-label={t("signup.businessType")}>
                  {TYPES.map(({ key, icon: Icon }) => (
                    <Choice key={key} value={key} label={t(`signup.types.${key}`)} icon={<Icon aria-hidden="true" />} />
                  ))}
                </ChoiceGroup>
              )}
            />
            {errors.business_type && (
              <p className="text-[13px] font-medium text-danger" role="alert">
                {errors.business_type.message}
              </p>
            )}
          </fieldset>
          <Field label={t("signup.teamSize")}>
            <Select {...register("team_size")}>
              {SIZES.map((s) => (
                <option key={s} value={s}>
                  {t(`signup.sizes.${s}`)}
                </option>
              ))}
            </Select>
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("signup.country")} optional={t("common.optional")}>
              <Select {...register("country")}>
                <option value="">–</option>
                {countryOptions().map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("signup.timezone")} error={errors.timezone?.message}>
              <Select {...register("timezone", required)}>
                {timezoneOptions().map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <p className="text-xs text-muted">{t("signup.terms")}</p>
          <div className="flex gap-2">
            <Button size="lg" onClick={() => setStep(1)}>
              {t("common.back")}
            </Button>
            <Button type="submit" variant="primary" size="lg" className="flex-1" loading={formState.isSubmitting}>
              {t("signup.create")}
            </Button>
          </div>
        </div>
      </form>
    </AuthLayout>
  );
}

export default function SignupPage() {
  return (
    <PublicOnly>
      <SignupForm />
    </PublicOnly>
  );
}
