"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import { useSession } from "@/auth/session";
import { AuthLayout } from "@/components/auth-layout";
import { markTillSession, tillToken } from "@/components/shop/tills";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { PageLoading } from "@/components/ui/spinner";
import { errorMessage } from "@/lib/errors";

interface TillInfo {
  till: string;
  workspace: string;
  cashiers: { membership_id: string; name: string }[];
}

const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "⌫"];

/** A shared till: pick your name, type your PIN. */
export default function TillPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const { signIn } = useSession();
  const [token] = useState(() => (typeof window === "undefined" ? null : tillToken()));
  const info = useQuery({
    queryKey: ["till", token],
    queryFn: () => api<TillInfo>("/v1/till", { headers: { "x-till-token": token ?? "" } }),
    enabled: !!token,
    retry: false,
  });
  const [who, setWho] = useState<string | null>(null);
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const unlock = async (value: string) => {
    if (!who || !token) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api<{ access_token: string }>("/v1/till/unlock", {
        body: { membership_id: who, pin: value },
        headers: { "x-till-token": token, "x-cm-client": "web" },
      });
      markTillSession(true);
      await signIn({ access_token: result.access_token });
      router.replace("/app/pos");
    } catch (e) {
      setError(errorMessage(e));
      setPin("");
      setBusy(false);
    }
  };

  const press = (key: string) => {
    if (busy) return;
    if (key === "⌫") setPin((p) => p.slice(0, -1));
    else if (key && pin.length < 8) setPin((p) => p + key);
  };

  if (!token)
    return (
      <AuthLayout title={t("tills.notATill")} sub={t("tills.notATillSub")}>
        <Link href="/login" className="text-sm font-semibold text-accent-soft-text hover:underline">
          {t("auth.signIn")}
        </Link>
      </AuthLayout>
    );
  if (info.isPending) return <PageLoading />;
  if (info.isError)
    return (
      <AuthLayout title={t("tills.notATill")}>
        <Alert tone="error">{errorMessage(info.error)}</Alert>
      </AuthLayout>
    );
  const chosen = info.data.cashiers.find((c) => c.membership_id === who);
  return (
    <AuthLayout title={info.data.till} sub={info.data.workspace}>
      {error && (
        <Alert tone="error" className="mb-4">
          {error}
        </Alert>
      )}
      {!chosen ? (
        info.data.cashiers.length ? (
          <ul className="grid grid-cols-2 gap-2" aria-label={t("tills.whoAreYou")}>
            {info.data.cashiers.map((c) => (
              <li key={c.membership_id}>
                <Button size="lg" className="w-full" onClick={() => setWho(c.membership_id)}>
                  {c.name}
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">{t("tills.noCashiers")}</p>
        )
      ) : (
        <form
          className="flex flex-col items-center gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            void unlock(pin);
          }}
        >
          <p className="text-sm">{t("tills.pinFor", { name: chosen.name })}</p>
          <output aria-live="polite" className="font-display text-3xl tracking-[0.5em]">
            {"•".repeat(pin.length) || " "}
          </output>
          <div className="grid w-64 grid-cols-3 gap-2">
            {KEYS.map((key, i) =>
              key ? (
                <Button key={key} type="button" size="lg" variant="ghost" className="h-14 text-xl" aria-label={key === "⌫" ? t("tills.delete") : key} onClick={() => press(key)}>
                  {key}
                </Button>
              ) : (
                <span key={`gap-${i}`} />
              ),
            )}
          </div>
          <div className="flex w-64 gap-2">
            <Button type="button" className="flex-1" onClick={() => (setWho(null), setPin(""))}>
              {t("common.back")}
            </Button>
            <Button type="submit" variant="primary" className="flex-1" loading={busy} disabled={pin.length < 4}>
              {t("tills.unlock")}
            </Button>
          </div>
        </form>
      )}
    </AuthLayout>
  );
}
