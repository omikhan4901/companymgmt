"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import { useSession } from "@/auth/session";
import { AuthLayout } from "@/components/auth-layout";
import { Alert } from "@/components/ui/alert";
import { PageLoading } from "@/components/ui/spinner";
import { errorMessage } from "@/lib/errors";
import { safeNext } from "@/lib/nav";

/** The company's sign-in provider sends people back here with a one-time code. */
function Callback() {
  const { t } = useTranslation();
  const params = useSearchParams();
  const router = useRouter();
  const { signIn } = useSession();
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const code = params.get("code");
    const state = params.get("state");
    const denied = params.get("error_description") ?? params.get("error");
    if (denied || !code || !state) {
      setError(denied ?? t("sso.missing"));
      return;
    }
    // Don't leave the one-time code in the address bar or history.
    window.history.replaceState(null, "", "/sso/callback");
    api<{ access_token: string; next: string | null }>("/v1/sso/callback", { body: { code, state }, headers: { "x-cm-client": "web" } })
      .then(async (result) => {
        await signIn({ access_token: result.access_token });
        router.replace(safeNext(result.next));
      })
      .catch((e: unknown) => setError(errorMessage(e)));
  }, [params, router, signIn, t]);
  if (!error) return <PageLoading />;
  return (
    <AuthLayout title={t("sso.failedTitle")}>
      <Alert tone="error" className="mb-5">
        {error}
      </Alert>
      <Link href="/login" className="text-sm font-semibold text-accent-soft-text hover:underline">
        {t("sso.backToSignIn")}
      </Link>
    </AuthLayout>
  );
}

export default function SsoCallbackPage() {
  return (
    <Suspense fallback={<PageLoading />}>
      <Callback />
    </Suspense>
  );
}
