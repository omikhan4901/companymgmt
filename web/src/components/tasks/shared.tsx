"use client";

import { CalendarDays, CheckSquare, MessageSquare } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { Task } from "@/api/types";
import { useWorkspace } from "@/auth/session";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";
import { formatDay, formatNumber, todayIn } from "@/lib/format";
import { addDays } from "@/lib/week";

const PRIORITY_TONE = { urgent: "danger", high: "warn", normal: null, low: null } as const;

export function PriorityBadge({ priority }: { priority: Task["priority"] }) {
  const { t } = useTranslation();
  const tone = PRIORITY_TONE[priority];
  if (!tone) return null;
  return <Badge tone={tone}>{t(`tasks.priority.${priority}`)}</Badge>;
}

/** "Today", "Tomorrow", "Overdue · 3 Mar" or the date. */
export function DueLabel({ task, className }: { task: Pick<Task, "due_date" | "overdue" | "status">; className?: string }) {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  if (!task.due_date) return null;
  const today = todayIn(timezone);
  let text = formatDay(task.due_date, { year: task.due_date.slice(0, 4) === today.slice(0, 4) ? undefined : "numeric" });
  if (task.due_date === today) text = t("tasks.today");
  else if (task.due_date === addDays(today, 1)) text = t("tasks.tomorrow");
  return (
    <span className={cn("inline-flex items-center gap-1 text-xs", task.overdue ? "font-semibold text-danger-text" : "text-muted", className)}>
      <CalendarDays className="size-3.5" aria-hidden="true" />
      {task.overdue ? t("tasks.overdueOn", { date: text }) : text}
    </span>
  );
}

/** Small counts shown on cards and rows: checklist progress and comments. */
export function TaskMeta({ task }: { task: Task }) {
  const { t } = useTranslation();
  return (
    <>
      {task.checklist_total > 0 && (
        <span className="inline-flex items-center gap-1 text-xs text-muted" title={t("tasks.checklist")}>
          <CheckSquare className="size-3.5" aria-hidden="true" />
          <span className="sr-only">{t("tasks.checklist")}:</span>
          {formatNumber(task.checklist_done)}/{formatNumber(task.checklist_total)}
        </span>
      )}
      {task.comments > 0 && (
        <span className="inline-flex items-center gap-1 text-xs text-muted">
          <MessageSquare className="size-3.5" aria-hidden="true" />
          <span className="sr-only">{t("tasks.comments")}:</span>
          {formatNumber(task.comments)}
        </span>
      )}
    </>
  );
}

/** One task in a list (My work, home). Opens the task. */
export function TaskRow({ task, onOpen, showProject = true }: { task: Task; onOpen: (id: string) => void; showProject?: boolean }) {
  const done = task.status === "done";
  return (
    <li>
      <button
        type="button"
        onClick={() => onOpen(task.id)}
        className="flex w-full items-start gap-3 rounded-xl px-3 py-2.5 text-left hover:bg-surface-2"
      >
        <span aria-hidden="true" className={cn("mt-1 size-4 shrink-0 rounded-full border-2", done ? "border-success-text bg-success-text" : task.status === "doing" ? "border-accent" : "border-border-strong")} />
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <span className={cn("text-sm font-medium", done && "text-muted line-through")}>{task.title}</span>
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            {showProject && task.project_name && <span className="text-xs text-muted">{task.project_name}</span>}
            <DueLabel task={task} />
            <TaskMeta task={task} />
            <PriorityBadge priority={task.priority} />
          </span>
        </span>
        {task.assignee && <Avatar name={task.assignee.name} className="size-7 text-[11px]" />}
      </button>
    </li>
  );
}
