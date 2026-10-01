"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, Pencil, Plus, Rocket, Trash2 } from "lucide-react";
import { useState } from "react";
import { useFieldArray, useForm, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { Employee, OnboardingRun, OnboardingTemplate, Page } from "@/api/types";
import { useSession } from "@/auth/session";
import { useLibrary } from "@/components/documents/data";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, EmptyState } from "@/components/ui/card";
import { Switch } from "@/components/ui/choice";
import { ConfirmDialog } from "@/components/ui/confirm";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { applyFieldErrors, errorMessage } from "@/lib/errors";
import { formatDay, formatNumber } from "@/lib/format";

import { taskKeys, useRefreshTasks } from "./data";

export const onboardingKeys = {
  templates: ["tasks", "onboarding", "templates"] as const,
  runs: (mine: boolean) => ["tasks", "onboarding", "runs", mine] as const,
};

export function useTemplates(enabled = true) {
  return useQuery({ queryKey: onboardingKeys.templates, queryFn: () => api<OnboardingTemplate[]>("/v1/onboarding/templates"), enabled });
}

export function useRuns(mine = false, enabled = true) {
  return useQuery({ queryKey: onboardingKeys.runs(mine), queryFn: () => api<OnboardingRun[]>("/v1/onboarding/runs", { query: { mine } }), enabled });
}

interface Item {
  title: string;
  who: "joiner" | "manager";
  due_days: string;
  document_id: string;
}

interface Values {
  name: string;
  automatic: boolean;
  items: Item[];
}

const BLANK: Item = { title: "", who: "joiner", due_days: "0", document_id: "" };

function asItem(raw: Record<string, unknown>): Item {
  return {
    title: String(raw.title ?? ""),
    who: raw.who === "manager" ? "manager" : "joiner",
    due_days: String(raw.due_days ?? 0),
    document_id: raw.document_id ? String(raw.document_id) : "",
  };
}

/** Create a checklist, or edit one (`template` given). */
export function TemplateDialog({ template, onClose }: { template?: OnboardingTemplate; onClose: () => void }) {
  const { t } = useTranslation();
  const { hasModule } = useSession();
  const queryClient = useQueryClient();
  const docs = useLibrary(false, hasModule("documents"));
  const [deleting, setDeleting] = useState(false);
  const { register, control, handleSubmit, setError, setValue, formState } = useForm<Values>({
    defaultValues: {
      name: template?.name ?? "",
      automatic: template?.automatic ?? false,
      items: template?.items.length ? template.items.map(asItem) : [{ ...BLANK }],
    },
  });
  const items = useFieldArray({ control, name: "items" });
  const automatic = useWatch({ control, name: "automatic" });
  const done = () => {
    void queryClient.invalidateQueries({ queryKey: onboardingKeys.templates });
    onClose();
  };
  const save = useMutation({
    mutationFn: (v: Values) => {
      const body = {
        name: v.name.trim(),
        automatic: v.automatic,
        items: v.items
          .filter((i) => i.title.trim())
          .map((i) => ({ title: i.title.trim(), who: i.who, due_days: Number(i.due_days) || 0, document_id: i.document_id || null })),
      };
      return template ? api(`/v1/onboarding/templates/${template.id}`, { method: "PUT", body }) : api("/v1/onboarding/templates", { body });
    },
    onSuccess: () => {
      toast.success(t("common.saved"));
      done();
    },
    onError: (e) => {
      if (!applyFieldErrors(setError, ["name"], e)) toast.error(errorMessage(e));
    },
  });
  const remove = useMutation({
    mutationFn: () => api(`/v1/onboarding/templates/${template?.id}`, { method: "DELETE" }),
    onSuccess: done,
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={template ? t("onboarding.editTemplate") : t("onboarding.newTemplate")}
        closeLabel={t("common.close")}
        className="sm:w-[min(720px,calc(100vw-32px))]"
        footer={
          <>
            {template && (
              <Button variant="ghost" className="mr-auto text-danger-text" onClick={() => setDeleting(true)}>
                <Trash2 aria-hidden="true" />
                {t("onboarding.deleteTemplate")}
              </Button>
            )}
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" type="submit" form="template-form" loading={save.isPending}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <form id="template-form" onSubmit={handleSubmit((v) => save.mutate(v))} className="flex flex-col gap-4" noValidate>
          <Field label={t("common.name")} error={formState.errors.name?.message}>
            <Input dir="auto" maxLength={120} placeholder={t("onboarding.namePlaceholder")} {...register("name", { validate: (v) => v.trim().length > 0 || t("common.required") })} />
          </Field>
          <label className="flex items-start gap-3 text-sm">
            <Switch checked={automatic} onCheckedChange={(v) => setValue("automatic", v)} aria-label={t("onboarding.automatic")} aria-describedby="automatic-help" />
            <span className="flex flex-col gap-0.5">
              <span className="font-medium">{t("onboarding.automatic")}</span>
              <span id="automatic-help" className="text-muted">
                {t("onboarding.automaticHelp")}
              </span>
            </span>
          </label>
          <fieldset className="flex flex-col gap-3">
            <legend className="mb-1 text-sm font-medium">{t("onboarding.items")}</legend>
            <ol className="flex flex-col gap-3">
              {items.fields.map((field, i) => (
                <li key={field.id} className="flex flex-col gap-3 rounded-xl border border-border p-3">
                  <div className="flex items-end gap-2">
                    <Field label={t("onboarding.itemTitle", { n: formatNumber(i + 1) })} className="flex-1">
                      <Input dir="auto" maxLength={200} placeholder={t("onboarding.itemPlaceholder")} {...register(`items.${i}.title`)} />
                    </Field>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={t("onboarding.removeItem", { n: formatNumber(i + 1) })}
                      disabled={items.fields.length === 1}
                      onClick={() => items.remove(i)}
                    >
                      <Trash2 aria-hidden="true" />
                    </Button>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-3">
                    <Field label={t("onboarding.who")}>
                      <Select {...register(`items.${i}.who`)}>
                        <option value="joiner">{t("onboarding.whoJoiner")}</option>
                        <option value="manager">{t("onboarding.whoManager")}</option>
                      </Select>
                    </Field>
                    <Field label={t("onboarding.dueDays")}>
                      <Input type="number" inputMode="numeric" min={0} max={365} {...register(`items.${i}.due_days`)} />
                    </Field>
                    {hasModule("documents") && (
                      <Field label={t("onboarding.document")}>
                        <Select {...register(`items.${i}.document_id`)}>
                          <option value="">{t("onboarding.noDocument")}</option>
                          {(docs.data ?? []).map((d) => (
                            <option key={d.id} value={d.id}>
                              {d.title}
                            </option>
                          ))}
                        </Select>
                      </Field>
                    )}
                  </div>
                </li>
              ))}
            </ol>
            {items.fields.length < 50 && (
              <Button className="w-fit" onClick={() => items.append({ ...BLANK })}>
                <Plus aria-hidden="true" />
                {t("onboarding.addItem")}
              </Button>
            )}
          </fieldset>
        </form>
        {template && (
          <ConfirmDialog
            open={deleting}
            title={t("onboarding.deleteTitle", { name: template.name })}
            confirmLabel={t("onboarding.deleteTemplate")}
            busy={remove.isPending}
            onConfirm={() => remove.mutate()}
            onClose={() => setDeleting(false)}
          >
            {t("onboarding.deleteBody")}
          </ConfirmDialog>
        )}
      </DialogContent>
    </Dialog>
  );
}

interface StartValues {
  employee_id: string;
  template_id: string;
  start_date: string;
}

export function StartDialog({ templates, onClose }: { templates: OnboardingTemplate[]; onClose: () => void }) {
  const { t } = useTranslation();
  const refresh = useRefreshTasks();
  const people = useQuery({
    queryKey: ["people", { status: "active", limit: 200 }],
    queryFn: () => api<Page<Employee>>("/v1/people", { query: { status: "active", limit: 200 } }),
  });
  const { register, handleSubmit, setError, formState } = useForm<StartValues>({
    defaultValues: { employee_id: "", template_id: templates[0]?.id ?? "", start_date: "" },
  });
  const start = useMutation({
    mutationFn: (v: StartValues) => api<OnboardingRun>("/v1/onboarding/runs", { body: { employee_id: v.employee_id, template_id: v.template_id, start_date: v.start_date || null } }),
    onSuccess: (run) => {
      toast.success(t("onboarding.started", { name: run.employee_name }));
      void refresh();
      onClose();
    },
    onError: (e) => {
      if (!applyFieldErrors(setError, ["employee_id", "template_id", "start_date"], e)) toast.error(errorMessage(e));
    },
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={t("onboarding.start")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" type="submit" form="start-form" loading={start.isPending}>
              {t("onboarding.startButton")}
            </Button>
          </>
        }
      >
        <form id="start-form" onSubmit={handleSubmit((v) => start.mutate(v))} className="flex flex-col gap-4" noValidate>
          <Field label={t("onboarding.person")} error={formState.errors.employee_id?.message}>
            <Select {...register("employee_id", { required: t("common.required") })}>
              <option value="">{t("onboarding.choosePerson")}</option>
              {(people.data?.items ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.full_name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("onboarding.checklist")} error={formState.errors.template_id?.message}>
            <Select {...register("template_id", { required: t("common.required") })}>
              {templates.map((tpl) => (
                <option key={tpl.id} value={tpl.id}>
                  {tpl.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("onboarding.startDate")} optional={t("common.optional")} help={t("onboarding.startDateHelp")} error={formState.errors.start_date?.message}>
            <Input type="date" {...register("start_date")} />
          </Field>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** "3 of 5 done" with a bar. */
export function RunProgress({ run }: { run: OnboardingRun }) {
  const { t } = useTranslation();
  const share = run.total ? Math.round((run.done / run.total) * 100) : 0;
  return (
    <span className="flex flex-col gap-1.5">
      <span className="flex justify-between gap-3 text-xs text-muted">
        <span>{t("onboarding.doneOf", { done: formatNumber(run.done), total: formatNumber(run.total) })}</span>
        {run.overdue > 0 && <span className="font-semibold text-danger-text">{t("tasks.overdueCount", { count: run.overdue, formatted: formatNumber(run.overdue) })}</span>}
      </span>
      <span className="h-1.5 overflow-hidden rounded-full bg-surface-2" role="img" aria-label={t("tasks.progress", { percent: formatNumber(share) })}>
        <span className="block h-full rounded-full bg-accent" style={{ width: `${share}%` }} />
      </span>
    </span>
  );
}

/** The Onboarding tab for managers: checklists to start from, and who's being onboarded. */
export function OnboardingTab() {
  const { t } = useTranslation();
  const { workspace } = useSession();
  const queryClient = useQueryClient();
  const templates = useTemplates();
  const runs = useRuns(false);
  const [editing, setEditing] = useState<OnboardingTemplate | "new" | null>(null);
  const [starting, setStarting] = useState(false);
  const canEdit = !workspace?.scope_department_id;
  if (templates.isPending || runs.isPending) {
    return (
      <div className="grid place-items-center py-16">
        <Spinner />
      </div>
    );
  }
  const list = templates.data ?? [];
  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
      <Card>
        <CardHeader
          title={t("onboarding.templates")}
          sub={t("onboarding.templatesSub")}
          action={
            canEdit ? (
              <Button size="sm" onClick={() => setEditing("new")}>
                <Plus aria-hidden="true" />
                {t("onboarding.newTemplate")}
              </Button>
            ) : undefined
          }
        />
        {list.length ? (
          <ul className="flex flex-col p-2 pt-3">
            {list.map((tpl) => (
              <li key={tpl.id} className="flex items-center gap-3 rounded-xl px-3 py-2.5">
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="truncate text-sm font-medium">{tpl.name}</span>
                  <span className="flex flex-wrap items-center gap-2 text-xs text-muted">
                    {t("onboarding.itemCount", { count: tpl.items.length, formatted: formatNumber(tpl.items.length) })}
                    {tpl.automatic && <Badge tone="accent">{t("onboarding.automaticBadge")}</Badge>}
                  </span>
                </span>
                {canEdit && (
                  <Button variant="ghost" size="icon" aria-label={t("onboarding.editNamed", { name: tpl.name })} onClick={() => setEditing(tpl)}>
                    <Pencil aria-hidden="true" />
                  </Button>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState icon={<ClipboardList />} title={t("onboarding.noTemplates")}>
            {canEdit ? t("onboarding.noTemplatesBody") : t("onboarding.noTemplatesScoped")}
          </EmptyState>
        )}
      </Card>
      <Card>
        <CardHeader
          title={t("onboarding.runs")}
          sub={t("onboarding.runsSub")}
          action={
            list.length ? (
              <Button size="sm" variant="primary" onClick={() => setStarting(true)}>
                <Rocket aria-hidden="true" />
                {t("onboarding.start")}
              </Button>
            ) : undefined
          }
        />
        {runs.data?.length ? (
          <ul className="flex flex-col gap-1 p-2 pt-3">
            {runs.data.map((run) => (
              <li key={run.id} className="flex flex-col gap-2 rounded-xl px-3 py-2.5">
                <span className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <span className="text-sm font-medium">{run.employee_name}</span>
                  <span className="text-xs text-muted">{t("onboarding.runMeta", { name: run.template_name, date: formatDay(run.start_date) })}</span>
                </span>
                <RunProgress run={run} />
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState icon={<Rocket />} title={t("onboarding.noRuns")}>
            {t("onboarding.noRunsBody")}
          </EmptyState>
        )}
      </Card>
      {editing && <TemplateDialog template={editing === "new" ? undefined : editing} onClose={() => setEditing(null)} />}
      {starting && (
        <StartDialog
          templates={list}
          onClose={() => {
            setStarting(false);
            void queryClient.invalidateQueries({ queryKey: taskKeys.all });
          }}
        />
      )}
    </div>
  );
}
