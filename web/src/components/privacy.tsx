"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, ShieldCheck, Trash2, Undo2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { ApiError, api, download } from "@/api/client";
import { useSession, useWorkspace } from "@/auth/session";
import { useStepUp } from "@/components/step-up";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Switch } from "@/components/ui/choice";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { errorMessage } from "@/lib/errors";
import { formatDay } from "@/lib/format";

function RequireMfa() {
  const { t } = useTranslation();
  const workspace = useWorkspace();
  const queryClient = useQueryClient();
  const save = useMutation({
    mutationFn: (on: boolean) => api("/v1/workspace", { method: "PATCH", body: { require_admin_mfa: on } }),
    onSuccess: () => {
      toast.success(t("common.saved"));
      void queryClient.invalidateQueries({ queryKey: ["me"] });
    },
    onError: (e) => toast.error(e instanceof ApiError && e.code === "mfa_required_first" ? t("privacy.requireMfaFirst") : errorMessage(e)),
  });
  return (
    <Card>
      <CardHeader title={t("privacy.requireMfa")} sub={t("privacy.requireMfaHelp")} action={<ShieldCheck className="size-5 text-muted" aria-hidden="true" />} />
      <div className="px-5 pb-5 pt-2">
        <label className="flex items-center justify-between gap-4 text-sm">
          {t("privacy.requireMfa")}
          <Switch checked={workspace.require_admin_mfa ?? false} disabled={save.isPending} onCheckedChange={(on) => save.mutate(on)} />
        </label>
      </div>
    </Card>
  );
}

function ExportCard() {
  const { t } = useTranslation();
  const [stepUp, dialog] = useStepUp();
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      await stepUp(() => download("/v1/privacy/workspace-export", {}, "workspace-export.zip"));
    } catch (e) {
      if (e !== null) toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card>
      <CardHeader title={t("privacy.exportTitle")} sub={t("privacy.exportBody")} />
      <div className="px-5 pb-5 pt-2">
        <Button onClick={() => void run()} loading={busy}>
          <Download aria-hidden="true" />
          {t("privacy.exportButton")}
        </Button>
      </div>
      {dialog}
    </Card>
  );
}

function DeleteCard() {
  const { t } = useTranslation();
  const workspace = useWorkspace();
  const { reload } = useSession();
  const [stepUp, stepUpDialog] = useStepUp();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const remove = useMutation({
    mutationFn: () => stepUp(() => api("/v1/workspace/delete", { body: { confirm_name: typed } })),
    onSuccess: () => {
      setOpen(false);
      void reload();
    },
    onError: (e) => {
      if (e !== null) toast.error(errorMessage(e));
    },
  });
  const matches = typed.trim().toLowerCase() === workspace.name.trim().toLowerCase();
  return (
    <Card className="border-danger-soft">
      <CardHeader title={t("privacy.deleteTitle")} sub={t("privacy.deleteBody")} />
      <div className="px-5 pb-5 pt-2">
        <Button variant="danger" onClick={() => setOpen(true)}>
          <Trash2 aria-hidden="true" />
          {t("privacy.deleteButton")}
        </Button>
      </div>
      <Dialog open={open} onOpenChange={(o) => !o && setOpen(false)}>
        <DialogContent
          title={t("privacy.deleteTitle")}
          description={t("privacy.deleteBody")}
          closeLabel={t("common.close")}
          footer={
            <>
              <Button onClick={() => setOpen(false)}>{t("common.cancel")}</Button>
              <Button variant="danger" disabled={!matches} loading={remove.isPending} onClick={() => remove.mutate()}>
                {t("privacy.deleteFinal")}
              </Button>
            </>
          }
        >
          <Field label={t("privacy.deleteConfirm", { name: workspace.name })}>
            <Input autoComplete="off" value={typed} onChange={(e) => setTyped(e.target.value)} />
          </Field>
        </DialogContent>
      </Dialog>
      {stepUpDialog}
    </Card>
  );
}

/** Settings → Data and security. */
export function WorkspaceData() {
  const { can } = useSession();
  return (
    <div className="grid max-w-3xl gap-4">
      {can("workspace.manage") && <RequireMfa />}
      {can("workspace.export") && <ExportCard />}
      {can("workspace.delete") && <DeleteCard />}
    </div>
  );
}

/** Account → Your data. */
export function MyData() {
  const { t } = useTranslation();
  const [stepUp, dialog] = useStepUp();
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      await stepUp(() => download("/v1/privacy/my-data", {}, "my-data.json"));
    } catch (e) {
      if (e !== null) toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card>
      <CardHeader title={t("privacy.myDataTitle")} sub={t("privacy.myDataBody")} />
      <div className="px-5 pb-5 pt-2">
        <Button onClick={() => void run()} loading={busy}>
          <Download aria-hidden="true" />
          {t("privacy.myDataButton")}
        </Button>
      </div>
      {dialog}
    </Card>
  );
}

/** Shown on the account page while the workspace waits to be purged. */
export function PendingDeletion() {
  const { t } = useTranslation();
  const { me, reload } = useSession();
  const [stepUp, dialog] = useStepUp();
  const restore = useMutation({
    mutationFn: () => stepUp(() => api("/v1/workspace/restore", { method: "POST" })),
    onSuccess: () => {
      toast.success(t("privacy.restored"));
      void reload();
    },
    onError: (e) => {
      if (e !== null) toast.error(errorMessage(e));
    },
  });
  const pending = me?.pending_deletion;
  if (!pending) return null;
  return (
    <>
      <Alert
        tone="warn"
        title={t("privacy.pendingTitle", { name: pending.name })}
        action={
          pending.can_restore ? (
            <Button size="sm" onClick={() => restore.mutate()} loading={restore.isPending}>
              <Undo2 aria-hidden="true" />
              {t("privacy.restore")}
            </Button>
          ) : undefined
        }
        className="mb-4"
      >
        {t("privacy.pendingBody", { date: formatDay(pending.purge_after.slice(0, 10), { weekday: "long" }) })}
        {!pending.can_restore && ` ${t("privacy.pendingOther")}`}
      </Alert>
      {dialog}
    </>
  );
}
