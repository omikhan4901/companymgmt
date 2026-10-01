"use client";

import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { ApiError, api } from "@/api/client";
import { departmentOptions, useDepartments, useRoles } from "@/api/hooks";
import type { DocDetail } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Choice, ChoiceGroup, Switch } from "@/components/ui/choice";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { applyFieldErrors, errorMessage } from "@/lib/errors";

import { CATEGORIES, uploadVersion, useRefreshDocs } from "./data";

type Visibility = "everyone" | "roles" | "departments";

interface Values {
  title: string;
  description: string;
  category: string;
}

export function fileError(e: unknown, t: (k: string) => string): string {
  if (e instanceof ApiError && ["file_type", "file_too_large", "file_empty", "too_large"].includes(e.code)) {
    return t(`docs.errors.${e.code === "too_large" ? "file_too_large" : e.code}`);
  }
  return errorMessage(e);
}

/** Publish a document (details, who sees it, and its first file), or edit one. */
export function DocumentDialog({ doc, onClose, onSaved }: { doc?: DocDetail; onClose: () => void; onSaved?: (id: string) => void }) {
  const { t } = useTranslation();
  const refresh = useRefreshDocs();
  const roles = useRoles();
  const departments = useDepartments();
  const [visibility, setVisibility] = useState<Visibility>(doc?.visibility ?? "everyone");
  const [targets, setTargets] = useState<string[]>(doc?.visibility_names.map((v) => v.id) ?? []);
  const [ack, setAck] = useState(doc?.requires_ack ?? false);
  const [file, setFile] = useState<File | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  // Created but the upload failed: a retry only uploads, it doesn't publish twice.
  const created = useRef<DocDetail | null>(null);
  const { register, handleSubmit, setError, formState } = useForm<Values>({
    defaultValues: { title: doc?.title ?? "", description: doc?.description ?? "", category: doc?.category ?? "policy" },
  });
  const choices =
    visibility === "roles"
      ? (roles.data ?? []).filter((r) => r.key !== "owner").map((r) => ({ value: r.id, label: r.name }))
      : departmentOptions(departments.data).map((d) => ({ value: d.value, label: d.label.trim() }));

  const save = useMutation({
    mutationFn: async (v: Values) => {
      const body = {
        title: v.title.trim(),
        description: v.description.trim() || null,
        category: v.category,
        visibility,
        visibility_ids: visibility === "everyone" ? [] : targets,
        requires_ack: ack,
      };
      const saved = doc
        ? await api<DocDetail>(`/v1/documents/${doc.id}`, { method: "PATCH", body, version: doc.version })
        : (created.current ?? (created.current = await api<DocDetail>("/v1/documents", { body })));
      if (file) await uploadVersion(saved.id, file);
      return saved;
    },
    onSuccess: (saved) => {
      toast.success(doc ? t("common.saved") : t("docs.published"));
      void refresh();
      onSaved?.(saved.id);
      onClose();
    },
    onError: (e) => {
      void refresh();
      if (!applyFieldErrors(setError, ["title", "description", "category"], e)) setProblem(fileError(e, t));
    },
  });
  const submit = handleSubmit((v) => {
    setProblem(null);
    if (visibility !== "everyone" && targets.length === 0) return setProblem(t("news.chooseAudience"));
    if (!doc && !file) return setProblem(t("docs.chooseFile"));
    save.mutate(v);
  });

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={doc ? t("docs.edit") : t("docs.new")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" type="submit" form="doc-form" loading={save.isPending}>
              {doc ? t("common.save") : t("docs.publish")}
            </Button>
          </>
        }
      >
        <form id="doc-form" onSubmit={(e) => void submit(e)} className="flex flex-col gap-4" noValidate>
          <Field label={t("docs.titleLabel")} error={formState.errors.title?.message}>
            <Input dir="auto" maxLength={200} {...register("title", { validate: (v) => v.trim().length > 0 || t("common.required") })} />
          </Field>
          <Field label={t("docs.description")} optional={t("common.optional")}>
            <Textarea dir="auto" rows={3} maxLength={5000} {...register("description")} />
          </Field>
          <Field label={t("docs.category")}>
            <Select {...register("category")}>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {t(`docs.categories.${c}`)}
                </option>
              ))}
            </Select>
          </Field>
          {!doc && (
            <Field label={t("docs.file")} help={t("docs.fileHelp")}>
              <Input type="file" accept=".pdf,.docx,.xlsx,.pptx,.odt,.png,.jpg,.jpeg,.txt,.md,.csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </Field>
          )}
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 text-sm font-medium">{t("docs.who")}</legend>
            <ChoiceGroup
              value={visibility}
              onValueChange={(v) => {
                setVisibility(v as Visibility);
                setTargets([]);
              }}
              className="sm:grid-cols-3"
              aria-label={t("docs.who")}
            >
              {(["everyone", "roles", "departments"] as const).map((k) => (
                <Choice key={k} value={k} label={t(`docs.visibility.${k}`)} />
              ))}
            </ChoiceGroup>
            {visibility !== "everyone" && (
              <ul className="mt-1 max-h-44 overflow-y-auto rounded-xl border border-border p-1" aria-label={t(`docs.visibility.${visibility}`)}>
                {choices.map((c) => (
                  <li key={c.value}>
                    <label className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm hover:bg-surface-2">
                      <input
                        type="checkbox"
                        className="size-4 accent-[var(--color-accent)]"
                        checked={targets.includes(c.value)}
                        onChange={() => setTargets((x) => (x.includes(c.value) ? x.filter((i) => i !== c.value) : [...x, c.value]))}
                      />
                      {c.label}
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </fieldset>
          <label className="flex items-center justify-between gap-4 text-sm">
            <span className="flex flex-col">
              {t("docs.askAck")}
              <span className="text-[13px] text-muted">{t("docs.askAckHelp")}</span>
            </span>
            <Switch checked={ack} onCheckedChange={setAck} aria-label={t("docs.askAck")} />
          </label>
          {problem && (
            <p className="text-[13px] font-medium text-danger" role="alert">
              {problem}
            </p>
          )}
        </form>
      </DialogContent>
    </Dialog>
  );
}
