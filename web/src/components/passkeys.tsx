"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { browserSupportsWebAuthn, startAuthentication, startRegistration } from "@simplewebauthn/browser";
import { Fingerprint, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { ApiError, api } from "@/api/client";
import { useStepUp } from "@/components/step-up";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { errorMessage } from "@/lib/errors";
import { formatDay } from "@/lib/format";

interface PasskeyRow {
  id: string;
  name: string;
  created_at: string;
  last_used_at: string | null;
  backed_up: boolean;
}

interface Options {
  challenge_id: string;
  // The server's PublicKeyCredential*OptionsJSON.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  options: any;
}

function deviceName(): string {
  const ua = navigator.userAgent;
  if (/iPhone|iPad/.test(ua)) return "iPhone or iPad";
  if (/Android/.test(ua)) return "Android";
  if (/Mac/.test(ua)) return "Mac";
  if (/Windows/.test(ua)) return "Windows";
  return "Passkey";
}

/** Account → Passkeys. */
export function Passkeys() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [stepUp, stepUpDialog] = useStepUp();
  const [supported, setSupported] = useState(true);
  useEffect(() => setSupported(browserSupportsWebAuthn()), []);
  const list = useQuery({ queryKey: ["passkeys"], queryFn: () => api<PasskeyRow[]>("/v1/auth/passkeys") });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["passkeys"] });
  const add = useMutation({
    mutationFn: async () => {
      const options = await stepUp(() => api<Options>("/v1/auth/passkeys/register/options", { method: "POST" }));
      const credential = await startRegistration({ optionsJSON: options.options });
      return stepUp(() =>
        api("/v1/auth/passkeys/register", { body: { challenge_id: options.challenge_id, credential, name: deviceName() } }),
      );
    },
    onSuccess: () => {
      toast.success(t("passkeys.added"));
      refresh();
    },
    onError: (e) => {
      if (e instanceof Error && e.name === "NotAllowedError") return; // cancelled in the browser
      if (!(e instanceof ApiError && e.code === "reauth_required")) toast.error(errorMessage(e));
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => stepUp(() => api(`/v1/auth/passkeys/${id}`, { method: "DELETE" })),
    onSuccess: refresh,
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Card>
      <CardHeader title={t("passkeys.title")} sub={t("passkeys.sub")} action={<Fingerprint className="size-5 text-muted" aria-hidden="true" />} />
      <div className="flex flex-col gap-3 p-5 pt-4">
        {(list.data ?? []).map((p) => (
          <div key={p.id} className="flex items-center gap-3 rounded-xl border border-border px-3 py-2">
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="text-sm font-medium">{p.name}</span>
              <span className="text-xs text-muted">
                {t("passkeys.added_on", { date: formatDay(p.created_at.slice(0, 10)) })}
                {p.last_used_at && ` · ${t("passkeys.used_on", { date: formatDay(p.last_used_at.slice(0, 10)) })}`}
              </span>
            </span>
            {p.backed_up && <Badge>{t("passkeys.synced")}</Badge>}
            <Button variant="ghost" size="iconSm" aria-label={`${t("common.delete")}: ${p.name}`} onClick={() => remove.mutate(p.id)}>
              <Trash2 aria-hidden="true" />
            </Button>
          </div>
        ))}
        {supported ? (
          <Button className="self-start" loading={add.isPending} onClick={() => add.mutate()}>
            {t("passkeys.add")}
          </Button>
        ) : (
          <p className="text-sm text-muted">{t("passkeys.unsupported")}</p>
        )}
      </div>
      {stepUpDialog}
    </Card>
  );
}

/** Login → "Sign in with a passkey". */
export function PasskeySignIn({ onToken, workspace }: { onToken: (token: { access_token: string }) => Promise<void>; workspace?: string | null }) {
  const { t } = useTranslation();
  const [supported, setSupported] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setSupported(browserSupportsWebAuthn()), []);
  if (!supported) return null;
  const go = async () => {
    setBusy(true);
    setError(null);
    try {
      const options = await api<Options>("/v1/auth/passkeys/login/options", { method: "POST" });
      const credential = await startAuthentication({ optionsJSON: options.options });
      const token = await api<{ access_token: string }>("/v1/auth/passkeys/login", {
        body: { challenge_id: options.challenge_id, credential, workspace: workspace || null },
        headers: { "x-cm-client": "web" },
      });
      await onToken(token);
    } catch (e) {
      if (!(e instanceof Error && e.name === "NotAllowedError")) setError(errorMessage(e));
      setBusy(false);
    }
  };
  return (
    <div className="mt-3">
      {error && <p className="mb-2 text-sm text-danger-text">{error}</p>}
      <Button className="w-full" loading={busy} onClick={() => void go()}>
        <Fingerprint aria-hidden="true" />
        {t("passkeys.signIn")}
      </Button>
    </div>
  );
}
