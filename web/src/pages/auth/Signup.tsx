import { Alert, Button, Form, Input, Select, Steps } from "antd";
import { Briefcase, Coffee, Factory, HelpCircle, Store, UtensilsCrossed } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";

import { api } from "@/api/client";
import type { Token } from "@/api/types";
import { useSession } from "@/auth/session";
import { currentLang, setLanguage, type Lang } from "@/i18n";
import { applyFieldErrors, errorMessage } from "@/lib/errors";
import { browserTimezone, countryOptions, guessCountry, timezoneOptions } from "@/lib/places";

import AuthLayout from "./AuthLayout";

const TYPES: { key: string; icon: LucideIcon }[] = [
  { key: "shop", icon: Coffee },
  { key: "restaurant", icon: UtensilsCrossed },
  { key: "retail", icon: Store },
  { key: "office", icon: Briefcase },
  { key: "factory", icon: Factory },
  { key: "other", icon: HelpCircle },
];
const SIZES = ["1", "2-5", "6-20", "21-100", "100+"];

interface Values {
  name: string;
  email: string;
  password: string;
  business_name: string;
  business_type: string;
  team_size: string;
  country?: string;
  timezone: string;
}

export default function Signup() {
  const { t } = useTranslation();
  const { signIn } = useSession();
  const navigate = useNavigate();
  const [form] = Form.useForm<Values>();
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const type = Form.useWatch("business_type", form);

  const chooseLanguage = (lang: Lang) => {
    setLanguage(lang);
    setStep(1);
  };

  const next = async () => {
    await form.validateFields(["name", "email", "password"]);
    setStep(2);
  };

  const submit = async () => {
    const values = await form.validateFields();
    setBusy(true);
    setError(null);
    try {
      const token = await api<Token>("/v1/auth/signup", { body: { ...form.getFieldsValue(true), ...values, locale: currentLang() } });
      await signIn(token);
      navigate("/", { replace: true });
    } catch (e) {
      if (applyFieldErrors(form, e)) {
        const fields = form.getFieldsError().filter((f) => f.errors.length).map((f) => String(f.name[0]));
        if (fields.some((f) => ["name", "email", "password"].includes(f))) setStep(1);
      } else setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout
      title={t("auth.signUp")}
      footer={
        <>
          {t("auth.haveAccount")}{" "}
          <Link to="/login" className="font-semibold text-brand hover:underline">
            {t("auth.signIn")}
          </Link>
        </>
      }
    >
      <Steps
        size="small"
        current={step}
        className="mb-6"
        items={[{ title: t("signup.stepLanguage") }, { title: t("signup.stepAccount") }, { title: t("signup.stepBusiness") }]}
      />
      {error ? <Alert type="error" title={error} className="mb-4" showIcon /> : null}

      {step === 0 ? (
        <div>
          <p className="mb-4 font-medium text-ink">{t("signup.chooseLanguage")}</p>
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
                onClick={() => chooseLanguage(lang)}
                className="rounded-2xl border-2 border-slate-200 px-4 py-6 text-lg font-semibold text-ink transition hover:border-brand hover:bg-brand-50"
                lang={lang}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <Form
        form={form}
        layout="vertical"
        requiredMark={false}
        initialValues={{ timezone: browserTimezone(), country: guessCountry(), team_size: "2-5", business_type: undefined }}
        className={step === 0 ? "hidden" : ""}
      >
        <div className={step === 1 ? "" : "hidden"}>
          <Form.Item name="name" label={t("signup.yourName")} rules={[{ required: true, whitespace: true, max: 120 }]}>
            <Input autoComplete="name" size="large" />
          </Form.Item>
          <Form.Item name="email" label={t("auth.email")} rules={[{ required: true, type: "email" }]}>
            <Input autoComplete="email" inputMode="email" size="large" />
          </Form.Item>
          <Form.Item name="password" label={t("auth.password")} extra={t("auth.passwordHelp")} rules={[{ required: true, min: 8, max: 128 }]}>
            <Input.Password autoComplete="new-password" size="large" />
          </Form.Item>
          <div className="flex gap-2">
            <Button size="large" onClick={() => setStep(0)}>
              {t("common.back")}
            </Button>
            <Button type="primary" size="large" block onClick={() => void next()}>
              {t("common.next")}
            </Button>
          </div>
        </div>

        <div className={step === 2 ? "" : "hidden"}>
          <Form.Item name="business_name" label={t("signup.businessName")} rules={[{ required: step === 2, whitespace: true, max: 120 }]}>
            <Input autoComplete="organization" size="large" />
          </Form.Item>
          <Form.Item name="business_type" label={t("signup.businessType")} rules={[{ required: step === 2 }]}>
            <div role="radiogroup" aria-label={t("signup.businessType")} className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {TYPES.map(({ key, icon: Icon }) => (
                <button
                  key={key}
                  type="button"
                  role="radio"
                  aria-checked={type === key}
                  onClick={() => form.setFieldValue("business_type", key)}
                  className={`flex min-h-24 flex-col items-center justify-center gap-2 rounded-xl border-2 p-3 text-center text-sm font-medium transition ${
                    type === key ? "border-brand bg-brand-50 text-ink" : "border-slate-200 text-slate-700 hover:border-brand-200"
                  }`}
                >
                  <Icon size={22} className={type === key ? "text-brand" : "text-slate-500"} aria-hidden="true" />
                  {t(`signup.types.${key}`)}
                </button>
              ))}
            </div>
          </Form.Item>
          <Form.Item name="team_size" label={t("signup.teamSize")}>
            <Select size="large" options={SIZES.map((s) => ({ value: s, label: t(`signup.sizes.${s}`) }))} />
          </Form.Item>
          <div className="grid gap-x-3 sm:grid-cols-2">
            <Form.Item name="country" label={t("signup.country")}>
              <Select size="large" showSearch optionFilterProp="label" options={countryOptions()} allowClear />
            </Form.Item>
            <Form.Item name="timezone" label={t("signup.timezone")} rules={[{ required: step === 2 }]}>
              <Select size="large" showSearch optionFilterProp="label" options={timezoneOptions()} />
            </Form.Item>
          </div>
          <p className="mb-4 text-xs text-slate-500">{t("signup.terms")}</p>
          <div className="flex gap-2">
            <Button size="large" onClick={() => setStep(1)}>
              {t("common.back")}
            </Button>
            <Button type="primary" size="large" block loading={busy} onClick={() => void submit()}>
              {t("signup.create")}
            </Button>
          </div>
        </div>
      </Form>
    </AuthLayout>
  );
}
