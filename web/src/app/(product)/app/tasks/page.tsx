"use client";

import { ArrowLeft, FolderKanban, ListChecks, Pencil, Plus } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import type { Project, Task } from "@/api/types";
import { useSession, useWorkspace } from "@/auth/session";
import { PageHeader } from "@/components/page";
import { Board } from "@/components/tasks/board";
import { useMyWork, useProject, useProjects, useTasks } from "@/components/tasks/data";
import { NewTaskDialog } from "@/components/tasks/new-task-dialog";
import { ProjectDialog } from "@/components/tasks/project-dialog";
import { TaskRow } from "@/components/tasks/shared";
import { TaskSheet } from "@/components/tasks/task-sheet";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, EmptyState } from "@/components/ui/card";
import { Switch } from "@/components/ui/choice";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatDay, formatNumber, todayIn } from "@/lib/format";
import { useTab } from "@/lib/use-tab";
import { addDays } from "@/lib/week";

/** `?project=` and `?task=` in the address, so notifications and reloads land in place. */
function useParam(name: string): [string | null, (value: string | null) => void] {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const set = useCallback(
    (value: string | null) => {
      const next = new URLSearchParams(params);
      if (value) next.set(name, value);
      else next.delete(name);
      const query = next.toString();
      router.push(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [params, router, pathname, name],
  );
  return [params.get(name), set];
}

function Loading() {
  return (
    <div className="grid place-items-center py-16">
      <Spinner />
    </div>
  );
}

function Group({ title, tasks, onOpen }: { title: string; tasks: Task[]; onOpen: (id: string) => void }) {
  if (!tasks.length) return null;
  return (
    <section aria-label={title} className="flex flex-col gap-1">
      <h2 className="px-3 text-xs font-semibold uppercase tracking-wide text-muted">
        {title} <span className="font-medium">· {formatNumber(tasks.length)}</span>
      </h2>
      <ul className="flex flex-col">
        {tasks.map((task) => (
          <TaskRow key={task.id} task={task} onOpen={onOpen} />
        ))}
      </ul>
    </section>
  );
}

function MyWork({ onOpen, onNew }: { onOpen: (id: string) => void; onNew: () => void }) {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const work = useMyWork();
  const groups = useMemo(() => {
    const today = todayIn(timezone);
    const week = addDays(today, 7);
    const list = work.data ?? [];
    return [
      { key: "overdue", tasks: list.filter((x) => x.overdue) },
      { key: "today", tasks: list.filter((x) => x.due_date === today) },
      { key: "week", tasks: list.filter((x) => x.due_date && x.due_date > today && x.due_date <= week) },
      { key: "later", tasks: list.filter((x) => x.due_date && x.due_date > week) },
      { key: "noDate", tasks: list.filter((x) => !x.due_date) },
    ];
  }, [work.data, timezone]);
  if (work.isPending) return <Loading />;
  if (!work.data?.length) {
    return (
      <EmptyState
        icon={<ListChecks />}
        title={t("tasks.nothingToDo")}
        action={
          <Button variant="primary" onClick={onNew}>
            <Plus aria-hidden="true" />
            {t("tasks.newTask")}
          </Button>
        }
      >
        {t("tasks.nothingToDoBody")}
      </EmptyState>
    );
  }
  return (
    <Card className="flex flex-col gap-5 p-3 md:p-4">
      {groups.map((g) => (
        <Group key={g.key} title={t(`tasks.groups.${g.key}`)} tasks={g.tasks} onOpen={onOpen} />
      ))}
    </Card>
  );
}

function ProjectCard({ project, onOpen }: { project: Project; onOpen: (id: string) => void }) {
  const { t } = useTranslation();
  const total = project.open_tasks + project.done_tasks;
  const share = total ? Math.round((project.done_tasks / total) * 100) : 0;
  return (
    <li>
      <button type="button" onClick={() => onOpen(project.id)} className="flex h-full w-full flex-col gap-4 rounded-2xl border border-border bg-surface p-5 text-left transition-shadow hover:shadow-md">
        <span className="flex items-start gap-3">
          <span aria-hidden="true" className="mt-1 size-3 shrink-0 rounded-full" style={{ background: project.color }} />
          <span className="flex min-w-0 flex-1 flex-col gap-0.5">
            <span className="truncate font-semibold">{project.name}</span>
            {project.due_date && <span className="text-xs text-muted">{t("tasks.dueOn", { date: formatDay(project.due_date) })}</span>}
          </span>
          {project.status === "archived" && <span className="text-xs text-muted">{t("tasks.archived")}</span>}
        </span>
        <span className="flex flex-col gap-1.5">
          <span className="flex justify-between text-xs text-muted">
            <span>{t("tasks.openCount", { count: project.open_tasks, formatted: formatNumber(project.open_tasks) })}</span>
            {project.overdue_tasks > 0 && <span className="font-semibold text-danger-text">{t("tasks.overdueCount", { count: project.overdue_tasks, formatted: formatNumber(project.overdue_tasks) })}</span>}
          </span>
          <span className="h-1.5 overflow-hidden rounded-full bg-surface-2" role="img" aria-label={t("tasks.progress", { percent: formatNumber(share) })}>
            <span className="block h-full rounded-full" style={{ width: `${share}%`, background: project.color }} />
          </span>
        </span>
        <span className="flex -space-x-1.5">
          {project.members.slice(0, 6).map((m) => (
            <Avatar key={m.id} name={m.name} className="size-7 text-[10px] ring-2 ring-surface" />
          ))}
          {project.members.length > 6 && <span className="grid size-7 place-items-center rounded-full bg-surface-2 text-[10px] font-semibold ring-2 ring-surface">+{formatNumber(project.members.length - 6)}</span>}
        </span>
      </button>
    </li>
  );
}

function Projects({ onOpen, onNew }: { onOpen: (id: string) => void; onNew: () => void }) {
  const { t } = useTranslation();
  const { can } = useSession();
  const [archived, setArchived] = useState(false);
  const projects = useProjects(archived ? "all" : "active");
  return (
    <div className="flex flex-col gap-4">
      <label className="flex w-fit items-center gap-3 text-sm">
        <Switch checked={archived} onCheckedChange={setArchived} />
        {t("tasks.showArchived")}
      </label>
      {projects.isPending ? (
        <Loading />
      ) : projects.data?.length ? (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {projects.data.map((p) => (
            <ProjectCard key={p.id} project={p} onOpen={onOpen} />
          ))}
        </ul>
      ) : (
        <EmptyState
          icon={<FolderKanban />}
          title={t("tasks.noProjects")}
          action={
            can("tasks.manage") ? (
              <Button variant="primary" onClick={onNew}>
                <Plus aria-hidden="true" />
                {t("tasks.newProject")}
              </Button>
            ) : undefined
          }
        >
          {can("tasks.manage") ? t("tasks.noProjectsManager") : t("tasks.noProjectsMember")}
        </EmptyState>
      )}
    </div>
  );
}

function ProjectView({ id, onBack, onOpenTask }: { id: string; onBack: () => void; onOpenTask: (id: string) => void }) {
  const { t } = useTranslation();
  const project = useProject(id);
  const tasks = useTasks({ project_id: id });
  const [editing, setEditing] = useState(false);
  const [adding, setAdding] = useState(false);
  if (project.isPending) return <Loading />;
  if (!project.data) return <EmptyState icon={<FolderKanban />} title={t("tasks.projectNotFound")} action={<Button onClick={onBack}>{t("tasks.allProjects")}</Button>} />;
  const p = project.data;
  return (
    <>
      <Link href="/app/tasks?tab=projects" onClick={(e) => (e.preventDefault(), onBack())} className="mb-3 inline-flex items-center gap-1.5 text-sm text-muted hover:text-text">
        <ArrowLeft className="size-4" aria-hidden="true" />
        {t("tasks.allProjects")}
      </Link>
      <PageHeader
        title={
          <span className="flex items-center gap-3">
            <span aria-hidden="true" className="size-3.5 rounded-full" style={{ background: p.color }} />
            {p.name}
          </span>
        }
        sub={p.description ?? undefined}
        actions={
          <>
            {p.can_manage && (
              <Button onClick={() => setEditing(true)}>
                <Pencil aria-hidden="true" />
                {t("tasks.editProject")}
              </Button>
            )}
            {p.status === "active" && (
              <Button variant="primary" onClick={() => setAdding(true)}>
                <Plus aria-hidden="true" />
                {t("tasks.newTask")}
              </Button>
            )}
          </>
        }
      />
      <div className="mb-5 flex flex-wrap items-center gap-2 text-sm text-muted">
        <span>{t("tasks.memberCount", { count: p.members.length, formatted: formatNumber(p.members.length) })}:</span>
        {p.members.map((m) => (
          <span key={m.id} className="inline-flex items-center gap-1.5 rounded-full bg-surface-2 py-0.5 pl-0.5 pr-2.5 text-xs text-text">
            <Avatar name={m.name} className="size-5 text-[9px]" />
            {m.name}
          </span>
        ))}
      </div>
      {tasks.isPending ? <Loading /> : <Board projectId={p.id} tasks={tasks.data ?? []} onOpen={onOpenTask} canAdd={p.status === "active"} />}
      {editing && <ProjectDialog project={p} onClose={() => setEditing(false)} />}
      {adding && <NewTaskDialog projectId={p.id} onClose={() => setAdding(false)} onCreated={onOpenTask} />}
    </>
  );
}

export default function TasksPage() {
  const { t } = useTranslation();
  const { can, hasModule } = useSession();
  const [projectId, setProject] = useParam("project");
  const [taskId, setTask] = useParam("task");
  const [newTask, setNewTask] = useState(false);
  const [newProject, setNewProject] = useState(false);
  const tabs = ["mine", "projects"];
  const [active, setActive] = useTab(tabs);

  if (!hasModule("tasks") || !can("tasks.self")) return <EmptyState icon={<ListChecks />} title={t("common.notAllowed")} />;
  const sheet = <TaskSheet taskId={taskId} onClose={() => setTask(null)} />;
  if (projectId) {
    return (
      <>
        <ProjectView id={projectId} onBack={() => setProject(null)} onOpenTask={setTask} />
        {sheet}
      </>
    );
  }
  return (
    <>
      <PageHeader
        title={t("tasks.title")}
        sub={t("tasks.sub")}
        actions={
          <>
            {can("tasks.manage") && (
              <Button onClick={() => setNewProject(true)}>
                <FolderKanban aria-hidden="true" />
                {t("tasks.newProject")}
              </Button>
            )}
            <Button variant="primary" onClick={() => setNewTask(true)}>
              <Plus aria-hidden="true" />
              {t("tasks.newTask")}
            </Button>
          </>
        }
      />
      <Tabs value={active} onValueChange={setActive}>
        <TabsList className="mb-5 w-fit max-w-full overflow-x-auto">
          <TabsTrigger value="mine">{t("tasks.tabs.mine")}</TabsTrigger>
          <TabsTrigger value="projects">{t("tasks.tabs.projects")}</TabsTrigger>
        </TabsList>
        <TabsContent value="mine">{active === "mine" && <MyWork onOpen={setTask} onNew={() => setNewTask(true)} />}</TabsContent>
        <TabsContent value="projects">{active === "projects" && <Projects onOpen={setProject} onNew={() => setNewProject(true)} />}</TabsContent>
      </Tabs>
      {newTask && <NewTaskDialog onClose={() => setNewTask(false)} onCreated={setTask} />}
      {newProject && <ProjectDialog onClose={() => setNewProject(false)} onSaved={(p) => setProject(p.id)} />}
      {sheet}
    </>
  );
}
