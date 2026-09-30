"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import { useSession } from "@/auth/session";
import { AuthLayout } from "@/components/auth-layout";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { errorMessage } from "@/lib/errors";

export default function VerifyEmailPage() {
  const { t } = useTranslation();
  const params = useSearchParams();
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
        <div className="grid place-items-center py-6 text-muted" role="status">
          <Spinner />
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <Alert tone={state === "ok" ? "success" : "error"}>{state === "ok" ? t("auth.verified") : (error ?? t("auth.verifyFailed"))}</Alert>
          <Button asChild variant="primary" size="lg">
            <Link href="/app">{t("auth.goToApp")}</Link>
          </Button>
        </div>
      )}
    </AuthLayout>
  );
}
