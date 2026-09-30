import { Alert, Button, Form, Input } from "antd";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router";

import { api } from "@/api/client";
import { applyFieldErrors, errorMessage } from "@/lib/errors";

import AuthLayout from "./AuthLayout";

export default function Reset() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const [form] = Form.useForm<{ password: string }>();
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async ({ password }: { password: string }) => {
    setBusy(true);
    setError(null);
    try {
      await api("/v1/auth/password/reset", { body: { token: params.get("token") ?? "", password } });
      setDone(true);
    } catch (e) {
      if (!applyFieldErrors(form, e)) setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout title={t("auth.resetTitle")}>
      {done ? (
        <>
          <Alert type="success" title={t("auth.passwordUpdated")} showIcon className="mb-4" />
          <Link to="/login">
            <Button type="primary" block size="large">
              {t("auth.signIn")}
            </Button>
          </Link>
        </>
      ) : (
        <>
          {error ? (
            <Alert
              type="error"
              title={error}
              className="mb-4"
              showIcon
              action={
                <Link to="/forgot-password" className="text-sm font-semibold text-brand">
                  {t("auth.sendLink")}
                </Link>
              }
            />
          ) : null}
          <Form form={form} layout="vertical" onFinish={submit} requiredMark={false}>
            <Form.Item name="password" label={t("auth.newPassword")} extra={t("auth.passwordHelp")} rules={[{ required: true, min: 8 }]}>
              <Input.Password autoComplete="new-password" size="large" autoFocus />
            </Form.Item>
            <Button type="primary" htmlType="submit" block size="large" loading={busy}>
              {t("common.save")}
            </Button>
          </Form>
        </>
      )}
    </AuthLayout>
  );
}
