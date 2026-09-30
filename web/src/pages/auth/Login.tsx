import { Alert, Button, Form, Input, Segmented } from "antd";
import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useSearchParams } from "react-router";

import { api, ApiError } from "@/api/client";
import type { LoginResult, Token } from "@/api/types";
import { useSession } from "@/auth/session";
import Turnstile, { captchaAvailable } from "@/components/Turnstile";
import { currentLang } from "@/i18n";
import { errorMessage } from "@/lib/errors";

import AuthLayout from "./AuthLayout";

interface Credentials {
  email?: string;
  workspace?: string;
  username?: string;
  password: string;
}

function safeNext(next: string | null): string {
  // Only same-site paths, never "//host" or "http://…".
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

export default function Login() {
  const { t } = useTranslation();
  const { signIn } = useSession();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [mode, setMode] = useState<"email" | "staff">(params.get("workspace") ? "staff" : "email");
  const [challenge, setChallenge] = useState<string | null>(null);
  const [useRecovery, setUseRecovery] = useState(false);
  const [needCaptcha, setNeedCaptcha] = useState(false);
  const [captchaToken, setCaptchaToken] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const onToken = useCallback((token: string) => setCaptchaToken(token), []);

  const done = async (token: Token | LoginResult) => {
    await signIn({ access_token: token.access_token ?? "" });
    navigate(safeNext(params.get("next")), { replace: true });
  };

  const submit = async (values: Credentials) => {
    setBusy(true);
    setError(null);
    try {
      const body =
        mode === "email"
          ? { email: values.email, password: values.password }
          : { workspace: values.workspace?.trim().toLowerCase(), username: values.username?.trim(), password: values.password };
      const result = await api<LoginResult>("/v1/auth/login", { body: { ...body, captcha_token: captchaToken } });
      if (result.mfa_required) setChallenge(result.challenge);
      else await done(result);
    } catch (e) {
      if (e instanceof ApiError && e.code === "captcha_required") {
        setNeedCaptcha(true);
        setError(captchaAvailable ? t("auth.captcha") : errorMessage(e));
      } else setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const verify = async (values: { code?: string; recovery_code?: string }) => {
    setBusy(true);
    setError(null);
    try {
      const token = await api<Token>("/v1/auth/mfa/verify", { body: { challenge, ...values } });
      await done(token);
    } catch (e) {
      if (e instanceof ApiError && e.code === "challenge_expired") setChallenge(null);
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  if (challenge) {
    return (
      <AuthLayout title={t("auth.mfaTitle")} sub={t("auth.mfaSub")}>
        {error ? <Alert type="error" title={error} className="mb-4" showIcon /> : null}
        <Form layout="vertical" onFinish={verify} requiredMark={false}>
          {useRecovery ? (
            <Form.Item name="recovery_code" label={t("auth.recoveryCode")} rules={[{ required: true }]}>
              <Input autoFocus autoComplete="off" size="large" />
            </Form.Item>
          ) : (
            <Form.Item name="code" label={t("auth.mfaCode")} rules={[{ required: true, pattern: /^\s*\d{6}\s*$/ }]}>
              <Input autoFocus inputMode="numeric" autoComplete="one-time-code" maxLength={6} size="large" className="tabular tracking-widest" />
            </Form.Item>
          )}
          <Button type="primary" htmlType="submit" block size="large" loading={busy}>
            {t("auth.verify")}
          </Button>
        </Form>
        <Button type="link" className="mt-3 px-0" onClick={() => setUseRecovery(!useRecovery)}>
          {useRecovery ? t("auth.useCode") : t("auth.useRecovery")}
        </Button>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title={t("auth.signInTitle")}
      sub={t("auth.signInSub")}
      footer={
        <>
          {t("auth.noAccount")}{" "}
          <Link to="/signup" className="font-semibold text-brand hover:underline">
            {t("auth.signUp")}
          </Link>
        </>
      }
    >
      <Segmented
        block
        value={mode}
        onChange={(v) => setMode(v as "email" | "staff")}
        options={[
          { label: t("auth.withEmail"), value: "email" },
          { label: t("auth.withUsername"), value: "staff" },
        ]}
        className="mb-5"
      />
      {error ? <Alert type="error" title={error} className="mb-4" showIcon /> : null}
      <Form layout="vertical" onFinish={submit} requiredMark={false} initialValues={{ workspace: params.get("workspace") ?? "" }}>
        {mode === "email" ? (
          <Form.Item name="email" label={t("auth.email")} rules={[{ required: true, type: "email" }]}>
            <Input autoComplete="email" inputMode="email" size="large" autoFocus />
          </Form.Item>
        ) : (
          <>
            <Form.Item name="workspace" label={t("auth.workspaceCode")} extra={t("auth.workspaceCodeHelp")} rules={[{ required: true }]}>
              <Input autoComplete="organization" size="large" autoCapitalize="none" />
            </Form.Item>
            <Form.Item name="username" label={t("auth.username")} rules={[{ required: true }]}>
              <Input autoComplete="username" size="large" autoCapitalize="none" />
            </Form.Item>
          </>
        )}
        <Form.Item name="password" label={t("auth.password")} rules={[{ required: true }]}>
          <Input.Password autoComplete="current-password" size="large" />
        </Form.Item>
        {needCaptcha && captchaAvailable ? <Turnstile onToken={onToken} language={currentLang()} /> : null}
        <Button type="primary" htmlType="submit" block size="large" loading={busy}>
          {t("auth.signIn")}
        </Button>
      </Form>
      {mode === "email" ? (
        <Link to="/forgot-password" className="mt-4 inline-block text-sm text-brand hover:underline">
          {t("auth.forgot")}
        </Link>
      ) : null}
    </AuthLayout>
  );
}
