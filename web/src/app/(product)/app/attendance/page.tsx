"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, Download, Pencil, Plus, Wrench } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api, download } from "@/api/client";
import { useCorrections, usePresent } from "@/api/hooks";
import type { AttendanceRecord, Correction, Page, Timesheet } from "@/api/types";
import { useSession, useWorkspace } from "@/auth/session";
import { ClockCard } from "@/components/attendance/clock-card";
import { CorrectionDialog } from "@/components/attendance/correction-dialog";
import { GeoBadge } from "@/components/attendance/geo-badge";
import { PageHeader } from "@/components/page";
import { PeopleSelect } from "@/components/people-select";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, EmptyState } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select } from "@/components/ui/input";
import { Table, Td, Th } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/cn";
import { applyFieldErrors, errorMessage } from "@/lib/errors";
import { formatDay, formatDuration, formatNumber, formatTime, isoToZoned, todayIn, zonedToIso } from "@/lib/format";
import { useTab } from "@/lib/use-tab";
import { daysBetween, lastDayOfMonth } from "@/lib/week";

const statusTone = { open: "accent", closed: "success", auto_closed: "warn" } as const;

function useRecords(filters: Record<string, string | undefined>) {
  return useInfiniteQuery({
    queryKey: ["attendance", "records", filters],
    queryFn: ({ pageParam }) => api<Page<AttendanceRecord>>("/v1/attendance/records", { query: { ...filters, cursor: pageParam, limit: 50 } }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
}

function RecordsTable({
  filters,
  showPerson,
  onFix,
  onEdit,
}: {
  filters: Record<string, string | undefined>;
  showPerson: boolean;
  onFix?: (r: AttendanceRecord) => void;
  onEdit?: (r: AttendanceRecord) => void;
}) {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const records = useRecords(filters);
  const rows = records.data?.pages.flatMap((p) => p.items) ?? [];
  if (records.data && rows.length === 0) {
    return (
      <Card>
        <EmptyState icon={<ClipboardList />} title={t("attendance.noRecords")} />
      </Card>
    );
  }
  return (
    <Card className="overflow-hidden">
      <Table label={t("attendance.tabs.records")}>
        <thead>
          <tr>
            <Th>{t("common.date")}</Th>
            {showPerson && <Th>{t("attendance.person")}</Th>}
            <Th>{t("attendance.in")}</Th>
            <Th>{t("attendance.out")}</Th>
            <Th>{t("attendance.duration")}</Th>
            <Th>{t("attendance.location")}</Th>
            <Th>{t("common.status")}</Th>
            {(onFix || onEdit) && (
              <Th>
                <span className="sr-only">{t("common.actions")}</span>
              </Th>
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="hover:bg-surface-2/60">
              <Td className="whitespace-nowrap">{formatDay(r.business_date, { weekday: "short" })}</Td>
              {showPerson && <Td className="max-w-48 truncate font-medium">{r.employee_name}</Td>}
              <Td className="tabular-nums">{formatTime(r.clock_in_at, timezone)}</Td>
              <Td className="tabular-nums">{r.clock_out_at ? formatTime(r.clock_out_at, timezone) : <Badge tone="accent">{t("attendance.stillWorking")}</Badge>}</Td>
              <Td className="whitespace-nowrap tabular-nums">{formatDuration(r.minutes, t)}</Td>
              <Td>
                <span className="flex flex-wrap gap-1">
                  <GeoBadge geo={r.in_geo} distance={r.in_distance_m} label={t("attendance.in")} />
                  <GeoBadge geo={r.out_geo} distance={r.out_distance_m} label={t("attendance.out")} />
                  {!r.in_geo && !r.out_geo && <span className="text-muted">–</span>}
                </span>
              </Td>
              <Td>
                <span className="flex flex-wrap gap-1">
                  <Badge tone={statusTone[r.status as keyof typeof statusTone] ?? "neutral"}>{t(`attendance.status.${r.status}`)}</Badge>
                  {r.source !== "self" && <Badge>{t(`attendance.source.${r.source}`)}</Badge>}
                </span>
              </Td>
              {(onFix || onEdit) && (
                <Td className="text-right">
                  {onFix && r.clock_out_at && (
                    <Button size="sm" variant="ghost" onClick={() => onFix(r)}>
                      <Wrench aria-hidden="true" />
                      {t("attendance.requestFix")}
                    </Button>
                  )}
                  {onEdit && (
                    <Button size="sm" variant="ghost" onClick={() => onEdit(r)} aria-label={`${t("common.edit")}: ${r.employee_name ?? ""} ${formatDay(r.business_date)}`}>
                      <Pencil aria-hidden="true" />
                      {t("common.edit")}
                    </Button>
                  )}
                </Td>
              )}
            </tr>
          ))}
        </tbody>
      </Table>
      {records.hasNextPage && (
        <div className="border-t border-border p-3 text-center">
          <Button onClick={() => void records.fetchNextPage()} loading={records.isFetchingNextPage}>
            {t("common.loadMore")}
          </Button>
        </div>
      )}
    </Card>
  );
}

const requestTone = { pending: "warn", approved: "success", rejected: "danger", cancelled: "neutral" } as const;

function CorrectionsList({ mine }: { mine: boolean }) {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState(mine ? "all" : "pending");
  const list = useCorrections(status, mine);
  const decide = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "approve" | "reject" | "cancel" }) =>
      api(`/v1/attendance/corrections/${id}/${action}`, { method: "POST", body: action === "cancel" ? undefined : {} }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["attendance"] }),
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <div className="flex flex-col gap-3">
      <Field label={t("common.status")} className="w-52">
        <Select value={status} onChange={(e) => setStatus(e.target.value)}>
          {["pending", "approved", "rejected", "cancelled", "all"].map((s) => (
            <option key={s} value={s}>
              {s === "all" ? t("common.all") : t(`attendance.requestStatus.${s}`)}
            </option>
          ))}
        </Select>
      </Field>
      {list.data?.length === 0 && (
        <Card>
          <EmptyState icon={<ClipboardList />} title={t("attendance.noRequests")} />
        </Card>
      )}
      <ul className="grid gap-3 lg:grid-cols-2">
        {(list.data ?? []).map((c: Correction) => (
          <li key={c.id}>
            <Card className="flex h-full flex-col gap-3 p-4">
              <div className="flex items-start gap-3">
                {!mine && <Avatar name={c.employee_name ?? "?"} className="size-9" />}
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">{mine ? t(`attendance.kind.${c.kind}`) : `${c.employee_name} · ${t(`attendance.kind.${c.kind}`)}`}</p>
                  {c.proposed_clock_in_at && (
                    <p className="text-sm text-muted tabular-nums">
                      {formatDay(isoToZoned(c.proposed_clock_in_at, timezone).slice(0, 10), { weekday: "short" })} · {formatTime(c.proposed_clock_in_at, timezone)} – {formatTime(c.proposed_clock_out_at, timezone)}
                    </p>
                  )}
                </div>
                <Badge tone={requestTone[c.status as keyof typeof requestTone] ?? "neutral"}>{t(`attendance.requestStatus.${c.status}`)}</Badge>
              </div>
              <blockquote className="rounded-lg bg-surface-2 px-3 py-2 text-sm">{c.reason}</blockquote>
              {c.decision_note && <p className="text-sm text-muted">→ {c.decision_note}</p>}
              {c.status === "pending" && (
                <div className="mt-auto flex gap-2">
                  {mine ? (
                    <Button size="sm" onClick={() => decide.mutate({ id: c.id, action: "cancel" })}>
                      {t("attendance.cancelRequest")}
                    </Button>
                  ) : (
                    <>
                      <Button size="sm" variant="solid" onClick={() => decide.mutate({ id: c.id, action: "approve" })} disabled={decide.isPending}>
                        {t("attendance.approve")}
                      </Button>
                      <Button size="sm" onClick={() => decide.mutate({ id: c.id, action: "reject" })} disabled={decide.isPending}>
                        {t("attendance.reject")}
                      </Button>
                    </>
                  )}
                </div>
              )}
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}

interface RecordValues {
  employee_id: string;
  clock_in_at: string;
  clock_out_at: string;
  note: string;
}

function RecordDialog({ record, onClose }: { record: AttendanceRecord | "new"; onClose: () => void }) {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const queryClient = useQueryClient();
  const isNew = record === "new";
  const [confirming, setConfirming] = useState(false);
  const { register, handleSubmit, setError, formState } = useForm<RecordValues>({
    defaultValues: isNew
      ? { employee_id: "", clock_in_at: "", clock_out_at: "", note: "" }
      : {
          employee_id: record.employee_id,
          clock_in_at: isoToZoned(record.clock_in_at, timezone),
          clock_out_at: record.clock_out_at ? isoToZoned(record.clock_out_at, timezone) : "",
          note: record.note ?? "",
        },
  });
  const done = () => {
    void queryClient.invalidateQueries({ queryKey: ["attendance"] });
    onClose();
  };
  const save = useMutation({
    mutationFn: (v: RecordValues) => {
      const body = {
        clock_in_at: zonedToIso(v.clock_in_at, timezone),
        clock_out_at: v.clock_out_at ? zonedToIso(v.clock_out_at, timezone) : undefined,
        note: v.note.trim() || undefined,
      };
      return isNew
        ? api("/v1/attendance/records", { body: { ...body, employee_id: v.employee_id } })
        : api(`/v1/attendance/records/${record.id}`, { method: "PATCH", body, version: record.version });
    },
    onSuccess: done,
    onError: (e) => {
      if (!applyFieldErrors(setError, ["employee_id", "clock_in_at", "clock_out_at", "note"], e)) toast.error(errorMessage(e));
    },
  });
  const remove = useMutation({
    mutationFn: () => api(`/v1/attendance/records/${(record as AttendanceRecord).id}`, { method: "DELETE" }),
    onSuccess: done,
    onError: (e) => toast.error(errorMessage(e)),
  });
  const required = { required: t("common.required") };
  return (
    <>
      <Dialog open onOpenChange={(o) => !o && onClose()}>
        <DialogContent
          title={isNew ? t("attendance.addRecord") : t("attendance.editRecord")}
          description={isNew ? undefined : (record.employee_name ?? undefined)}
          closeLabel={t("common.close")}
          footer={
            <>
              {!isNew && (
                <Button variant="ghost" className="mr-auto text-danger" onClick={() => setConfirming(true)}>
                  {t("common.delete")}
                </Button>
              )}
              <Button onClick={onClose}>{t("common.cancel")}</Button>
              <Button variant="primary" type="submit" form="record-form" loading={save.isPending}>
                {t("common.save")}
              </Button>
            </>
          }
        >
          <form id="record-form" onSubmit={handleSubmit((v) => save.mutate(v))} className="flex flex-col gap-4" noValidate>
            {isNew && (
              <Field label={t("attendance.person")} error={formState.errors.employee_id?.message}>
                <PeopleSelect emptyLabel={t("attendance.choosePerson")} {...register("employee_id", required)} />
              </Field>
            )}
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t("attendance.in")} error={formState.errors.clock_in_at?.message}>
                <Input type="datetime-local" {...register("clock_in_at", required)} />
              </Field>
              <Field label={t("attendance.out")} optional={t("common.optional")} error={formState.errors.clock_out_at?.message}>
                <Input type="datetime-local" {...register("clock_out_at")} />
              </Field>
            </div>
            <Field label={t("common.note")} optional={t("common.optional")}>
              <Input maxLength={500} {...register("note")} />
            </Field>
          </form>
        </DialogContent>
      </Dialog>
      <ConfirmDialog
        open={confirming}
        title={t("attendance.deleteRecord")}
        confirmLabel={t("common.delete")}
        busy={remove.isPending}
        onConfirm={() => remove.mutate()}
        onClose={() => setConfirming(false)}
      />
    </>
  );
}

function DateRange({ from, to, onChange }: { from: string; to: string; onChange: (from: string, to: string) => void }) {
  const { t } = useTranslation();
  return (
    <>
      <Field label={t("attendance.from")} className="w-40">
        <Input type="date" value={from} max={to || undefined} onChange={(e) => onChange(e.target.value, to)} />
      </Field>
      <Field label={t("attendance.to")} className="w-40">
        <Input type="date" value={to} min={from || undefined} onChange={(e) => onChange(from, e.target.value)} />
      </Field>
    </>
  );
}

function AllRecords() {
  const { t } = useTranslation();
  const { can } = useSession();
  const [person, setPerson] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [editing, setEditing] = useState<AttendanceRecord | "new" | null>(null);
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <Field label={t("attendance.person")} className="w-60">
          <PeopleSelect value={person} onChange={(e) => setPerson(e.target.value)} />
        </Field>
        <DateRange
          from={from}
          to={to}
          onChange={(f, tt) => {
            setFrom(f);
            setTo(tt);
          }}
        />
        {can("attendance.manage") && (
          <Button className="ml-auto" onClick={() => setEditing("new")}>
            <Plus aria-hidden="true" />
            {t("attendance.addRecord")}
          </Button>
        )}
      </div>
      <RecordsTable filters={{ employee_id: person || undefined, from: from || undefined, to: to || undefined }} showPerson onEdit={can("attendance.manage") ? setEditing : undefined} />
      {editing && <RecordDialog record={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function TodayTab() {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const present = usePresent();
  const today = todayIn(timezone);
  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader title={t("home.whoIsIn")} action={<Badge tone="accent">{formatNumber(present.data?.length ?? 0)}</Badge>} />
        <div className="px-5 pb-5 pt-3">
          {present.data?.length === 0 && <p className="text-sm text-muted">{t("home.nobodyIn")}</p>}
          <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {(present.data ?? []).map((p) => (
              <li key={p.employee_id} className="flex items-center gap-3 rounded-xl border border-border bg-surface-2 px-3 py-2.5">
                <Avatar name={p.employee_name} />
                <span className="min-w-0 flex-1 truncate text-sm font-medium">{p.employee_name}</span>
                <span className="text-sm text-muted tabular-nums">{formatTime(p.clock_in_at, timezone)}</span>
              </li>
            ))}
          </ul>
        </div>
      </Card>
      <RecordsTable filters={{ from: today, to: today }} showPerson />
    </div>
  );
}

function TimesheetTab() {
  const { t } = useTranslation();
  const { can } = useSession();
  const { timezone } = useWorkspace();
  const today = todayIn(timezone);
  const thisMonth = today.slice(0, 7);
  const [month, setMonth] = useState(thisMonth);
  const sheet = useQuery({ queryKey: ["attendance", "timesheet", month], queryFn: () => api<Timesheet>("/v1/attendance/timesheet", { query: { month } }) });
  const scroller = useRef<HTMLDivElement>(null);
  const first = `${month}-01`;
  const last = lastDayOfMonth(month);
  const days = useMemo(() => daysBetween(first, last), [first, last]);
  const [from, setFrom] = useState(first);
  const [to, setTo] = useState(last);

  // In the current month, scroll just far enough that today's column is in view.
  useEffect(() => {
    const el = scroller.current;
    if (!sheet.data || month !== thisMonth || !el) return;
    const cell = el.querySelector<HTMLElement>(`[data-day="${today}"]`);
    if (!cell) return;
    const overflow = cell.offsetLeft + cell.offsetWidth - el.clientWidth + 16;
    el.scrollLeft = Math.max(0, overflow);
  }, [sheet.data, month, thisMonth, today]);

  const exportCsv = async () => {
    try {
      await download("/v1/attendance/export.csv", { from, to }, `attendance-${from}-to-${to}.csv`);
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <Field label={t("attendance.month")} className="w-44">
          <Input
            type="month"
            value={month}
            onChange={(e) => {
              if (!e.target.value) return;
              setMonth(e.target.value);
              setFrom(`${e.target.value}-01`);
              setTo(lastDayOfMonth(e.target.value));
            }}
          />
        </Field>
        {can("attendance.export") && (
          <div className="ml-auto flex flex-wrap items-end gap-3">
            <DateRange
              from={from}
              to={to}
              onChange={(f, tt) => {
                setFrom(f);
                setTo(tt);
              }}
            />
            <Button onClick={() => void exportCsv()}>
              <Download aria-hidden="true" />
              {t("attendance.exportCsv")}
            </Button>
          </div>
        )}
      </div>
      <Card className="overflow-hidden">
        <div ref={scroller} className="relative overflow-x-auto" role="region" aria-label={t("attendance.tabs.timesheet")} tabIndex={0}>
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                <th scope="col" className="sticky left-0 z-10 min-w-44 border-b border-r border-border bg-surface px-4 py-2.5 text-left text-[13px] font-medium text-muted">
                  {t("attendance.person")}
                </th>
                <th scope="col" className="border-b border-border px-3 py-2.5 text-left text-[13px] font-medium text-muted">
                  {t("attendance.total")}
                </th>
                <th scope="col" className="border-b border-border px-3 py-2.5 text-left text-[13px] font-medium text-muted">
                  {t("attendance.daysPresent")}
                </th>
                {days.map((d) => (
                  <th
                    key={d}
                    scope="col"
                    data-day={d}
                    aria-current={d === today ? "date" : undefined}
                    className={cn("min-w-11 border-b border-border px-1 py-2.5 text-center text-[12px] font-medium tabular-nums", d === today ? "text-accent-soft-text" : "text-muted")}
                  >
                    {formatNumber(Number(d.slice(8)))}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(sheet.data?.rows ?? []).map((r) => {
                const byDay = new Map(r.days.map((d) => [d.date, d]));
                return (
                  <tr key={r.employee_id}>
                    <th scope="row" className="sticky left-0 z-10 max-w-52 truncate border-b border-r border-border bg-surface px-4 py-2.5 text-left font-medium">
                      {r.employee_name}
                    </th>
                    <td className="whitespace-nowrap border-b border-border px-3 py-2.5 font-semibold tabular-nums">{formatDuration(r.total_minutes, t)}</td>
                    <td className="border-b border-border px-3 py-2.5 tabular-nums">{formatNumber(r.days_present)}</td>
                    {days.map((d) => {
                      const day = byDay.get(d);
                      return (
                        <td key={d} className="border-b border-border px-1 py-2.5 text-center tabular-nums" title={day ? formatDuration(day.minutes, t) : undefined}>
                          {day ? (
                            <span className={day.needs_review ? "font-semibold text-warn-text" : ""}>{formatNumber(Math.round((day.minutes / 60) * 10) / 10)}</span>
                          ) : (
                            <span className="text-border-strong" aria-hidden="true">·</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
          {sheet.data?.rows.length === 0 && <EmptyState icon={<ClipboardList />} title={t("attendance.noRecords")} />}
        </div>
      </Card>
      <p className="text-[13px] text-muted">{t("attendance.timesheetHelp")}</p>
    </div>
  );
}

function MineTab() {
  const { t } = useTranslation();
  const [fix, setFix] = useState<AttendanceRecord | "add" | null>(null);
  return (
    <div className="flex flex-col gap-5">
      <div className="grid gap-4 lg:grid-cols-2">
        <ClockCard />
      </div>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">{t("attendance.myRecords")}</h2>
        <Button onClick={() => setFix("add")}>
          <Plus aria-hidden="true" />
          {t("attendance.addMissing")}
        </Button>
      </div>
      <RecordsTable filters={{ mine: "true" }} showPerson={false} onFix={setFix} />
      <h2 className="text-lg font-semibold">{t("attendance.tabs.corrections")}</h2>
      <CorrectionsList mine />
      {fix && <CorrectionDialog record={fix === "add" ? undefined : fix} onClose={() => setFix(null)} />}
    </div>
  );
}

export default function AttendancePage() {
  const { t } = useTranslation();
  const { can, hasModule } = useSession();
  const tabs = [
    { key: "mine", label: t("attendance.tabs.mine"), content: <MineTab />, show: can("attendance.self") },
    { key: "today", label: t("attendance.tabs.today"), content: <TodayTab />, show: can("attendance.view") },
    { key: "records", label: t("attendance.tabs.records"), content: <AllRecords />, show: can("attendance.view") },
    { key: "corrections", label: t("attendance.tabs.corrections"), content: <CorrectionsList mine={false} />, show: can("attendance.approve") },
    { key: "timesheet", label: t("attendance.tabs.timesheet"), content: <TimesheetTab />, show: true },
  ].filter((x) => x.show);
  const [active, setActive] = useTab(tabs.map((x) => x.key));
  if (!hasModule("attendance")) return <EmptyState icon={<ClipboardList />} title={t("common.notAllowed")} />;
  return (
    <>
      <PageHeader title={t("attendance.title")} sub={t("attendance.sub")} />
      <Tabs value={active} onValueChange={setActive}>
        <TabsList className="mb-5 w-fit">
          {tabs.map((x) => (
            <TabsTrigger key={x.key} value={x.key}>
              {x.label}
            </TabsTrigger>
          ))}
        </TabsList>
        {tabs.map((x) => (
          <TabsContent key={x.key} value={x.key}>
            {active === x.key && x.content}
          </TabsContent>
        ))}
      </Tabs>
    </>
  );
}
