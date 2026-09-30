import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Form, Input, Spin } from "antd";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useSearchParams } from "react-router";

import { api } from "@/api/client";
import type { Token } from "@/api/types";
import { useSession } from "@/auth/session";
import { applyFieldErrors, errorMessage } from "@/lib/errors";

import AuthLayout from "./AuthLayout";

interface Lookup {
  workspace: string;
  email: string;
  name: string | null;
  account_exists: boolean;
}

export default function Invite() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const { signedIn, me, signIn } = useSession();
  const navigate = useNavigate();
  const [form] = Form.useForm<{ name: string; password: string }>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lookup = useQuery({
    queryKey: ["invite", token],
    queryFn: () => api<Lookup>("/v1/invites/lookup", { query: { token } }),
    retry: false,
  });

  const accept = async (values?: { name: string; password: string }) => {
    setBusy(true);
    setError(null);
    try {
      const result = await api<Token>("/v1/invites/accept", { body: { token, ...(values ?? {}) } });
      await signIn(result);
      navigate("/", { replace: true });
    } catch (e) {
      if (!applyFieldErrors(form, e)) setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  if (lookup.isPending) {
    return (
      <AuthLayout title="…">
        <div className="grid place-items-center py-6" role="status">
          <Spin />
        </div>
      </AuthLayout>
    );
  }
  if (lookup.isError) {
    return (
      <AuthLayout title={t("errors.notFound")}>
        <Alert type="error" title={errorMessage(lookup.error)} showIcon />
      </AuthLayout>
    );
  }
  const invite = lookup.data;
  const sameUser = signedIn && me?.email?.toLowerCase() === invite.email.toLowerCase();

  return (
    <AuthLayout title={invite.workspace} sub={invite.email}>
      {error ? <Alert type="error" title={error} className="mb-4" showIcon /> : null}
      {invite.account_exists ? (
        sameUser ? (
          <Button type="primary" block size="large" loading={busy} onClick={() => void accept()}>
            {t("common.continue")}
          </Button>
        ) : (
          <Link to={`/login?next=${encodeURIComponent(`/invite?token=${token}`)}`}>
            <Button type="primary" block size="large">
              {t("auth.signIn")}
            </Button>
          </Link>
        )
      ) : (
        <Form form={form} layout="vertical" onFinish={accept} requiredMark={false} initialValues={{ name: invite.name ?? "" }}>
          <Form.Item name="name" label={t("signup.yourName")} rules={[{ required: true, whitespace: true }]}>
            <Input autoComplete="name" size="large" />
          </Form.Item>
          <Form.Item name="password" label={t("auth.password")} extra={t("auth.passwordHelp")} rules={[{ required: true, min: 8 }]}>
            <Input.Password autoComplete="new-password" size="large" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block size="large" loading={busy}>
            {t("common.continue")}
          </Button>
        </Form>
      )}
    </AuthLayout>
  );
}
