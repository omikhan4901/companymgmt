"use client";

import { useMutation } from "@tanstack/react-query";
import { useForm, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { ApiError, api } from "@/api/client";
import type { TaskDetail } from "@/api/types";
import { useSession } from "@/auth/session";
import { PeopleSelect } from "@/components/people-select";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { applyFieldErrors, errorMessage } from "@/lib/errors";

import { PRIORITIES, useProjects, useRefreshTasks } from "./data";

interface Values {
  title: string;
  project_id: string;
  assignee_id: string;
  due_date: string;
  priority: string;
  description: string;
}

/** A new task: on its own (for you, or someone you manage) or in a project. */
export function NewTaskDialog({ projectId, onClose, onCreated }: { projectId?: string; onClose: () => void; onCreated?: (id: string) => void }) {
  const { t } = useTranslation();
  const { can } = useSession();
  const refresh = useRefreshTasks();
  const projects = useProjects();
  const { register, handleSubmit, setError, control, formState } = useForm<Values>({
    defaultValues: { title: "", project_id: projectId ?? "", assignee_id: "", due_date: "", priority: "normal", description: "" },
  });
  const chosen = useWatch({ control, name: "project_id" });
  const project = projects.data?.find((p) => p.id === chosen);
  const save = useMutation({
    mutationFn: (v: Values) =>
      api<TaskDetail>("/v1/tasks", {
        body: {
          title: v.title.trim(),
          project_id: v.project_id || null,
          assignee_id: v.assignee_id || null,
          // In a project, "Nobody" means nobody; on its own, an empty choice means you.
          unassigned: !!v.project_id && !v.assignee_id,
          due_date: v.due_date || null,
          priority: v.priority,
          description: v.description.trim() || null,
        },
      }),
    onSuccess: (task) => {
      toast.success(t("tasks.created"));
      void refresh();
      onCreated?.(task.id);
      onClose();
    },
    onError: (e) => {
      if (e instanceof ApiError && ["not_a_member", "cannot_assign"].includes(e.code)) {
        setError("assignee_id", { message: t(`tasks.errors.${e.code}`) });
        return;
      }
      if (!applyFieldErrors(setError, ["title", "project_id", "assignee_id", "due_date", "priority", "description"], e)) toast.error(errorMessage(e));
    },
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={t("tasks.newTask")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" type="submit" form="task-form" loading={save.isPending}>
              {t("tasks.createTask")}
            </Button>
          </>
        }
      >
        <form id="task-form" onSubmit={handleSubmit((v) => save.mutate(v))} className="flex flex-col gap-4" noValidate>
          <Field label={t("tasks.titleLabel")} error={formState.errors.title?.message}>
            <Input dir="auto" maxLength={200} {...register("title", { validate: (v) => v.trim().length > 0 || t("common.required") })} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("tasks.project")}>
              <Select {...register("project_id")}>
                <option value="">{t("tasks.noProject")}</option>
                {(projects.data ?? []).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("tasks.assignee")} help={project || can("tasks.manage") ? undefined : t("tasks.forYou")} error={formState.errors.assignee_id?.message}>
              {project ? (
                <Select {...register("assignee_id")}>
                  <option value="">{t("tasks.nobody")}</option>
                  {project.members.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </Select>
              ) : can("tasks.manage") && can("people.view") ? (
                <PeopleSelect {...register("assignee_id")} emptyLabel={t("tasks.me")} />
              ) : (
                <Input value={t("tasks.me")} readOnly />
              )}
            </Field>
            <Field label={t("tasks.due")} optional={t("common.optional")}>
              <Input type="date" {...register("due_date")} />
            </Field>
            <Field label={t("tasks.priorityLabel")}>
              <Select {...register("priority")}>
                {PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {t(`tasks.priority.${p}`)}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <Field label={t("tasks.description")} optional={t("common.optional")}>
            <Textarea rows={3} maxLength={5000} {...register("description")} />
          </Field>
        </form>
      </DialogContent>
    </Dialog>
  );
}
