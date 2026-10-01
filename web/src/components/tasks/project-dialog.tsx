"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import { departmentOptions, useDepartments } from "@/api/hooks";
import type { Employee, Page, Project } from "@/api/types";
import { useSession } from "@/auth/session";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { cn } from "@/lib/cn";
import { applyFieldErrors, errorMessage } from "@/lib/errors";
import { formatNumber } from "@/lib/format";

import { useRefreshTasks } from "./data";

export const PROJECT_COLORS = ["#6d28d9", "#b4235a", "#0f766e", "#b45309", "#4d7c0f", "#475569"];
const COLOR_NAMES = ["plum", "rose", "teal", "amber", "olive", "slate"];

interface Values {
  name: string;
  description: string;
  department_id: string;
  color: string;
  due_date: string;
}

function MemberPicker({ value, onChange }: { value: string[]; onChange: (ids: string[]) => void }) {
  const { t } = useTranslation();
  const [filter, setFilter] = useState("");
  const people = useQuery({
    queryKey: ["people", { status: "active", limit: 200 }],
    queryFn: () => api<Page<Employee>>("/v1/people", { query: { status: "active", limit: 200 } }),
  });
  const shown = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return (people.data?.items ?? []).filter((p) => !q || p.full_name.toLowerCase().includes(q));
  }, [people.data, filter]);
  const toggle = (id: string) => onChange(value.includes(id) ? value.filter((x) => x !== id) : [...value, id]);
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-1 text-sm font-medium">
        {t("tasks.members")} <span className="font-normal text-muted">({formatNumber(value.length)})</span>
      </legend>
      <Input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder={t("tasks.findPeople")} aria-label={t("tasks.findPeople")} />
      <ul className="max-h-52 overflow-y-auto rounded-xl border border-border p-1">
        {shown.map((p) => (
          <li key={p.id}>
            <label className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm hover:bg-surface-2">
              <input type="checkbox" className="size-4 accent-[var(--color-accent)]" checked={value.includes(p.id)} onChange={() => toggle(p.id)} />
              {p.full_name}
            </label>
          </li>
        ))}
        {shown.length === 0 && <li className="px-2 py-3 text-sm text-muted">{t("tasks.noPeople")}</li>}
      </ul>
    </fieldset>
  );
}

/** Create a project, or edit one (`project` given). */
export function ProjectDialog({ project, onClose, onSaved }: { project?: Project; onClose: () => void; onSaved?: (p: Project) => void }) {
  const { t } = useTranslation();
  const { workspace } = useSession();
  const refresh = useRefreshTasks();
  const departments = useDepartments();
  const scoped = !!workspace?.scope_department_id;
  const [members, setMembers] = useState<string[]>(project?.members.map((m) => m.id) ?? []);
  const { register, handleSubmit, setError, setValue, control, formState } = useForm<Values>({
    defaultValues: {
      name: project?.name ?? "",
      description: project?.description ?? "",
      department_id: project?.department_id ?? (scoped ? (workspace?.scope_department_id ?? "") : ""),
      color: project?.color ?? PROJECT_COLORS[0],
      due_date: project?.due_date ?? "",
    },
  });
  const color = useWatch({ control, name: "color" });
  const save = useMutation({
    mutationFn: (v: Values) => {
      const body = {
        name: v.name.trim(),
        description: v.description.trim() || null,
        department_id: v.department_id || null,
        color: v.color,
        due_date: v.due_date || null,
        member_ids: members,
      };
      return project
        ? api<Project>(`/v1/projects/${project.id}`, { method: "PATCH", body, version: project.version })
        : api<Project>("/v1/projects", { body });
    },
    onSuccess: (saved) => {
      toast.success(t("common.saved"));
      void refresh();
      onSaved?.(saved);
      onClose();
    },
    onError: (e) => {
      if (!applyFieldErrors(setError, ["name", "description", "department_id", "due_date"], e)) toast.error(errorMessage(e));
    },
  });
  const archive = useMutation({
    mutationFn: (status: "active" | "archived") => api(`/v1/projects/${project?.id}`, { method: "PATCH", body: { status }, version: project?.version }),
    onSuccess: () => {
      void refresh();
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={project ? t("tasks.editProject") : t("tasks.newProject")}
        closeLabel={t("common.close")}
        footer={
          <>
            {project && (
              <Button variant="ghost" className="mr-auto" loading={archive.isPending} onClick={() => archive.mutate(project.status === "active" ? "archived" : "active")}>
                {project.status === "active" ? t("tasks.archive") : t("tasks.unarchive")}
              </Button>
            )}
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" type="submit" form="project-form" loading={save.isPending}>
              {project ? t("common.save") : t("tasks.createProject")}
            </Button>
          </>
        }
      >
        <form id="project-form" onSubmit={handleSubmit((v) => save.mutate(v))} className="flex flex-col gap-4" noValidate>
          <Field label={t("common.name")} error={formState.errors.name?.message}>
            <Input dir="auto" maxLength={120} {...register("name", { validate: (v) => v.trim().length > 0 || t("common.required") })} />
          </Field>
          <Field label={t("tasks.description")} optional={t("common.optional")}>
            <Textarea rows={3} maxLength={5000} {...register("description")} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("tasks.homeDepartment")} help={t("tasks.homeDepartmentHelp")} error={formState.errors.department_id?.message}>
              <Select {...register("department_id")}>
                {!scoped && <option value="">{t("tasks.noDepartment")}</option>}
                {departmentOptions(departments.data).map((d) => (
                  <option key={d.value} value={d.value}>
                    {d.label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("tasks.due")} optional={t("common.optional")}>
              <Input type="date" {...register("due_date")} />
            </Field>
          </div>
          <fieldset>
            <legend className="mb-2 text-sm font-medium">{t("tasks.color")}</legend>
            <div className="flex gap-2">
              {PROJECT_COLORS.map((c, i) => (
                <button
                  key={c}
                  type="button"
                  aria-label={t(`tasks.colors.${COLOR_NAMES[i]}`)}
                  aria-pressed={color === c}
                  onClick={() => setValue("color", c)}
                  className={cn("size-8 rounded-full ring-offset-2 ring-offset-surface", color === c && "ring-2 ring-text")}
                  style={{ background: c }}
                />
              ))}
            </div>
          </fieldset>
          <MemberPicker value={members} onChange={setMembers} />
        </form>
      </DialogContent>
    </Dialog>
  );
}
