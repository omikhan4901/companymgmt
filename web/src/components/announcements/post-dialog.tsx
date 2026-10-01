"use client";

import { useMutation } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import { departmentOptions, useBranches, useDepartments } from "@/api/hooks";
import type { Announcement } from "@/api/types";
import { useSession } from "@/auth/session";
import { Button } from "@/components/ui/button";
import { Choice, ChoiceGroup, Switch } from "@/components/ui/choice";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Textarea } from "@/components/ui/input";
import { applyFieldErrors, errorMessage } from "@/lib/errors";

import { useRefreshNews } from "./data";

type Audience = "everyone" | "branches" | "departments";

interface Values {
  title: string;
  body: string;
}

/** Write a post, or edit one (`post` given). */
export function PostDialog({ post, onClose }: { post?: Announcement; onClose: () => void }) {
  const { t } = useTranslation();
  const { workspace } = useSession();
  const refresh = useRefreshNews();
  const scope = workspace?.scope_department_id ?? null;
  const branches = useBranches(!scope);
  const departments = useDepartments();
  const [audience, setAudience] = useState<Audience>(post?.audience ?? (scope ? "departments" : "everyone"));
  const [targets, setTargets] = useState<string[]>(post?.audience_names.map((a) => a.id) ?? (scope ? [scope] : []));
  const [pinned, setPinned] = useState(post?.pinned ?? false);
  const [targetError, setTargetError] = useState<string | null>(null);
  const { register, handleSubmit, setError, formState } = useForm<Values>({ defaultValues: { title: post?.title ?? "", body: post?.body ?? "" } });

  // Scoped managers choose among their own department and the ones below it.
  const departmentChoices = useMemo(() => {
    const all = departmentOptions(departments.data);
    if (!scope || !departments.data) return all;
    const inside = new Set([scope]);
    let grew = true;
    while (grew) {
      grew = false;
      for (const d of departments.data) {
        if (d.parent_id && inside.has(d.parent_id) && !inside.has(d.id)) {
          inside.add(d.id);
          grew = true;
        }
      }
    }
    return all.filter((d) => inside.has(d.value));
  }, [departments.data, scope]);
  const choices = audience === "branches" ? (branches.data ?? []).map((b) => ({ value: b.id, label: b.name })) : departmentChoices;
  const kinds: Audience[] = scope ? ["departments"] : ["everyone", "branches", "departments"];

  const save = useMutation({
    mutationFn: (v: Values) => {
      const body = { title: v.title.trim(), body: v.body.trim(), audience, audience_ids: audience === "everyone" ? [] : targets, pinned };
      return post ? api(`/v1/announcements/${post.id}`, { method: "PATCH", body, version: post.version }) : api("/v1/announcements", { body });
    },
    onSuccess: () => {
      toast.success(post ? t("common.saved") : t("news.posted"));
      void refresh();
      onClose();
    },
    onError: (e) => {
      if (!applyFieldErrors(setError, ["title", "body"], e)) toast.error(errorMessage(e));
    },
  });
  const submit = handleSubmit((v) => {
    if (audience !== "everyone" && targets.length === 0) {
      setTargetError(t("news.chooseAudience"));
      return;
    }
    save.mutate(v);
  });

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={post ? t("news.editPost") : t("news.newPost")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" type="submit" form="post-form" loading={save.isPending}>
              {post ? t("common.save") : t("news.publish")}
            </Button>
          </>
        }
      >
        <form id="post-form" onSubmit={(e) => void submit(e)} className="flex flex-col gap-4" noValidate>
          <Field label={t("news.titleLabel")} error={formState.errors.title?.message}>
            <Input dir="auto" maxLength={200} {...register("title", { validate: (v) => v.trim().length > 0 || t("common.required") })} />
          </Field>
          <Field label={t("news.body")} error={formState.errors.body?.message}>
            <Textarea dir="auto" rows={6} maxLength={20000} {...register("body", { validate: (v) => v.trim().length > 0 || t("common.required") })} />
          </Field>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 text-sm font-medium">{t("news.audience")}</legend>
            <ChoiceGroup
              value={audience}
              onValueChange={(v) => {
                const k = v as Audience;
                setAudience(k);
                setTargets(k === "departments" && scope ? [scope] : []);
                setTargetError(null);
              }}
              className={kinds.length > 1 ? "sm:grid-cols-3" : undefined}
              aria-label={t("news.audience")}
            >
              {kinds.map((k) => (
                <Choice key={k} value={k} label={t(`news.audiences.${k}`)} />
              ))}
            </ChoiceGroup>
            {audience !== "everyone" && (
              <ul className="mt-1 max-h-48 overflow-y-auto rounded-xl border border-border p-1" aria-label={t(`news.audiences.${audience}`)}>
                {choices.map((c) => (
                  <li key={c.value}>
                    <label className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm hover:bg-surface-2">
                      <input
                        type="checkbox"
                        className="size-4 accent-[var(--color-accent)]"
                        checked={targets.includes(c.value)}
                        onChange={() => {
                          setTargetError(null);
                          setTargets((x) => (x.includes(c.value) ? x.filter((i) => i !== c.value) : [...x, c.value]));
                        }}
                      />
                      {c.label.trim()}
                    </label>
                  </li>
                ))}
              </ul>
            )}
            {audience === "departments" && <p className="text-[13px] text-muted">{t("news.departmentsHelp")}</p>}
            {targetError && (
              <p className="text-[13px] font-medium text-danger" role="alert">
                {targetError}
              </p>
            )}
          </fieldset>
          <label className="flex items-center justify-between gap-4 text-sm">
            {t("news.pinLabel")}
            <Switch checked={pinned} onCheckedChange={setPinned} />
          </label>
        </form>
      </DialogContent>
    </Dialog>
  );
}
