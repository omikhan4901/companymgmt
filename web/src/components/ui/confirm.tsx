"use client";

import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "./button";
import { Dialog, DialogContent } from "./dialog";

/** Asks before something destructive. Names the thing being changed in `title`. */
export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  onConfirm,
  onClose,
  busy,
}: {
  open: boolean;
  title: string;
  children?: ReactNode;
  confirmLabel: string;
  onConfirm: () => void;
  onClose: () => void;
  busy?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={title}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="danger" loading={busy} onClick={onConfirm}>
              {confirmLabel}
            </Button>
          </>
        }
      >
        {children && <div className="text-sm text-muted">{children}</div>}
      </DialogContent>
    </Dialog>
  );
}
