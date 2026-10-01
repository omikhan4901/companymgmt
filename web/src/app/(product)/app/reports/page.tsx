"use client";

import { useQuery } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import { departmentOptions, useDepartments } from "@/api/hooks";
import type { Overview } from "@/api/types";
import { useSession, useWorkspace } from "@/auth/session";
import { BarChart, type Bar } from "@/components/bar-chart";
import { PageHeader } from "@/components/page";
import { Card, CardHeader, EmptyState } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { errorMessage } from "@/lib/errors";
import { formatDay, formatDuration, formatNumber, todayIn } from "@/lib/format";
import { addDays, lastDayOfMonth, startOfWeek } from "@/lib/week";

const PERIODS = ["thisWeek", "lastWeek", "thisMonth", "lastMonth", "last30", "thisYear"] as const;
type Period = (typeof PERIODS)[number];

function range(period: Period, today: string, weekStart: number): [string, string] {
  const week = startOfWeek(today, weekStart);
  const month = today.slice(0, 7);
  const lastMonth = addDays(`${month}-01`, -1).slice(0, 7);
  switch (period) {
    case "thisWeek":
      return [week, today];
    case "lastWeek":
      return [addDays(week, -7), addDays(week, -1)];
    case "thisMonth":
      return [`${month}-01`, today];
    case "lastMonth":
      return [`${lastMonth}-01`, lastDayOfMonth(lastMonth)];
    case "last30":
      return [addDays(today, -29), today];
    case "thisYear":
      return [`${today.slice(0, 4)}-01-01`, today];
  }
}

function percent(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${formatNumber(Math.round(value * 100))}%`;
}

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card className="flex flex-col gap-1 p-5">
      <span className="text-[13px] text-muted">{label}</span>
      <span className="font-display text-[34px] font-semibold leading-tight tabular-nums">{value}</span>
      {sub && <span className="text-[13px] text-muted">{sub}</span>}
    </Card>
  );
}

/** Horizontal bars with the value written out, for a handful of categories. */
function Breakdown({ rows, label }: { rows: { key: string; name: string; value: number; display: string; color?: string }[]; label: string }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <ul className="flex flex-col gap-3 px-5 pb-5 pt-3" aria-label={label}>
      {rows.map((r) => (
        <li key={r.key} className="flex flex-col gap-1.5">
          <span className="flex justify-between gap-3 text-sm">
            <span className="truncate">{r.name}</span>
            <span className="font-medium tabular-nums">{r.display}</span>
          </span>
          <span className="h-2 overflow-hidden rounded-full bg-surface-2" aria-hidden="true">
            <span className="block h-full rounded-full" style={{ width: `${(r.value / max) * 100}%`, background: r.color ?? "var(--color-accent)" }} />
          </span>
        </li>
      ))}
    </ul>
  );
}

function PeopleList({ rows, empty, unit }: { rows: { employee_id: string; name: string; count: number }[]; empty: string; unit: (n: number) => string }) {
  if (!rows.length) return <p className="px-5 pb-5 pt-3 text-sm text-muted">{empty}</p>;
  return (
    <ol className="flex flex-col px-5 pb-4 pt-2">
      {rows.map((r) => (
        <li key={r.employee_id} className="flex justify-between gap-3 border-b border-border py-2.5 text-sm last:border-0">
          <span className="truncate">{r.name}</span>
          <span className="font-medium tabular-nums">{unit(r.count)}</span>
        </li>
      ))}
    </ol>
  );
}

function Report({ data }: { data: Overview }) {
  const { t } = useTranslation();
  const { attendance: att, leave, tasks, headcount } = data;
  const bars: Bar[] = (att?.days ?? []).map((d) => ({
    key: d.day,
    label: formatNumber(Number(d.day.slice(8))),
    name: formatDay(d.day, { weekday: "short", day: "numeric", month: "short" }),
    value: d.expected ? d.present / d.expected : 0,
    display: t("reports.dayRate", { rate: percent(d.expected ? d.present / d.expected : null), present: formatNumber(d.present), expected: formatNumber(d.expected) }),
  }));
  return (
    <div className="flex flex-col gap-5">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5">
        <Tile label={t("reports.headcount")} value={formatNumber(headcount.active)} sub={t("reports.joinedLeft", { joined: formatNumber(headcount.joined), left: formatNumber(headcount.left) })} />
        {att && <Tile label={t("reports.attendanceRate")} value={percent(att.rate)} sub={t("reports.presentOf", { present: formatNumber(att.present), expected: formatNumber(att.expected) })} />}
        {att && <Tile label={t("reports.late")} value={formatNumber(att.late)} sub={att.average_minutes ? t("reports.averageDay", { duration: formatDuration(att.average_minutes, t) }) : undefined} />}
        {leave && <Tile label={t("reports.leaveTaken")} value={formatNumber(leave.days_taken)} sub={t("reports.awayWaiting", { away: formatNumber(leave.away_today), pending: formatNumber(leave.pending) })} />}
        {tasks && <Tile label={t("reports.overdue")} value={formatNumber(tasks.overdue)} sub={t("reports.openDone", { open: formatNumber(tasks.open), done: formatNumber(tasks.done) })} />}
      </div>
      {att && (
        <Card>
          <CardHeader title={t("reports.byDay")} sub={t("reports.byDaySub")} />
          <div className="px-5 pb-5">{bars.length ? <BarChart bars={bars} label={t("reports.byDay")} /> : <p className="py-6 text-sm text-muted">{t("reports.noWorkingDays")}</p>}</div>
        </Card>
      )}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title={t("reports.byDepartment")} />
          <Breakdown label={t("reports.byDepartment")} rows={headcount.by_department.map((d) => ({ key: d.department_id ?? "none", name: d.name ?? t("reports.noDepartment"), value: d.people, display: formatNumber(d.people) }))} />
        </Card>
        {leave && (
          <Card>
            <CardHeader title={t("reports.leaveByType")} />
            {leave.by_type.length ? (
              <Breakdown label={t("reports.leaveByType")} rows={leave.by_type.map((l) => ({ key: l.leave_type_id, name: l.name, value: l.days, display: t("reports.days", { count: l.days, formatted: formatNumber(l.days) }), color: l.color }))} />
            ) : (
              <p className="px-5 pb-5 pt-3 text-sm text-muted">{t("reports.noLeave")}</p>
            )}
          </Card>
        )}
        {att && (
          <Card>
            <CardHeader title={t("reports.mostLate")} />
            <PeopleList rows={att.most_late} empty={t("reports.nobodyLate")} unit={(n) => t("reports.times", { count: n, formatted: formatNumber(n) })} />
          </Card>
        )}
        {tasks && (
          <Card>
            <CardHeader title={t("reports.mostOverdue")} />
            <PeopleList rows={tasks.most_overdue} empty={t("reports.nothingOverdue")} unit={(n) => t("reports.tasks", { count: n, formatted: formatNumber(n) })} />
          </Card>
        )}
      </div>
    </div>
  );
}

export default function ReportsPage() {
  const { t } = useTranslation();
  const { can } = useSession();
  const workspace = useWorkspace();
  const departments = useDepartments();
  const [period, setPeriod] = useState<Period>("thisMonth");
  const [department, setDepartment] = useState("");
  const [start, end] = useMemo(() => range(period, todayIn(workspace.timezone), workspace.week_start), [period, workspace.timezone, workspace.week_start]);
  const report = useQuery({
    queryKey: ["reports", "overview", start, end, department],
    queryFn: () => api<Overview>("/v1/reports/overview", { query: { from: start, to: end, department_id: department || undefined } }),
    enabled: can("reports.view"),
  });
  if (!can("reports.view")) return <EmptyState icon={<BarChart3 />} title={t("common.notAllowed")} />;
  return (
    <>
      <PageHeader title={t("reports.title")} sub={t("reports.sub")} />
      <div className="mb-5 flex flex-wrap items-end gap-3">
        <Field label={t("reports.period")} className="w-full sm:w-52">
          <Select value={period} onChange={(e) => setPeriod(e.target.value as Period)}>
            {PERIODS.map((p) => (
              <option key={p} value={p}>
                {t(`reports.periods.${p}`)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("people.department")} className="w-full sm:w-60">
          <Select value={department} onChange={(e) => setDepartment(e.target.value)}>
            <option value="">{t("reports.allDepartments")}</option>
            {departmentOptions(departments.data).map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
        </Field>
        <p className="pb-2.5 text-sm text-muted">{t("reports.range", { start: formatDay(start), end: formatDay(end) })}</p>
        {can("workspace.manage") && (
          <Link href="/app/settings?tab=branches" className="pb-2.5 text-sm font-medium text-accent-soft-text hover:underline sm:ml-auto">
            {t("reports.lateSettings")}
          </Link>
        )}
      </div>
      {report.isPending ? (
        <div className="grid place-items-center py-16">
          <Spinner />
        </div>
      ) : report.data ? (
        <Report data={report.data} />
      ) : (
        <EmptyState icon={<BarChart3 />} title={errorMessage(report.error)} />
      )}
    </>
  );
}
