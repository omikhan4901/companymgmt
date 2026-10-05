"use client";

import { useMutation } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Choice, ChoiceGroup } from "@/components/ui/choice";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Textarea } from "@/components/ui/input";
import { errorMessage } from "@/lib/errors";

type Topic = "question" | "problem" | "idea";

/** "Contact support" from any screen: the page you're on goes with the message. */
export function SupportDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { t } = useTranslation();
  const page = usePathname();
  const [topic, setTopic] = useState<Topic>("question");
  const [message, setMessage] = useState("");
  const send = useMutation({
    mutationFn: () => api<{ reference: string }>("/v1/support", { body: { topic, message: message.trim(), page } }),
    onSuccess: (r) => {
      toast.success(t("support.sent", { reference: r.reference }));
      setMessage("");
      onOpenChange(false);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={t("support.title")}
        description={t("support.sub")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={() => onOpenChange(false)}>{t("common.cancel")}</Button>
            <Button variant="primary" disabled={message.trim().length < 5} loading={send.isPending} onClick={() => send.mutate()}>
              {t("support.send")}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <ChoiceGroup value={topic} onValueChange={(v) => setTopic(v as Topic)} className="grid-cols-3" aria-label={t("support.topic")}>
            {(["question", "problem", "idea"] as const).map((k) => (
              <Choice key={k} value={k} label={t(`support.topics.${k}`)} />
            ))}
          </ChoiceGroup>
          <Field label={t("support.message")} help={t("support.messageHelp")}>
            <Textarea rows={6} maxLength={4000} value={message} onChange={(e) => setMessage(e.target.value)} />
          </Field>
        </div>
      </DialogContent>
    </Dialog>
  );
}
