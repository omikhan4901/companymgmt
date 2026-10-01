"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check, CheckCircle2, Circle, Mail, MapPin, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import { useAttendanceSettings, useAway, useCorrections, useDepartments, useLeaveRequests, usePresent, useTimesheet } from "@/api/hooks";
import type { AttendanceRecord, Employee, Page } from "@/api/types";
import { useSession, useWorkspace } from "@/auth/session";
import { ClockCard } from "@/components/attendance/clock-card";
import { useFeed } from "@/components/announcements/data";
import { useMyWork } from "@/components/tasks/data";
import { TaskRow } from "@/components/tasks/shared";
import { BarChart, type Bar } from "@/components/bar-chart";
import { PageHeader } from "@/components/page";
import { Alert } from "@/components/ui/alert";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { intlLocale } from "@/i18n";
import { errorMessage } from "@/lib/errors";
import { formatAgo, formatDateTime, formatDay, formatDuration, formatNumber, formatTime, todayIn } from "@/lib/format";
import { addDays, daysBetween, startOfWeek } from "@/lib/week";

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card className="flex min-h-36 flex-col justify-between gap-4 p-5">
      <span className="text-sm text-muted">{label}</span>
      <div className="flex flex-col gap-0.5">
        <span className="font-display text-4xl font-semibold tracking-tight tabular-nums">{value}</span>
        {sub && <span className="text-[13px] text-muted">{sub}</span>}
      </div>
    </Card>
  );
}

function hoursText(minutes: number): string {
  return `${formatNumber(Math.floor(minutes / 60))}:${String(minutes % 60).padStart(2, "0").replace(/\d/g, (d) => formatNumber(Number(d)))}`;
}

/** Team hours per day for the last 14 days (managers). */
function useTeamDays(enabled: boolean) {
  const { timezone } = useWorkspace();
  const today = todayIn(timezone);
  const first = addDays(today, -13);
  const thisMonth = useTimesheet(today.slice(0, 7), enabled);
  const lastMonth = useTimesheet(first.slice(0, 7), enabled && first.slice(0, 7) !== today.slice(0, 7));
  return useMemo(() => {
    const perDay = new Map<string, number>();
    for (const sheet of [thisMonth.data, lastMonth.data]) {
      for (const row of sheet?.rows ?? []) for (const d of row.days) perDay.set(d.date, (perDay.get(d.date) ?? 0) + d.minutes);
    }
    return { days: daysBetween(first, today).map((d) => ({ day: d, minutes: perDay.get(d) ?? 0 })), ready: !!thisMonth.data };
  }, [thisMonth.data, lastMonth.data, first, today]);
}

/** My own hours per day for the last 14 days (everyone who clocks in). */
function useMyDays(enabled: boolean) {
  const { timezone } = useWorkspace();
  const today = todayIn(timezone);
  const first = addDays(today, -13);
  const records = useQuery({
    queryKey: ["attendance", "records", { mine: true, from: first }],
    queryFn: () => api<Page<AttendanceRecord>>("/v1/attendance/records", { query: { mine: true, from: first, to: today, limit: 200 } }),
    enabled,
  });
  return useMemo(() => {
    const perDay = new Map<string, number>();
    for (const r of records.data?.items ?? []) perDay.set(r.business_date, (perDay.get(r.business_date) ?? 0) + (r.minutes ?? 0));
    return { days: daysBetween(first, today).map((d) => ({ day: d, minutes: perDay.get(d) ?? 0 })), ready: !!records.data };
  }, [records.data, first, today]);
}

function HoursCard({ days, title, className }: { days: { day: string; minutes: number }[]; title: string; className?: string }) {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const today = todayIn(timezone);
  const bars: Bar[] = days.map(({ day, minutes }) => ({
    key: day,
    label: formatDay(day, { day: "numeric", month: undefined, year: undefined }),
    name: formatDay(day, { weekday: "short", day: "numeric", month: "short", year: undefined }),
    value: minutes,
    display: formatDuration(minutes, t),
    highlight: day === today,
  }));
  return (
    <Card className={className}>
      <CardHeader title={title} />
      <div className="px-5 pb-5 pt-2">
        <BarChart bars={bars} label={title} />
      </div>
    </Card>
  );
}

function AtWorkCard({ className }: { className?: string }) {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const present = usePresent();
  const people = present.data ?? [];
  return (
    <Card className={className}>
      <CardHeader
        title={t("home.whoIsIn")}
        action={
          <Link href="/app/attendance?tab=today" className="text-sm font-medium text-accent-soft-text hover:underline">
            {t("nav.attendance")}
          </Link>
        }
      />
      <div className="px-5 pb-4 pt-2">
        {present.data && people.length === 0 && <p className="py-4 text-sm text-muted">{t("home.nobodyIn")}</p>}
        <ul className="divide-y divide-border">
          {people.slice(0, 8).map((p) => (
            <li key={p.employee_id} className="flex items-center gap-3 py-2.5">
              <Avatar name={p.employee_name} />
              <span className="min-w-0 flex-1 truncate text-sm font-medium">{p.employee_name}</span>
              <span className="shrink-0 text-sm text-muted tabular-nums">{formatTime(p.clock_in_at, timezone)}</span>
            </li>
          ))}
        </ul>
      </div>
    </Card>
  );
}

function AwayCard({ className }: { className?: string }) {
  const { t } = useTranslation();
  const { can } = useSession();
  const { timezone } = useWorkspace();
  const today = todayIn(timezone);
  const away = useAway(today, today);
  const approver = can("leave.approve");
  const pending = useLeaveRequests({ status: "pending" }, approver);
  const people = (away.data ?? []).filter((e) => e.status === "approved");
  const waiting = pending.data?.length ?? 0;
  return (
    <Card className={className}>
      <CardHeader
        title={t("leave.awayToday")}
        action={
          <Link href={approver && waiting ? "/app/leave?tab=requests" : "/app/leave"} className="text-sm font-medium text-accent-soft-text hover:underline">
            {approver && waiting ? t("leave.tabs.requests") : t("nav.leave")}
            {approver && waiting > 0 && (
              <Badge tone="accent" className="ml-2">
                {formatNumber(waiting)}
              </Badge>
            )}
          </Link>
        }
      />
      <div className="px-5 pb-4 pt-2">
        {away.data && people.length === 0 && <p className="py-4 text-sm text-muted">{t("leave.nobodyAway")}</p>}
        <ul className="divide-y divide-border">
          {people.slice(0, 8).map((p) => (
            <li key={`${p.employee_id}-${p.start_date}`} className="flex items-center gap-3 py-2.5">
              <Avatar name={p.employee_name} />
              <span className="min-w-0 flex-1 truncate text-sm font-medium">{p.employee_name}</span>
              <span className="shrink-0 text-sm text-muted">{p.leave_type_name ?? t("leave.away")}</span>
            </li>
          ))}
        </ul>
      </div>
    </Card>
  );
}

function NewsCard({ className }: { className?: string }) {
  const { t } = useTranslation();
  const feed = useFeed();
  const latest = (feed.data ?? []).slice(0, 2);
  if (feed.data && latest.length === 0) return null;
  return (
    <Card className={className}>
      <CardHeader
        title={t("news.latest")}
        action={
          <Link href="/app/announcements" className="text-sm font-medium text-accent-soft-text hover:underline">
            {t("news.seeAll")}
          </Link>
        }
      />
      <ul className="flex flex-col gap-3 px-5 pb-5 pt-2">
        {latest.map((post) => (
          <li key={post.id}>
            <Link href={`/app/announcements?post=${post.id}`} className="block rounded-xl border border-border p-3 hover:bg-surface-2">
              <span className="flex items-center gap-2 text-sm font-semibold">
                {post.title}
                {!post.read && <Badge tone="accent">{t("news.new")}</Badge>}
              </span>
              <span className="mt-1 line-clamp-2 block text-sm text-muted">{post.body}</span>
              <span className="mt-1.5 block text-xs text-muted">
                {post.author_name} · {formatAgo(post.published_at)}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function MyWorkCard({ className }: { className?: string }) {
  const { t } = useTranslation();
  const router = useRouter();
  const work = useMyWork();
  const open = (id: string) => router.push(`/app/tasks?task=${id}`);
  const list = work.data ?? [];
  return (
    <Card className={className}>
      <CardHeader
        title={t("tasks.tabs.mine")}
        action={
          <Link href="/app/tasks" className="text-sm font-medium text-accent-soft-text hover:underline">
            {t("nav.tasks")}
            {list.length > 0 && (
              <Badge tone="accent" className="ml-2">
                {formatNumber(list.length)}
              </Badge>
            )}
          </Link>
        }
      />
      <div className="px-2 pb-3 pt-1">
        {work.data && list.length === 0 && <p className="px-3 py-4 text-sm text-muted">{t("tasks.nothingToDoBody")}</p>}
        <ul className="flex flex-col">
          {list.slice(0, 6).map((task) => (
            <TaskRow key={task.id} task={task} onOpen={open} />
          ))}
        </ul>
      </div>
    </Card>
  );
}

function ApprovalsCard({ className }: { className?: string }) {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const queryClient = useQueryClient();
  const pending = useCorrections("pending", false);
  const decide = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "approve" | "reject" }) => api(`/v1/attendance/corrections/${id}/${action}`, { body: {} }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["attendance"] }),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const items = pending.data ?? [];
  return (
    <Card className={className}>
      <CardHeader
        title={t("home.waiting")}
        action={items.length > 0 ? <Badge tone="accent">{formatNumber(items.length)}</Badge> : undefined}
      />
      <div className="flex flex-col gap-2 px-5 pb-5 pt-3">
        {pending.data && items.length === 0 && (
          <p className="flex items-center gap-2 py-4 text-sm text-muted">
            <CheckCircle2 className="size-4 text-success-text" aria-hidden="true" />
            {t("attendance.noRequests")}
          </p>
        )}
        {items.slice(0, 4).map((c) => (
          <div key={c.id} className="flex items-center gap-3 rounded-xl border border-border bg-surface-2 px-3 py-2.5">
            <Badge tone="warn" className="w-12 justify-center">
              {t("home.fixBadge")}
            </Badge>
            <div className="flex min-w-0 flex-1 flex-col text-sm">
              <span className="truncate font-semibold">{c.employee_name}</span>
              <span className="truncate text-muted">
                {t(`attendance.kind.${c.kind}`)}
                {c.proposed_clock_in_at ? ` · ${formatDateTime(c.proposed_clock_in_at, timezone)}` : ""}
              </span>
            </div>
            <Button size="iconSm" aria-label={`${t("attendance.reject")}: ${c.employee_name}`} onClick={() => decide.mutate({ id: c.id, action: "reject" })} disabled={decide.isPending}>
              <X aria-hidden="true" />
            </Button>
            <Button size="iconSm" variant="solid" aria-label={`${t("attendance.approve")}: ${c.employee_name}`} onClick={() => decide.mutate({ id: c.id, action: "approve" })} disabled={decide.isPending}>
              <Check aria-hidden="true" />
            </Button>
          </div>
        ))}
        {items.length > 4 && (
          <Link href="/app/attendance?tab=corrections" className="mt-1 inline-flex items-center gap-1 text-sm font-medium text-accent-soft-text hover:underline">
            {t("home.seeAll")} <ArrowRight className="size-3.5" aria-hidden="true" />
          </Link>
        )}
      </div>
    </Card>
  );
}

function Checklist({ className }: { className?: string }) {
  const { t } = useTranslation();
  const { me, can } = useSession();
  const people = useQuery({
    queryKey: ["people", { limit: 2 }],
    queryFn: () => api<Page<Employee>>("/v1/people", { query: { limit: 2 } }),
    enabled: can("people.view"),
  });
  const departments = useDepartments(can("departments.manage"));
  const settings = useAttendanceSettings(can("branches.manage"));
  if (!can("members.invite") || !people.data) return null;
  const steps = [
    { done: !!me?.email_verified, label: t("home.stepVerify"), href: "/app/account" },
    { done: people.data.items.length > 1, label: t("home.stepPeople"), href: "/app/team" },
    { done: (departments.data?.length ?? 0) > 0, label: t("home.stepDepartments"), href: "/app/people?tab=departments" },
    { done: (settings.data?.branches_located ?? 1) > 0, label: t("home.stepBranch"), href: "/app/settings?tab=branches" },
  ];
  if (steps.every((s) => s.done)) return null;
  return (
    <Card className={className}>
      <CardHeader title={t("home.checklist")} />
      <ol className="flex flex-col gap-0.5 px-3 pb-4 pt-2">
        {steps.map((s) => (
          <li key={s.label}>
            <Link href={s.href} className="flex items-center gap-3 rounded-lg px-2 py-2.5 hover:bg-surface-2">
              {s.done ? <CheckCircle2 className="size-5 text-success-text" aria-hidden="true" /> : <Circle className="size-5 text-border-strong" aria-hidden="true" />}
              <span className={s.done ? "text-muted line-through" : ""}>{s.label}</span>
              <span className="sr-only">{s.done ? t("home.done") : ""}</span>
            </Link>
          </li>
        ))}
      </ol>
    </Card>
  );
}

export default function HomePage() {
  const { t } = useTranslation();
  const { me, can, hasModule } = useSession();
  const workspace = useWorkspace();
  const attendance = hasModule("attendance");
  const self = attendance && can("attendance.self");
  const manager = attendance && can("attendance.view");
  const team = useTeamDays(manager);
  const mine = useMyDays(self && !manager);
  const today = todayIn(workspace.timezone);
  const weekStart = startOfWeek(today, workspace.week_start);
  const series = manager ? team : mine;
  const weekMinutes = series.days.filter((d) => d.day >= weekStart).reduce((sum, d) => sum + d.minutes, 0);
  const present = usePresent(manager);
  const settings = useAttendanceSettings(can("branches.manage") && attendance);
  const plan = workspace.plan;

  const resend = async () => {
    try {
      await api("/v1/auth/email/resend", { method: "POST" });
      toast.success(t("home.verifySent"));
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  const unplaced = settings.data && settings.data.location_mode !== "off" ? settings.data.branches_total - settings.data.branches_located : 0;

  return (
    <>
      <PageHeader
        sub={`${workspace.name} · ${new Intl.DateTimeFormat(intlLocale(), { weekday: "long", day: "numeric", month: "long", timeZone: workspace.timezone }).format(new Date())}`}
        title={t("home.greeting", { name: (me?.name ?? "").split(" ")[0] })}
      />

      <div className="mb-5 flex flex-col gap-3 empty:hidden">
        {me?.email && !me.email_verified && (
          <Alert tone="warn" action={<Button size="sm" onClick={() => void resend()}><Mail aria-hidden="true" />{t("home.resendVerify")}</Button>}>
            {t("home.stepVerify")}
          </Alert>
        )}
        {unplaced > 0 && settings.data && (
          <Alert
            tone="info"
            action={
              <Button asChild size="sm">
                <Link href="/app/settings?tab=branches">
                  <MapPin aria-hidden="true" />
                  {t("location.placeBranch")}
                </Link>
              </Button>
            }
          >
            {t("location.unplaced", { count: formatNumber(unplaced), total: formatNumber(settings.data.branches_total) })}
          </Alert>
        )}
        {plan.status === "trialing" && plan.trial_ends_at && can("workspace.manage") && (
          <Alert
            tone="info"
            action={
              <Button asChild size="sm">
                <Link href="/app/settings?tab=plan">
                  <Sparkles aria-hidden="true" />
                  {t("home.seePlans")}
                </Link>
              </Button>
            }
          >
            {t("home.trialEnds", { date: formatDay(plan.trial_ends_at.slice(0, 10)) })}
          </Alert>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {self && <ClockCard className="md:col-span-2" />}
        {manager ? (
          <>
            <Kpi label={t("home.atWork")} value={formatNumber(present.data?.length ?? 0)} sub={t("home.atWorkSub")} />
            <Kpi label={t("home.hoursThisWeek")} value={hoursText(weekMinutes)} sub={t("home.sinceWeekStart", { date: formatDay(weekStart, { weekday: "long", day: undefined, month: undefined, year: undefined }) })} />
          </>
        ) : self ? (
          <>
            <Kpi label={t("home.myWeek")} value={hoursText(weekMinutes)} sub={t("home.sinceWeekStart", { date: formatDay(weekStart, { weekday: "long", day: undefined, month: undefined, year: undefined }) })} />
            <Card className="flex min-h-36 flex-col justify-between gap-3 p-5">
              <span className="text-sm text-muted">{t("attendance.title")}</span>
              <p className="text-sm">{t("attendance.sub")}</p>
              <Link href="/app/attendance" className="inline-flex items-center gap-1 text-sm font-semibold text-accent-soft-text hover:underline">
                {t("home.openAttendance")} <ArrowRight className="size-3.5" aria-hidden="true" />
              </Link>
            </Card>
          </>
        ) : null}

        {self || manager ? <HoursCard days={series.days} title={manager ? t("home.teamHours") : t("home.myHours")} className="md:col-span-2" /> : null}
        {manager && can("attendance.approve") && <ApprovalsCard className="md:col-span-2" />}
        {manager && <AtWorkCard className="md:col-span-2" />}
        {hasModule("announcements") && can("announcements.read") && <NewsCard className="md:col-span-2" />}
        {hasModule("tasks") && can("tasks.self") && <MyWorkCard className="md:col-span-2" />}
        {hasModule("leave") && can("leave.self") && <AwayCard className="md:col-span-2" />}
        <Checklist className="md:col-span-2" />
      </div>
    </>
  );
}
