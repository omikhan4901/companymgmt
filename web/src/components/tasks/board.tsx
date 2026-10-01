"use client";

import { useMutation } from "@tanstack/react-query";
import { MoreHorizontal, Plus } from "lucide-react";
import { DropdownMenu as M } from "radix-ui";
import { useState, type DragEvent, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { Task } from "@/api/types";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MenuContent, MenuItem, MenuLabel } from "@/components/ui/menu";
import { cn } from "@/lib/cn";
import { errorMessage } from "@/lib/errors";
import { formatNumber } from "@/lib/format";

import { STATUSES, useRefreshTasks, type Status } from "./data";
import { DueLabel, PriorityBadge, TaskMeta } from "./shared";

function Card({ task, onOpen, onMove }: { task: Task; onOpen: (id: string) => void; onMove: (status: Status) => void }) {
  const { t } = useTranslation();
  return (
    <li
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("text/task", task.id);
        e.dataTransfer.effectAllowed = "move";
      }}
      data-task={task.id}
      className="group relative rounded-xl border border-border bg-surface shadow-sm transition-shadow hover:shadow-md"
    >
      <button type="button" onClick={() => onOpen(task.id)} className="flex w-full flex-col gap-2 rounded-xl p-3 pr-10 text-left">
        <span className={cn("text-sm font-medium", task.status === "done" && "text-muted line-through")}>{task.title}</span>
        <span className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <PriorityBadge priority={task.priority} />
          <DueLabel task={task} />
          <TaskMeta task={task} />
        </span>
        {task.assignee && (
          <span className="flex items-center gap-1.5 text-xs text-muted">
            <Avatar name={task.assignee.name} className="size-5 text-[9px]" />
            {task.assignee.name}
          </span>
        )}
      </button>
      <M.Root>
        <M.Trigger className="absolute right-2 top-2 grid size-7 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-text" aria-label={t("tasks.moveTask", { title: task.title })}>
          <MoreHorizontal className="size-4" aria-hidden="true" />
        </M.Trigger>
        <MenuContent>
          <MenuLabel>{t("tasks.moveTo")}</MenuLabel>
          {STATUSES.filter((s) => s !== task.status).map((s) => (
            <MenuItem key={s} onSelect={() => onMove(s)}>
              {t(`tasks.status.${s}`)}
            </MenuItem>
          ))}
        </MenuContent>
      </M.Root>
    </li>
  );
}

function QuickAdd({ projectId, status }: { projectId: string; status: Status }) {
  const { t } = useTranslation();
  const refresh = useRefreshTasks();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const add = useMutation({
    mutationFn: (value: string) => api("/v1/tasks", { body: { title: value, project_id: projectId, status, unassigned: true } }),
    onSuccess: () => {
      setTitle("");
      void refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (title.trim()) add.mutate(title.trim());
  };
  if (!open) {
    return (
      <Button variant="ghost" size="sm" className="justify-start text-muted" onClick={() => setOpen(true)}>
        <Plus aria-hidden="true" />
        {t("tasks.addCard")}
      </Button>
    );
  }
  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <Input
        autoFocus
        value={title}
        maxLength={200}
        onChange={(e) => setTitle(e.target.value)}
        onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
        placeholder={t("tasks.newTitle")}
        aria-label={t("tasks.newTitleIn", { column: t(`tasks.status.${status}`) })}
      />
      <div className="flex gap-2">
        <Button type="submit" size="sm" variant="primary" loading={add.isPending} disabled={!title.trim()}>
          {t("common.add")}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(false)}>
          {t("common.cancel")}
        </Button>
      </div>
    </form>
  );
}

/** To do / Doing / Done. Cards are dragged on desktop; the ⋯ menu moves them anywhere. */
export function Board({ projectId, tasks, onOpen, canAdd }: { projectId: string; tasks: Task[]; onOpen: (id: string) => void; canAdd: boolean }) {
  const { t } = useTranslation();
  const refresh = useRefreshTasks();
  const [over, setOver] = useState<Status | null>(null);
  const move = useMutation({
    mutationFn: ({ id, status, after }: { id: string; status: Status; after: string | null }) =>
      api(`/v1/tasks/${id}/move`, { body: { status, after_id: after } }),
    onSettled: () => void refresh(),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const columns = STATUSES.map((status) => ({ status, cards: tasks.filter((x) => x.status === status).sort((a, b) => a.position - b.position) }));

  const drop = (status: Status, cards: Task[]) => (e: DragEvent<HTMLElement>) => {
    e.preventDefault();
    setOver(null);
    const id = e.dataTransfer.getData("text/task");
    if (!id) return;
    // Land after the last card above the pointer.
    const items = Array.from(e.currentTarget.querySelectorAll<HTMLElement>("[data-task]")).filter((el) => el.dataset.task !== id);
    const above = items.filter((el) => el.getBoundingClientRect().top + el.offsetHeight / 2 < e.clientY);
    const after = above.length ? (above[above.length - 1]?.dataset.task ?? null) : null;
    // Dropped where it already is: nothing to do.
    const index = cards.findIndex((c) => c.id === id);
    if (index >= 0 && (index > 0 ? cards[index - 1]?.id : null) === after) return;
    move.mutate({ id, status, after });
  };

  return (
    <div className="-mx-4 flex snap-x gap-4 overflow-x-auto px-4 pb-2 md:mx-0 md:grid md:grid-cols-3 md:overflow-visible md:px-0">
      {columns.map(({ status, cards }) => (
        <section
          key={status}
          aria-labelledby={`col-${status}`}
          onDragOver={(e) => {
            e.preventDefault();
            setOver(status);
          }}
          onDragLeave={() => setOver(null)}
          onDrop={drop(status, cards)}
          className={cn(
            "flex w-[82vw] max-w-sm shrink-0 snap-start flex-col gap-3 rounded-2xl bg-surface-2 p-3 md:w-auto md:max-w-none",
            over === status && "ring-2 ring-accent",
          )}
        >
          <h3 id={`col-${status}`} className="flex items-center justify-between px-1 text-sm font-semibold">
            {t(`tasks.status.${status}`)}
            <span className="text-xs font-medium text-muted">{formatNumber(cards.length)}</span>
          </h3>
          <ul className="flex min-h-12 flex-col gap-2">
            {cards.map((task) => (
              <Card key={task.id} task={task} onOpen={onOpen} onMove={(s) => move.mutate({ id: task.id, status: s, after: tasks.filter((x) => x.status === s).sort((a, b) => a.position - b.position).at(-1)?.id ?? null })} />
            ))}
          </ul>
          {canAdd && <QuickAdd projectId={projectId} status={status} />}
        </section>
      ))}
    </div>
  );
}
