import { Alert, Button, Form, Input } from "antd";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { api } from "@/api/client";
import { errorMessage } from "@/lib/errors";

import AuthLayout from "./AuthLayout";

export default function Forgot() {
  const { t } = useTranslation();
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async ({ email }: { email: string }) => {
    setBusy(true);
    setError(null);
    try {
      await api("/v1/auth/password/forgot", { body: { email } });
      setSent(true);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout
      title={t("auth.forgotTitle")}
      sub={t("auth.forgotSub")}
      footer={
        <Link to="/login" className="font-semibold text-brand hover:underline">
          {t("auth.signIn")}
        </Link>
      }
    >
      {sent ? (
        <Alert type="success" title={t("auth.linkSent")} showIcon />
      ) : (
        <>
          {error ? <Alert type="error" title={error} className="mb-4" showIcon /> : null}
          <Form layout="vertical" onFinish={submit} requiredMark={false}>
            <Form.Item name="email" label={t("auth.email")} rules={[{ required: true, type: "email" }]}>
              <Input autoComplete="email" inputMode="email" size="large" autoFocus />
            </Form.Item>
            <Button type="primary" htmlType="submit" block size="large" loading={busy}>
              {t("auth.sendLink")}
            </Button>
          </Form>
        </>
      )}
    </AuthLayout>
  );
}
