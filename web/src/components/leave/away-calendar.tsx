"use client";

import { CalendarRange } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { useAway, useHolidays, useLeavePolicy } from "@/api/hooks";
import type { AwayEntry } from "@/api/types";
import { useWorkspace } from "@/auth/session";
import { Card, EmptyState } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/cn";
import { formatDay, formatNumber, todayIn } from "@/lib/format";
import { daysBetween, isoWeekday, lastDayOfMonth } from "@/lib/week";

interface Row {
  id: string;
  name: string;
  byDay: Map<string, AwayEntry>;
}

function rows(entries: AwayEntry[], days: string[]): Row[] {
  const people = new Map<string, Row>();
  for (const e of entries) {
    const row = people.get(e.employee_id) ?? { id: e.employee_id, name: e.employee_name, byDay: new Map() };
    for (const d of days) {
      // An approved entry wins over a waiting one on the same day.
      if (d >= e.start_date && d <= e.end_date && (!row.byDay.has(d) || e.status === "approved")) row.byDay.set(d, e);
    }
    people.set(e.employee_id, row);
  }
  return [...people.values()].sort((a, b) => a.name.localeCompare(b.name));
}

/** Who is away in a month: people down the side, days across. */
export function AwayCalendar() {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const today = todayIn(timezone);
  const [month, setMonth] = useState(today.slice(0, 7));
  const first = `${month}-01`;
  const last = lastDayOfMonth(month);
  const days = useMemo(() => daysBetween(first, last), [first, last]);
  const away = useAway(first, last);
  const policy = useLeavePolicy();
  const holidays = useHolidays(Number(month.slice(0, 4)));
  const off = new Set(policy.data?.weekly_off ?? []);
  const holidayNames = new Map((holidays.data ?? []).filter((h) => !h.branch_id).map((h) => [h.day, h.name]));
  const table = useMemo(() => rows(away.data ?? [], days), [away.data, days]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <Field label={t("leave.month")} className="w-44">
          <Input type="month" value={month} onChange={(e) => e.target.value && setMonth(e.target.value)} />
        </Field>
        <p className="pb-2 text-[13px] text-muted">{t("leave.calendarHelp")}</p>
      </div>
      <Card className="overflow-hidden">
        <div className="relative overflow-x-auto" role="region" aria-label={t("leave.tabs.calendar")} tabIndex={0}>
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                <th scope="col" className="sticky left-0 z-10 min-w-40 border-b border-r border-border bg-surface px-4 py-2.5 text-left text-[13px] font-medium text-muted">
                  {t("leave.person")}
                </th>
                {days.map((d) => {
                  const holiday = holidayNames.get(d);
                  return (
                    <th
                      key={d}
                      scope="col"
                      title={holiday}
                      aria-current={d === today ? "date" : undefined}
                      className={cn(
                        "min-w-9 border-b border-border px-0.5 py-2 text-center text-[12px] font-medium tabular-nums",
                        d === today ? "text-accent-soft-text" : "text-muted",
                        (off.has(isoWeekday(d)) || holiday) && "bg-surface-2",
                      )}
                    >
                      <span className="block text-[10px] uppercase">{formatDay(d, { weekday: "narrow", day: undefined, month: undefined, year: undefined })}</span>
                      {formatNumber(Number(d.slice(8)))}
                      {holiday && <span className="sr-only">, {holiday}</span>}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {table.map((r) => (
                <tr key={r.id}>
                  <th scope="row" className="sticky left-0 z-10 max-w-48 truncate border-b border-r border-border bg-surface px-4 py-2 text-left font-medium">
                    {r.name}
                  </th>
                  {days.map((d) => {
                    const e = r.byDay.get(d);
                    const dayOff = off.has(isoWeekday(d)) || holidayNames.has(d);
                    return (
                      <td key={d} className={cn("border-b border-border p-0.5 text-center", dayOff && "bg-surface-2")}>
                        {e && (
                          <span
                            className={cn(
                              "mx-auto block h-6 w-full min-w-6 rounded-md",
                              e.status === "approved" ? "bg-accent" : "border-2 border-dashed border-accent",
                              e.half_day !== "none" && "w-1/2",
                            )}
                            style={e.color ? (e.status === "approved" ? { background: e.color } : { borderColor: e.color }) : undefined}
                            title={`${e.leave_type_name ?? t("leave.away")} · ${t(`leave.status.${e.status}`)}`}
                          >
                            <span className="sr-only">
                              {e.leave_type_name ?? t("leave.away")}, {t(`leave.status.${e.status}`)}
                            </span>
                          </span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          {away.data && table.length === 0 && <EmptyState icon={<CalendarRange />} title={t("leave.noAway")} />}
        </div>
      </Card>
    </div>
  );
}
