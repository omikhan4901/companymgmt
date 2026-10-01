"use client";

import { useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, api } from "@/api/client";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { PasswordInput } from "@/components/ui/password";
import { errorMessage } from "@/lib/errors";

/**
 * Runs an action; if the server asks the person to confirm who they are first, asks for
 * the password, then retries. Returns the runner and the dialog to render.
 */
export function useStepUp(): [<T>(action: () => Promise<T>) => Promise<T>, ReactNode] {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const pending = useRef<{ resolve: () => void; reject: (e: unknown) => void } | null>(null);

  const run = async <T,>(action: () => Promise<T>): Promise<T> => {
    try {
      return await action();
    } catch (e) {
      if (!(e instanceof ApiError && e.code === "reauth_required")) throw e;
      await new Promise<void>((resolve, reject) => {
        pending.current = { resolve, reject: () => reject(e) };
        setPassword("");
        setError(null);
        setOpen(true);
      });
      return action();
    }
  };

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await api("/v1/auth/reauth", { body: { password } });
      setOpen(false);
      pending.current?.resolve();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const cancel = () => {
    setOpen(false);
    pending.current?.reject(null);
  };

  const dialog = (
    <Dialog open={open} onOpenChange={(o) => !o && cancel()}>
      <DialogContent
        title={t("account.confirmIt")}
        description={t("account.confirmSub")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={cancel}>{t("common.cancel")}</Button>
            <Button variant="primary" type="submit" form="stepup-form" loading={busy}>
              {t("common.continue")}
            </Button>
          </>
        }
      >
        <form
          id="stepup-form"
          onSubmit={(e) => {
            e.preventDefault();
            void confirm();
          }}
          className="flex flex-col gap-3"
        >
          {error && <Alert tone="error">{error}</Alert>}
          <Field label={t("auth.password")}>
            <PasswordInput autoFocus autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
        </form>
      </DialogContent>
    </Dialog>
  );
  return [run, dialog];
}
