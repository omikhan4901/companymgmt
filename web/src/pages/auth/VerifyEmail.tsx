import { Alert, Button, Spin } from "antd";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router";

import { api } from "@/api/client";
import { useSession } from "@/auth/session";
import { errorMessage } from "@/lib/errors";

import AuthLayout from "./AuthLayout";

export default function VerifyEmail() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const { reload } = useSession();
  const [state, setState] = useState<"working" | "ok" | "failed">("working");
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    api("/v1/auth/email/verify", { body: { token: params.get("token") ?? "" } })
      .then(async () => {
        setState("ok");
        await reload();
      })
      .catch((e: unknown) => {
        setError(errorMessage(e));
        setState("failed");
      });
  }, [params, reload]);

  return (
    <AuthLayout title={t("auth.verifyTitle")}>
      {state === "working" ? (
        <div className="grid place-items-center py-6" role="status">
          <Spin />
        </div>
      ) : (
        <>
          <Alert type={state === "ok" ? "success" : "error"} title={state === "ok" ? t("auth.verified") : (error ?? t("auth.verifyFailed"))} showIcon className="mb-4" />
          <Link to="/">
            <Button type="primary" block size="large">
              {t("auth.goToApp")}
            </Button>
          </Link>
        </>
      )}
    </AuthLayout>
  );
}
