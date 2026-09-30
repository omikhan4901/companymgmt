import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, DatePicker, Form, Input, Modal, Popconfirm, Select, Tabs } from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs, { type Dayjs } from "dayjs";
import { ClipboardList, Download, Plus } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import { api, download } from "@/api/client";
import { useCorrections, usePresent } from "@/api/hooks";
import type { AttendanceRecord, Correction, Employee, Page, Timesheet } from "@/api/types";
import { useSession, useWorkspace } from "@/auth/session";
import ClockCard from "@/components/ClockCard";
import CorrectionModal from "@/components/CorrectionModal";
import DataTable from "@/components/DataTable";
import { Card, EmptyState, PageHeader, Pill } from "@/components/ui";
import { applyFieldErrors, errorMessage } from "@/lib/errors";
import { formatDay, formatDuration, formatTime, isoToZoned, todayIn, zonedToIso } from "@/lib/format";

const statusTone = { open: "brand", closed: "green", auto_closed: "amber" } as const;

function useRecords(filters: Record<string, string | undefined>, enabled = true) {
  return useInfiniteQuery({
    queryKey: ["attendance", "records", filters],
    queryFn: ({ pageParam }) => api<Page<AttendanceRecord>>("/v1/attendance/records", { query: { ...filters, cursor: pageParam, limit: 50 } }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled,
  });
}

function RecordsTable({ filters, showPerson, onFix, onEdit }: { filters: Record<string, string | undefined>; showPerson: boolean; onFix?: (r: AttendanceRecord) => void; onEdit?: (r: AttendanceRecord) => void }) {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const records = useRecords(filters);
  const rows = records.data?.pages.flatMap((p) => p.items) ?? [];
  const columns: ColumnsType<AttendanceRecord> = [
    { title: t("common.date"), dataIndex: "business_date", render: (d: string) => formatDay(d), width: 130 },
    ...(showPerson ? [{ title: t("attendance.person"), dataIndex: "employee_name", ellipsis: true }] : []),
    { title: t("attendance.in"), dataIndex: "clock_in_at", render: (v: string) => <span className="tabular">{formatTime(v, timezone)}</span> },
    {
      title: t("attendance.out"),
      dataIndex: "clock_out_at",
      render: (v: string | null) => (v ? <span className="tabular">{formatTime(v, timezone)}</span> : <Pill tone="brand">{t("attendance.stillWorking")}</Pill>),
    },
    { title: t("attendance.duration"), dataIndex: "minutes", render: (m: number | null) => <span className="tabular">{formatDuration(m, t)}</span> },
    {
      title: t("common.status"),
      dataIndex: "status",
      render: (s: keyof typeof statusTone, r) => (
        <span className="flex flex-wrap gap-1">
          <Pill tone={statusTone[s]}>{t(`attendance.status.${s}`)}</Pill>
          {r.source !== "self" ? <Pill>{t(`attendance.source.${r.source}`)}</Pill> : null}
        </span>
      ),
    },
    ...(onFix || onEdit
      ? [
          {
            title: <span className="sr-only">{t("common.actions")}</span>,
            key: "a",
            render: (_: unknown, r: AttendanceRecord) => (
              <span className="flex gap-1">
                {onFix && r.clock_out_at ? (
                  <Button size="small" onClick={() => onFix(r)}>
                    {t("attendance.requestFix")}
                  </Button>
                ) : null}
                {onEdit ? (
                  <Button size="small" onClick={() => onEdit(r)}>
                    {t("common.edit")}
                  </Button>
                ) : null}
              </span>
            ),
          },
        ]
      : []),
  ];
  return (
    <>
      <DataTable<AttendanceRecord>
        rowKey="id"
        size="middle"
        columns={columns}
        dataSource={rows}
        loading={records.isPending}
        pagination={false}
        scroll={{ x: 640 }}
        locale={{ emptyText: t("attendance.noRecords") }}
      />
      {records.hasNextPage ? (
        <div className="mt-3 text-center">
          <Button onClick={() => void records.fetchNextPage()} loading={records.isFetchingNextPage}>
            {t("common.loadMore")}
          </Button>
        </div>
      ) : null}
    </>
  );
}

function CorrectionsList({ mine }: { mine: boolean }) {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [status, setStatus] = useState(mine ? "all" : "pending");
  const list = useCorrections(status, mine);
  const decide = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "approve" | "reject" | "cancel" }) =>
      api(`/v1/attendance/corrections/${id}/${action}`, { body: action === "cancel" ? undefined : {} , method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["attendance"] }),
    onError: (e) => void message.error(errorMessage(e)),
  });
  const tone = { pending: "amber", approved: "green", rejected: "red", cancelled: "slate" } as const;
  return (
    <div>
      <Select
        value={status}
        onChange={setStatus}
        className="mb-3 w-48"
        aria-label={t("common.status")}
        options={["pending", "approved", "rejected", "cancelled", "all"].map((s) => ({ value: s, label: s === "all" ? t("common.all") : t(`attendance.requestStatus.${s}`) }))}
      />
      {list.data?.length === 0 ? <EmptyState icon={ClipboardList} title={t("attendance.noRequests")} /> : null}
      <ul className="flex flex-col gap-2">
        {(list.data ?? []).map((c: Correction) => (
          <li key={c.id} className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="font-semibold text-ink">
                  {mine ? t(`attendance.kind.${c.kind}`) : `${c.employee_name} · ${t(`attendance.kind.${c.kind}`)}`}
                </p>
                {c.proposed_clock_in_at ? (
                  <p className="text-sm text-slate-600 tabular">
                    {formatDay(isoToZoned(c.proposed_clock_in_at, timezone).slice(0, 10))} · {formatTime(c.proposed_clock_in_at, timezone)} – {formatTime(c.proposed_clock_out_at, timezone)}
                  </p>
                ) : null}
                <p className="mt-1 text-sm text-slate-500">“{c.reason}”</p>
                {c.decision_note ? <p className="mt-1 text-sm text-slate-500">→ {c.decision_note}</p> : null}
              </div>
              <Pill tone={tone[c.status as keyof typeof tone]}>{t(`attendance.requestStatus.${c.status}`)}</Pill>
            </div>
            {c.status === "pending" ? (
              <div className="mt-3 flex gap-2">
                {mine ? (
                  <Button size="small" onClick={() => decide.mutate({ id: c.id, action: "cancel" })}>
                    {t("attendance.cancelRequest")}
                  </Button>
                ) : (
                  <>
                    <Button type="primary" size="small" onClick={() => decide.mutate({ id: c.id, action: "approve" })}>
                      {t("attendance.approve")}
                    </Button>
                    <Button size="small" danger onClick={() => decide.mutate({ id: c.id, action: "reject" })}>
                      {t("attendance.reject")}
                    </Button>
                  </>
                )}
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

function PeopleSelect({ value, onChange, allowClear = true }: { value?: string; onChange: (v?: string) => void; allowClear?: boolean }) {
  const { t } = useTranslation();
  const [q, setQ] = useState("");
  const people = useQuery({
    queryKey: ["people", { q, limit: 50 }],
    queryFn: () => api<Page<Employee>>("/v1/people", { query: { q, limit: 50 } }),
  });
  return (
    <Select
      showSearch
      allowClear={allowClear}
      value={value}
      onChange={onChange}
      filterOption={false}
      onSearch={setQ}
      placeholder={t("attendance.person")}
      aria-label={t("attendance.person")}
      className="min-w-56"
      options={(people.data?.items ?? []).map((p) => ({ value: p.id, label: p.full_name }))}
    />
  );
}

function RecordModal({ record, onClose }: { record: AttendanceRecord | "new"; onClose: () => void }) {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [form] = Form.useForm();
  const isNew = record === "new";
  const done = () => {
    void queryClient.invalidateQueries({ queryKey: ["attendance"] });
    onClose();
  };
  const save = useMutation({
    mutationFn: (v: { employee_id?: string; clock_in_at: string; clock_out_at?: string; note?: string }) => {
      const body = {
        clock_in_at: zonedToIso(v.clock_in_at, timezone),
        clock_out_at: v.clock_out_at ? zonedToIso(v.clock_out_at, timezone) : undefined,
        note: v.note || undefined,
      };
      return isNew
        ? api("/v1/attendance/records", { body: { ...body, employee_id: v.employee_id } })
        : api(`/v1/attendance/records/${record.id}`, { method: "PATCH", body, version: record.version });
    },
    onSuccess: done,
    onError: (e) => {
      if (!applyFieldErrors(form, e)) void message.error(errorMessage(e));
    },
  });
  const remove = useMutation({
    mutationFn: () => api(`/v1/attendance/records/${(record as AttendanceRecord).id}`, { method: "DELETE" }),
    onSuccess: done,
    onError: (e) => void message.error(errorMessage(e)),
  });
  return (
    <Modal
      open
      title={isNew ? t("attendance.addRecord") : t("attendance.editRecord")}
      onCancel={onClose}
      onOk={() => form.submit()}
      okText={t("common.save")}
      cancelText={t("common.cancel")}
      confirmLoading={save.isPending}
      footer={(orig) => (
        <div className="flex justify-between gap-2">
          {!isNew ? (
            <Popconfirm title={t("common.delete")} onConfirm={() => remove.mutate()} okButtonProps={{ danger: true }}>
              <Button danger>{t("common.delete")}</Button>
            </Popconfirm>
          ) : (
            <span />
          )}
          <span className="flex gap-2">{orig}</span>
        </div>
      )}
    >
      <Form
        form={form}
        layout="vertical"
        requiredMark={false}
        onFinish={(v) => save.mutate(v)}
        initialValues={
          isNew
            ? {}
            : {
                clock_in_at: isoToZoned(record.clock_in_at, timezone),
                clock_out_at: record.clock_out_at ? isoToZoned(record.clock_out_at, timezone) : "",
                note: record.note ?? "",
              }
        }
      >
        {isNew ? (
          <Form.Item name="employee_id" label={t("attendance.person")} rules={[{ required: true }]}>
            <PeopleSelect onChange={(v) => form.setFieldValue("employee_id", v)} allowClear={false} />
          </Form.Item>
        ) : (
          <p className="mb-3 font-semibold text-ink">{record.employee_name}</p>
        )}
        <div className="grid gap-x-3 sm:grid-cols-2">
          <Form.Item name="clock_in_at" label={t("attendance.in")} rules={[{ required: true }]}>
            <Input type="datetime-local" />
          </Form.Item>
          <Form.Item name="clock_out_at" label={t("attendance.out")}>
            <Input type="datetime-local" />
          </Form.Item>
        </div>
        <Form.Item name="note" label={t("common.note")}>
          <Input maxLength={500} />
        </Form.Item>
      </Form>
    </Modal>
  );
}

function AllRecords() {
  const { t } = useTranslation();
  const { can } = useSession();
  const [person, setPerson] = useState<string | undefined>();
  const [range, setRange] = useState<[Dayjs, Dayjs] | null>(null);
  const [editing, setEditing] = useState<AttendanceRecord | "new" | null>(null);
  const filters = {
    employee_id: person,
    from: range?.[0].format("YYYY-MM-DD"),
    to: range?.[1].format("YYYY-MM-DD"),
  };
  return (
    <>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <PeopleSelect value={person} onChange={setPerson} />
        <DatePicker.RangePicker value={range} onChange={(v) => setRange(v as [Dayjs, Dayjs] | null)} aria-label={t("common.date")} />
        {can("attendance.manage") ? (
          <Button icon={<Plus size={16} />} onClick={() => setEditing("new")} className="ml-auto">
            {t("attendance.addRecord")}
          </Button>
        ) : null}
      </div>
      <RecordsTable filters={filters} showPerson onEdit={can("attendance.manage") ? setEditing : undefined} />
      {editing ? <RecordModal record={editing} onClose={() => setEditing(null)} /> : null}
    </>
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
        <h2 className="mb-3 font-display text-lg font-bold text-ink">{t("home.whoIsIn")}</h2>
        {present.data?.length === 0 ? <p className="text-slate-500">{t("home.nobodyIn")}</p> : null}
        <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {(present.data ?? []).map((p) => (
            <li key={p.employee_id} className="flex items-center justify-between rounded-xl bg-brand-50 px-3 py-2">
              <span className="truncate font-medium text-ink">{p.employee_name}</span>
              <span className="text-sm text-slate-600 tabular">{formatTime(p.clock_in_at, timezone)}</span>
            </li>
          ))}
        </ul>
      </Card>
      <RecordsTable filters={{ from: today, to: today }} showPerson />
    </div>
  );
}

function TimesheetTab() {
  const { t } = useTranslation();
  const { can } = useSession();
  const [month, setMonth] = useState<Dayjs>(dayjs());
  const key = month.format("YYYY-MM");
  const sheet = useQuery({ queryKey: ["attendance", "timesheet", key], queryFn: () => api<Timesheet>("/v1/attendance/timesheet", { query: { month: key } }) });
  const tableRef = useRef<HTMLDivElement>(null);
  // In the current month, open scrolled to the most recent days.
  useEffect(() => {
    if (!sheet.data || !month.isSame(dayjs(), "month")) return;
    const el = tableRef.current?.querySelector<HTMLElement>(".ant-table-content, .ant-table-body");
    if (el) el.scrollLeft = el.scrollWidth;
  }, [sheet.data, month]);
  const [range, setRange] = useState<[Dayjs, Dayjs]>([month.startOf("month"), month.endOf("month")]);
  const { message } = App.useApp();
  const days = useMemo(() => {
    const out: string[] = [];
    for (let d = month.startOf("month"); d.isBefore(month.endOf("month")) || d.isSame(month.endOf("month"), "day"); d = d.add(1, "day")) out.push(d.format("YYYY-MM-DD"));
    return out;
  }, [month]);
  type Row = Timesheet["rows"][number];
  const columns: ColumnsType<Row> = [
    { title: t("attendance.person"), dataIndex: "employee_name", fixed: "left", width: 180, ellipsis: true },
    { title: t("attendance.total"), dataIndex: "total_minutes", width: 120, render: (m: number) => <span className="tabular font-semibold">{formatDuration(m, t)}</span> },
    { title: t("attendance.daysPresent"), dataIndex: "days_present", width: 70, render: (n: number) => <span className="tabular">{n}</span> },
    ...days.map((d) => ({
      title: <span className="tabular">{Number(d.slice(8))}</span>,
      key: d,
      width: 52,
      align: "center" as const,
      render: (_: unknown, r: Row) => {
        const day = r.days.find((x) => x.date === d);
        if (!day) return <span className="text-slate-300">·</span>;
        const h = Math.round((day.minutes / 60) * 10) / 10;
        return <span className={`tabular ${day.needs_review ? "text-amber-700" : "text-ink"}`} title={formatDuration(day.minutes, t)}>{h}</span>;
      },
    })),
  ];
  const exportCsv = async () => {
    try {
      const from = range[0].format("YYYY-MM-DD");
      const to = range[1].format("YYYY-MM-DD");
      await download("/v1/attendance/export.csv", { from, to }, `attendance-${from}-to-${to}.csv`);
    } catch (e) {
      void message.error(errorMessage(e));
    }
  };
  return (
    <>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <DatePicker picker="month" value={month} onChange={(v) => v && setMonth(v)} allowClear={false} aria-label={t("attendance.month")} />
        {can("attendance.export") ? (
          <span className="ml-auto flex flex-wrap items-center gap-2">
            <DatePicker.RangePicker value={range} onChange={(v) => v && setRange(v as [Dayjs, Dayjs])} allowClear={false} aria-label={t("common.export")} />
            <Button icon={<Download size={16} />} onClick={() => void exportCsv()}>
              {t("attendance.exportCsv")}
            </Button>
          </span>
        ) : null}
      </div>
      <div ref={tableRef}>
      <DataTable<Row> rowKey="employee_id" size="small" columns={columns} dataSource={sheet.data?.rows ?? []} loading={sheet.isPending} pagination={false} scroll={{ x: 400 + days.length * 52 }} bordered aria-label={t("attendance.tabs.timesheet")} />
      </div>
    </>
  );
}

function MineTab() {
  const { t } = useTranslation();
  const [fix, setFix] = useState<AttendanceRecord | "add" | null>(null);
  return (
    <div className="flex flex-col gap-4">
      <ClockCard />
      <div className="flex flex-wrap justify-end">
        <Button icon={<Plus size={16} />} onClick={() => setFix("add")}>
          {t("attendance.addMissing")}
        </Button>
      </div>
      <RecordsTable filters={{ mine: "true" }} showPerson={false} onFix={setFix} />
      <h2 className="mt-2 font-display text-lg font-bold text-ink">{t("attendance.tabs.corrections")}</h2>
      <CorrectionsList mine />
      {fix ? <CorrectionModal record={fix === "add" ? undefined : fix} onClose={() => setFix(null)} /> : null}
    </div>
  );
}

export default function AttendancePage() {
  const { t } = useTranslation();
  const { can, hasModule } = useSession();
  const [params, setParams] = useSearchParams();
  if (!hasModule("attendance")) return <EmptyState icon={ClipboardList} title={t("common.notAllowed")} />;
  const tabs = [
    { key: "mine", label: t("attendance.tabs.mine"), children: <MineTab />, show: can("attendance.self") },
    { key: "today", label: t("attendance.tabs.today"), children: <TodayTab />, show: can("attendance.view") },
    { key: "records", label: t("attendance.tabs.records"), children: <AllRecords />, show: can("attendance.view") },
    { key: "corrections", label: t("attendance.tabs.corrections"), children: <CorrectionsList mine={false} />, show: can("attendance.approve") },
    { key: "timesheet", label: t("attendance.tabs.timesheet"), children: <TimesheetTab />, show: true },
  ].filter((x) => x.show);
  const active = tabs.some((x) => x.key === params.get("tab")) ? (params.get("tab") as string) : tabs[0]?.key;
  return (
    <>
      <PageHeader title={t("attendance.title")} sub={t("attendance.sub")} />
      <Tabs activeKey={active} onChange={(k) => setParams({ tab: k }, { replace: true })} items={tabs} destroyOnHidden />
    </>
  );
}
