import { Alert, Button, Form, Input } from "antd";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { api } from "@/api/client";
import { useSession } from "@/auth/session";
import { applyFieldErrors, errorMessage } from "@/lib/errors";

import AuthLayout from "./AuthLayout";

export default function ChangePassword() {
  const { t } = useTranslation();
  const { reload } = useSession();
  const navigate = useNavigate();
  const [form] = Form.useForm<{ current_password: string; new_password: string }>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (values: { current_password: string; new_password: string }) => {
    setBusy(true);
    setError(null);
    try {
      await api("/v1/auth/password/change", { body: values });
      await reload();
      navigate("/", { replace: true });
    } catch (e) {
      if (!applyFieldErrors(form, e)) setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout title={t("auth.mustChangeTitle")} sub={t("auth.mustChangeSub")}>
      {error ? <Alert type="error" title={error} className="mb-4" showIcon /> : null}
      <Form form={form} layout="vertical" onFinish={submit} requiredMark={false}>
        <Form.Item name="current_password" label={t("auth.currentPassword")} rules={[{ required: true }]}>
          <Input.Password autoComplete="current-password" size="large" />
        </Form.Item>
        <Form.Item name="new_password" label={t("auth.newPassword")} extra={t("auth.passwordHelp")} rules={[{ required: true, min: 8 }]}>
          <Input.Password autoComplete="new-password" size="large" />
        </Form.Item>
        <Button type="primary" htmlType="submit" block size="large" loading={busy}>
          {t("common.save")}
        </Button>
      </Form>
    </AuthLayout>
  );
}
