"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock, MonitorSmartphone, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import { useSession, useWorkspace } from "@/auth/session";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, EmptyState } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { errorMessage } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";

const TILL_KEY = "cm_till";
const TILL_SESSION = "cm_till_session";

/** The till secret this browser keeps (only on registered tills). */
export function tillToken(): string | null {
  try {
    return window.localStorage.getItem(TILL_KEY);
  } catch {
    return null;
  }
}

function keepTillToken(token: string | null) {
  try {
    if (token) window.localStorage.setItem(TILL_KEY, token);
    else window.localStorage.removeItem(TILL_KEY);
  } catch {
    // Storage blocked: the till won't be remembered.
  }
}

export function markTillSession(on: boolean) {
  try {
    if (on) window.sessionStorage.setItem(TILL_SESSION, "1");
    else window.sessionStorage.removeItem(TILL_SESSION);
  } catch {
    // Ignore.
  }
}

export function isTillSession(): boolean {
  try {
    return window.sessionStorage.getItem(TILL_SESSION) === "1";
  } catch {
    return false;
  }
}

interface TillRow {
  id: string;
  name: string;
  hint: string;
  last_seen_at: string | null;
  revoked: boolean;
  token: string | null;
}

/** Sales → Tills (managers): register this browser as a shared till, see and revoke tills. */
export function Tills() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { timezone } = useWorkspace();
  const tills = useQuery({ queryKey: ["tills"], queryFn: () => api<TillRow[]>("/v1/sales/tills") });
  const [name, setName] = useState("");
  const [here, setHere] = useState(() => (typeof window === "undefined" ? null : tillToken()));
  const register = useMutation({
    mutationFn: () => api<TillRow>("/v1/sales/tills", { method: "POST", body: { name: name.trim() } }),
    onSuccess: (till) => {
      keepTillToken(till.token);
      setHere(till.token);
      setName("");
      toast.success(t("tills.registered", { name: till.name }));
      void queryClient.invalidateQueries({ queryKey: ["tills"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const revoke = useMutation({
    mutationFn: (id: string) => api(`/v1/sales/tills/${id}`, { method: "DELETE" }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["tills"] }),
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <p className="text-sm text-muted">{t("tills.intro")}</p>
      <Card className="flex flex-wrap items-end gap-3 p-4">
        {here ? (
          <p className="flex-1 text-sm">{t("tills.thisIsATill")}</p>
        ) : (
          <>
            <Field label={t("tills.name")} className="min-w-56 flex-1">
              <Input value={name} maxLength={80} onChange={(e) => setName(e.target.value)} placeholder={t("tills.namePlaceholder")} />
            </Field>
            <Button variant="primary" disabled={!name.trim()} loading={register.isPending} onClick={() => register.mutate()}>
              <MonitorSmartphone aria-hidden="true" />
              {t("tills.register")}
            </Button>
          </>
        )}
        {here && (
          <Button
            variant="ghost"
            onClick={() => {
              keepTillToken(null);
              setHere(null);
            }}
          >
            {t("tills.forget")}
          </Button>
        )}
      </Card>
      {!tills.data?.length ? (
        <EmptyState icon={<MonitorSmartphone />} title={t("tills.none")} />
      ) : (
        <ul className="flex flex-col gap-2">
          {tills.data.map((till) => (
            <li key={till.id}>
              <Card className="flex items-center gap-3 px-4 py-3">
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="font-medium">{till.name}</span>
                  <span className="text-xs text-muted">{till.last_seen_at ? t("tills.lastSeen", { when: formatDateTime(till.last_seen_at, timezone) }) : t("tills.notYet")}</span>
                </span>
                {till.revoked ? (
                  <Badge>{t("tills.revoked")}</Badge>
                ) : (
                  <Button variant="ghost" size="iconSm" aria-label={`${t("tills.revoke")}: ${till.name}`} onClick={() => revoke.mutate(till.id)}>
                    <Trash2 aria-hidden="true" />
                  </Button>
                )}
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Account → Till PIN (people who sell). */
export function TillPin() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const status = useQuery({ queryKey: ["my-pin"], queryFn: () => api<{ has_pin: boolean }>("/v1/sales/my-pin") });
  const [pin, setPin] = useState("");
  const save = useMutation({
    mutationFn: () => api("/v1/sales/my-pin", { method: "PUT", body: { pin } }),
    onSuccess: () => {
      setPin("");
      toast.success(t("common.saved"));
      void queryClient.invalidateQueries({ queryKey: ["my-pin"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Card>
      <CardHeader title={t("tills.pinTitle")} sub={status.data?.has_pin ? t("tills.pinSet") : t("tills.pinHelp")} />
      <div className="flex flex-wrap items-end gap-2 p-5 pt-4">
        <Field label={status.data?.has_pin ? t("tills.newPin") : t("tills.pin")} help={t("tills.pinRules")} className="w-48">
          <Input inputMode="numeric" autoComplete="off" maxLength={8} value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))} />
        </Field>
        <Button loading={save.isPending} disabled={pin.length < 4} onClick={() => save.mutate()}>
          {t("common.save")}
        </Button>
      </div>
    </Card>
  );
}

/** On a till: hand it to the next cashier. */
export function LockTill() {
  const { t } = useTranslation();
  const { signOut } = useSession();
  const router = useRouter();
  const [show] = useState(() => typeof window !== "undefined" && isTillSession() && tillToken() !== null);
  if (!show) return null;
  return (
    <Button
      onClick={async () => {
        markTillSession(false);
        await signOut();
        router.replace("/till");
      }}
    >
      <Lock aria-hidden="true" />
      {t("tills.lock")}
    </Button>
  );
}
