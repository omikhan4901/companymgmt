"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Send, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { ApiError, api } from "@/api/client";
import type { Project, TaskDetail } from "@/api/types";
import { useSession } from "@/auth/session";
import { PeopleSelect } from "@/components/people-select";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm";
import { Dialog, SheetContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { errorMessage } from "@/lib/errors";
import { formatAgo } from "@/lib/format";

import { PRIORITIES, STATUSES, taskKeys, useComments, useProject, useRefreshTasks, useTask } from "./data";

type Patch = Partial<{
  title: string;
  description: string | null;
  status: string;
  priority: string;
  assignee_id: string;
  unassigned: boolean;
  due_date: string;
  no_due_date: boolean;
}>;

function taskError(e: unknown, t: (k: string) => string): string {
  if (e instanceof ApiError && ["not_a_member", "cannot_assign"].includes(e.code)) return t(`tasks.errors.${e.code}`);
  if (e instanceof ApiError && e.status === 412) return t("tasks.errors.stale");
  return errorMessage(e);
}

/** `id` and `aria-*` come from the surrounding Field, which labels the control. */
function AssigneeField({ task, project, onChange, ...aria }: { task: TaskDetail; project: Project | undefined; onChange: (p: Patch) => void; id?: string; "aria-describedby"?: string }) {
  const { t } = useTranslation();
  const { can } = useSession();
  const value = task.assignee?.id ?? "";
  const change = (id: string) => onChange(id ? { assignee_id: id } : { unassigned: true });
  if (project) {
    return (
      <Select {...aria} value={value} onChange={(e) => change(e.target.value)}>
        <option value="">{t("tasks.nobody")}</option>
        {project.members.map((m) => (
          <option key={m.id} value={m.id}>
            {m.name}
          </option>
        ))}
      </Select>
    );
  }
  if (can("tasks.manage") && can("people.view")) {
    return <PeopleSelect {...aria} value={value} onChange={(e) => change(e.target.value)} emptyLabel={t("tasks.nobody")} />;
  }
  return <Input {...aria} value={task.assignee?.name ?? t("tasks.nobody")} readOnly />;
}

/** Ticks at once; the server catches up (and a failure puts it back on refresh). */
function ItemBox({ done, label, onChange }: { done: boolean; label: string; onChange: (done: boolean) => void }) {
  const [checked, setChecked] = useState(done);
  useEffect(() => setChecked(done), [done]);
  return (
    <input
      type="checkbox"
      className="size-4 accent-[var(--color-accent)]"
      checked={checked}
      aria-label={label}
      onChange={(e) => {
        setChecked(e.target.checked);
        onChange(e.target.checked);
      }}
    />
  );
}

function Checklist({ task, refresh }: { task: TaskDetail; refresh: () => void }) {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const base = `/v1/tasks/${task.id}/checklist`;
  const run = useMutation({
    mutationFn: (fn: () => Promise<unknown>) => fn(),
    onSuccess: refresh,
    onError: (e) => toast.error(errorMessage(e)),
  });
  const add = (e: FormEvent) => {
    e.preventDefault();
    const value = text.trim();
    if (!value) return;
    run.mutate(() => api(base, { body: { text: value } }));
    setText("");
  };
  return (
    <section aria-labelledby="checklist-title" className="flex flex-col gap-2">
      <h3 id="checklist-title" className="text-sm font-semibold">
        {t("tasks.checklist")}
      </h3>
      {task.checklist.length > 0 && (
        <ul className="flex flex-col gap-1">
          {task.checklist.map((item) => (
            <li key={item.id} className="group flex items-center gap-2 rounded-lg px-1 py-1 hover:bg-surface-2">
              <ItemBox
                done={item.done}
                label={item.text}
                onChange={(done) => run.mutate(() => api(`${base}/${item.id}`, { method: "PATCH", body: { done } }))}
              />
              <span className={item.done ? "flex-1 text-sm text-muted line-through" : "flex-1 text-sm"}>{item.text}</span>
              <button
                type="button"
                className="grid size-7 place-items-center rounded-md text-muted opacity-60 hover:bg-surface hover:text-text group-hover:opacity-100"
                aria-label={t("tasks.removeItem", { text: item.text })}
                onClick={() => run.mutate(() => api(`${base}/${item.id}`, { method: "DELETE" }))}
              >
                <X className="size-3.5" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={add} className="flex gap-2">
        <Input value={text} onChange={(e) => setText(e.target.value)} placeholder={t("tasks.addItem")} aria-label={t("tasks.addItem")} maxLength={300} />
        <Button type="submit" disabled={!text.trim()}>
          {t("common.add")}
        </Button>
      </form>
    </section>
  );
}

function Comments({ taskId, refresh }: { taskId: string; refresh: () => void }) {
  const { t } = useTranslation();
  const comments = useComments(taskId);
  const [body, setBody] = useState("");
  const send = useMutation({
    mutationFn: (text: string) => api(`/v1/tasks/${taskId}/comments`, { body: { body: text } }),
    onSuccess: () => {
      setBody("");
      void comments.refetch();
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/v1/tasks/${taskId}/comments/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      void comments.refetch();
      refresh();
    },
  });
  return (
    <section aria-labelledby="comments-title" className="flex flex-col gap-3">
      <h3 id="comments-title" className="text-sm font-semibold">
        {t("tasks.comments")}
      </h3>
      {(comments.data ?? []).length > 0 && (
        <ul className="flex flex-col gap-3">
          {comments.data?.map((c) => (
            <li key={c.id} className="flex gap-2.5">
              <Avatar name={c.author_name ?? "?"} className="size-7 text-[11px]" />
              <div className="min-w-0 flex-1 rounded-xl bg-surface-2 px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold">{c.author_name ?? t("notifications.someone")}</span>
                  <span className="text-xs text-muted">{formatAgo(c.created_at)}</span>
                </div>
                <p className="mt-0.5 whitespace-pre-wrap break-words text-sm">{c.body}</p>
                {c.mine && (
                  <button type="button" className="mt-1 text-xs text-muted underline-offset-2 hover:underline" onClick={() => remove.mutate(c.id)}>
                    {t("common.delete")}
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      <form
        className="flex items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (body.trim()) send.mutate(body.trim());
        }}
      >
        <Textarea value={body} onChange={(e) => setBody(e.target.value)} rows={2} placeholder={t("tasks.writeComment")} aria-label={t("tasks.writeComment")} maxLength={5000} />
        <Button type="submit" variant="primary" size="icon" loading={send.isPending} disabled={!body.trim()} aria-label={t("tasks.sendComment")}>
          <Send aria-hidden="true" />
        </Button>
      </form>
    </section>
  );
}

function Body({ task, onClose }: { task: TaskDetail; onClose: () => void }) {
  const { t } = useTranslation();
  const refresh = useRefreshTasks();
  const project = useProject(task.project_id ?? null);
  const [title, setTitle] = useState(task.title);
  const [description, setDescription] = useState(task.description ?? "");
  const [deleting, setDeleting] = useState(false);
  useEffect(() => setTitle(task.title), [task.title]);
  useEffect(() => setDescription(task.description ?? ""), [task.description]);

  // Edits go one after another, each with the version the previous one returned, so quick
  // changes (assignee, then priority, then date) don't trip over each other.
  const queryClient = useQueryClient();
  const version = useRef(task.version);
  const queue = useRef<Promise<void>>(Promise.resolve());
  useEffect(() => {
    version.current = Math.max(version.current, task.version);
  }, [task.version]);
  const save = {
    mutate: (patch: Patch) => {
      queue.current = queue.current.then(async () => {
        try {
          const saved = await api<TaskDetail>(`/v1/tasks/${task.id}`, { method: "PATCH", body: patch, version: version.current });
          version.current = saved.version;
          queryClient.setQueryData(taskKeys.task(task.id), saved);
        } catch (e) {
          toast.error(taskError(e, t));
        }
        await refresh();
      });
    },
  };
  const remove = useMutation({
    mutationFn: () => api(`/v1/tasks/${task.id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success(t("tasks.deleted"));
      onClose();
      void refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4">
        <Field label={t("tasks.titleLabel")}>
          <Input
            value={title}
            maxLength={200}
            onChange={(e) => setTitle(e.target.value)}
            onBlur={() => title.trim() && title.trim() !== task.title && save.mutate({ title: title.trim() })}
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("common.status")}>
            <Select value={task.status} onChange={(e) => save.mutate({ status: e.target.value })}>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {t(`tasks.status.${s}`)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("tasks.priorityLabel")}>
            <Select value={task.priority} onChange={(e) => save.mutate({ priority: e.target.value })}>
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {t(`tasks.priority.${p}`)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("tasks.assignee")}>
            <AssigneeField task={task} project={project.data} onChange={(p) => save.mutate(p)} />
          </Field>
          <Field label={t("tasks.due")}>
            <Input type="date" value={task.due_date ?? ""} onChange={(e) => save.mutate(e.target.value ? { due_date: e.target.value } : { no_due_date: true })} />
          </Field>
        </div>
        <Field label={t("tasks.description")} optional={t("common.optional")}>
          <Textarea
            value={description}
            rows={4}
            maxLength={5000}
            onChange={(e) => setDescription(e.target.value)}
            onBlur={() => description !== (task.description ?? "") && save.mutate({ description: description.trim() || null })}
          />
        </Field>
        {task.project_name && (
          <p className="text-sm text-muted">
            {t("tasks.inProject")} <span className="font-medium text-text">{task.project_name}</span>
            {task.created_by_name && ` · ${t("tasks.createdBy", { name: task.created_by_name })}`}
          </p>
        )}
      </div>
      <Checklist task={task} refresh={() => void refresh()} />
      <Comments taskId={task.id} refresh={() => void refresh()} />
      {task.can_delete && (
        <div className="border-t border-border pt-4">
          <Button variant="ghost" className="text-danger-text" onClick={() => setDeleting(true)}>
            <Trash2 aria-hidden="true" />
            {t("tasks.delete")}
          </Button>
        </div>
      )}
      <ConfirmDialog
        open={deleting}
        onClose={() => setDeleting(false)}
        title={t("tasks.deleteTitle", { title: task.title })}
        confirmLabel={t("tasks.delete")}
        busy={remove.isPending}
        onConfirm={() => remove.mutate()}
      >
        <p className="text-sm text-muted">{t("tasks.deleteBody")}</p>
      </ConfirmDialog>
    </div>
  );
}

/** The task panel: a side sheet on desktop, a bottom sheet on phones. */
export function TaskSheet({ taskId, onClose }: { taskId: string | null; onClose: () => void }) {
  const { t } = useTranslation();
  const task = useTask(taskId);
  return (
    <Dialog open={!!taskId} onOpenChange={(o) => !o && onClose()}>
      <SheetContent title={task.data?.title ?? t("tasks.task")} closeLabel={t("common.close")}>
        {task.isPending ? (
          <div className="grid place-items-center py-16">
            <Spinner />
          </div>
        ) : task.data ? (
          <Body task={task.data} onClose={onClose} />
        ) : (
          <p className="text-sm text-muted">{t("tasks.notFound")}</p>
        )}
      </SheetContent>
    </Dialog>
  );
}
