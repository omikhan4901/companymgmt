"use client";

import { useMutation } from "@tanstack/react-query";
import { Languages, Minimize2, PenLine, Sparkles, Wand2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@/components/ui/menu";
import { errorMessage } from "@/lib/errors";

import { useAIStatus } from "./ai";

type Task = "draft" | "improve" | "shorter" | "translate";
type Kind = "announcement" | "task" | "document" | "message" | "general";

/** Helps with the text in a field: draft from notes, improve, shorten, translate. The
 * result replaces the field's text, where the person can still edit or undo it. */
export function WriteHelp({ kind, getText, setText }: { kind: Kind; getText: () => string; setText: (text: string) => void }) {
  const { t } = useTranslation();
  const status = useAIStatus();
  const run = useMutation({
    mutationFn: (v: { task: Task; language?: "en" | "bn" }) =>
      api<{ text: string }>("/v1/ai/write", { method: "POST", body: { ...v, kind, text: getText() } }),
    onSuccess: (r) => {
      setText(r.text);
      toast.success(t("ai.writeDone"));
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const s = status.data;
  if (!s || !s.available || !s.enabled || !s.can_use || !s.features.includes("writing")) return null;
  const go = (task: Task, language?: "en" | "bn") => {
    if (!getText().trim()) {
      toast.error(t("ai.writeEmpty"));
      return;
    }
    run.mutate({ task, language });
  };
  return (
    <Menu>
      <MenuTrigger asChild>
        <Button type="button" size="sm" variant="ghost" className="self-start" loading={run.isPending}>
          {!run.isPending && <Sparkles aria-hidden="true" />}
          {t("ai.writeHelp")}
        </Button>
      </MenuTrigger>
      <MenuContent align="start">
        <MenuItem onSelect={() => go("draft")}>
          <PenLine aria-hidden="true" />
          {t("ai.writeTasks.draft")}
        </MenuItem>
        <MenuItem onSelect={() => go("improve")}>
          <Wand2 aria-hidden="true" />
          {t("ai.writeTasks.improve")}
        </MenuItem>
        <MenuItem onSelect={() => go("shorter")}>
          <Minimize2 aria-hidden="true" />
          {t("ai.writeTasks.shorter")}
        </MenuItem>
        <MenuItem onSelect={() => go("translate", "bn")}>
          <Languages aria-hidden="true" />
          {t("ai.writeTasks.toBangla")}
        </MenuItem>
        <MenuItem onSelect={() => go("translate", "en")}>
          <Languages aria-hidden="true" />
          {t("ai.writeTasks.toEnglish")}
        </MenuItem>
      </MenuContent>
    </Menu>
  );
}

/** "Summarise" on a document the person can open: the main points, in their language. */
export function DocumentSummary({ documentId }: { documentId: string }) {
  const { t } = useTranslation();
  const status = useAIStatus();
  const summary = useMutation({
    mutationFn: () => api<{ text: string }>(`/v1/ai/documents/${documentId}/summary`, { method: "POST" }),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const s = status.data;
  if (!s || !s.available || !s.enabled || !s.can_use || !s.features.includes("documents")) return null;
  if (summary.data) {
    return (
      <div className="flex flex-col gap-2 rounded-xl border border-border bg-surface-2/60 p-4">
        <span className="flex items-center gap-2 text-sm font-medium">
          <Sparkles className="size-4 text-accent-soft-text" aria-hidden="true" />
          {t("ai.summary")}
        </span>
        <p className="whitespace-pre-wrap text-sm leading-relaxed">{summary.data.text}</p>
        <p className="text-xs text-muted">{t("ai.summaryNote")}</p>
      </div>
    );
  }
  return (
    <Button className="self-start" loading={summary.isPending} onClick={() => summary.mutate()}>
      {!summary.isPending && <Sparkles aria-hidden="true" />}
      {t("ai.summarise")}
    </Button>
  );
}
