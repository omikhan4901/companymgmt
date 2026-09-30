import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { App, Button, DatePicker, Drawer, Form, Input, Modal, Popconfirm, Select, Tabs, Tree } from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { FolderTree, Plus, UsersRound } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import { api } from "@/api/client";
import { departmentOptions, useBranches, useDepartments } from "@/api/hooks";
import type { Department, Employee, Page } from "@/api/types";
import { useSession } from "@/auth/session";
import DataTable from "@/components/DataTable";
import { EmptyState, PageHeader, Pill } from "@/components/ui";
import { applyFieldErrors, errorMessage } from "@/lib/errors";
import { formatDay, normalizeDigits } from "@/lib/format";

const TYPES = ["full_time", "part_time", "contract", "intern", "daily"];
const STATUSES = ["active", "inactive", "left"];
const DATE_FIELDS = ["joined_on", "left_on", "date_of_birth"] as const;

type FormValues = Record<string, unknown>;

function PersonDrawer({ person, onClose }: { person: Employee | "new"; onClose: () => void }) {
  const { t } = useTranslation();
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const departments = useDepartments();
  const branches = useBranches();
  const [form] = Form.useForm<FormValues>();
  const isNew = person === "new";

  const initial = useMemo(() => {
    if (isNew) return { employment_type: "full_time" };
    const values: FormValues = { ...person };
    for (const f of DATE_FIELDS) values[f] = person[f] ? dayjs(person[f]) : undefined;
    return values;
  }, [person, isNew]);

  const save = useMutation({
    mutationFn: (values: FormValues) => {
      const body: FormValues = {};
      const clear: string[] = [];
      for (const [key, raw] of Object.entries(values)) {
        let value = raw;
        if (DATE_FIELDS.includes(key as (typeof DATE_FIELDS)[number])) value = raw ? (raw as dayjs.Dayjs).format("YYYY-MM-DD") : null;
        if (key === "phone" && typeof value === "string") value = normalizeDigits(value);
        if (value === "" || value === undefined) value = null;
        if (isNew) {
          if (value !== null) body[key] = value;
        } else if (value === null) {
          if ((person as Record<string, unknown>)[key] !== null && key !== "national_id") clear.push(key);
        } else if (value !== (person as Record<string, unknown>)[key]) body[key] = value;
      }
      if (!isNew && clear.length) body.clear = clear;
      return isNew
        ? api<Employee>("/v1/people", { body })
        : api<Employee>(`/v1/people/${person.id}`, { method: "PATCH", body, version: person.version });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["people"] });
      await queryClient.invalidateQueries({ queryKey: ["departments"] });
      onClose();
    },
    onError: (e) => {
      if (!applyFieldErrors(form, e)) void message.error(errorMessage(e));
    },
  });

  return (
    <Drawer
      open
      onClose={onClose}
      title={isNew ? t("people.add") : t("people.editTitle", { name: person.full_name })}
      size="default"
      destroyOnHidden
      footer={
        <div className="flex justify-end gap-2">
          <Button onClick={onClose}>{t("common.cancel")}</Button>
          <Button type="primary" loading={save.isPending} onClick={() => form.submit()}>
            {t("common.save")}
          </Button>
        </div>
      }
    >
      <Form form={form} layout="vertical" requiredMark={false} initialValues={initial} onFinish={(v) => save.mutate(v)}>
        <Form.Item name="full_name" label={t("people.fullName")} rules={[{ required: true, whitespace: true, max: 200 }]}>
          <Input autoComplete="off" />
        </Form.Item>
        <div className="grid gap-x-3 sm:grid-cols-2">
          <Form.Item name="preferred_name" label={t("people.preferredName")}>
            <Input maxLength={100} />
          </Form.Item>
          <Form.Item name="employee_code" label={t("people.code")}>
            <Input maxLength={40} />
          </Form.Item>
          <Form.Item name="phone" label={t("people.phone")}>
            <Input inputMode="tel" maxLength={40} />
          </Form.Item>
          <Form.Item name="email" label={t("common.email")} rules={[{ type: "email" }]}>
            <Input inputMode="email" />
          </Form.Item>
          <Form.Item name="department_id" label={t("people.department")}>
            <Select allowClear options={departmentOptions(departments.data)} />
          </Form.Item>
          <Form.Item name="branch_id" label={t("people.branch")}>
            <Select allowClear options={(branches.data ?? []).filter((b) => b.is_active).map((b) => ({ value: b.id, label: b.name }))} />
          </Form.Item>
          <Form.Item name="job_title" label={t("people.jobTitle")}>
            <Input maxLength={120} />
          </Form.Item>
          <Form.Item name="employment_type" label={t("people.employmentType")}>
            <Select options={TYPES.map((v) => ({ value: v, label: t(`people.types.${v}`) }))} />
          </Form.Item>
          <Form.Item name="joined_on" label={t("people.joinedOn")}>
            <DatePicker className="w-full" />
          </Form.Item>
          <Form.Item name="date_of_birth" label={t("people.dateOfBirth")}>
            <DatePicker className="w-full" disabledDate={(d) => d.isAfter(dayjs())} />
          </Form.Item>
          {!isNew ? (
            <>
              <Form.Item name="status" label={t("common.status")}>
                <Select options={STATUSES.map((v) => ({ value: v, label: t(`people.status.${v}`) }))} />
              </Form.Item>
              <Form.Item name="left_on" label={t("people.leftOn")}>
                <DatePicker className="w-full" />
              </Form.Item>
            </>
          ) : null}
        </div>
        <Form.Item
          name="national_id"
          label={t("people.nationalId")}
          extra={!isNew && person.national_id_last4 ? t("people.nationalIdSaved", { last4: person.national_id_last4 }) : undefined}
        >
          <Input autoComplete="off" maxLength={40} />
        </Form.Item>
        <Form.Item name="notes" label={t("people.notes")}>
          <Input.TextArea rows={3} maxLength={5000} />
        </Form.Item>
      </Form>
    </Drawer>
  );
}

function PeopleList() {
  const { t } = useTranslation();
  const { can } = useSession();
  const [q, setQ] = useState("");
  const query = useDeferredValue(q);
  const [department, setDepartment] = useState<string | undefined>();
  const [status, setStatus] = useState("active");
  const [editing, setEditing] = useState<Employee | "new" | null>(null);
  const departments = useDepartments();
  const names = new Map((departments.data ?? []).map((d) => [d.id, d.name]));
  const people = useInfiniteQuery({
    queryKey: ["people", { q: query, department, status }],
    queryFn: ({ pageParam }) =>
      api<Page<Employee>>("/v1/people", { query: { q: query, department_id: department, status, cursor: pageParam, limit: 50 } }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
  const rows = people.data?.pages.flatMap((p) => p.items) ?? [];
  const tones = { active: "green", inactive: "slate", left: "amber" } as const;
  const columns: ColumnsType<Employee> = [
    {
      title: t("common.name"),
      dataIndex: "full_name",
      render: (name: string, p) => (
        <span className="flex flex-col">
          <span dir="auto" className="font-medium text-ink">{name}</span>
          <span className="text-xs text-slate-500">{[p.job_title, p.employee_code].filter(Boolean).join(" · ")}</span>
        </span>
      ),
    },
    { title: t("people.department"), dataIndex: "department_id", render: (id: string | null) => (id ? names.get(id) : "–"), responsive: ["md"] },
    { title: t("people.phone"), dataIndex: "phone", responsive: ["lg"], render: (v: string | null) => <span className="tabular">{v ?? "–"}</span> },
    { title: t("people.joinedOn"), dataIndex: "joined_on", responsive: ["lg"], render: (d: string | null) => formatDay(d) || "–" },
    {
      title: t("common.status"),
      dataIndex: "status",
      render: (s: keyof typeof tones, p) => (
        <span className="flex flex-wrap gap-1">
          <Pill tone={tones[s]}>{t(`people.status.${s}`)}</Pill>
          {p.membership_id ? <Pill tone="brand">{t("people.hasLogin")}</Pill> : null}
        </span>
      ),
    },
  ];
  return (
    <>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Input.Search value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("people.searchPlaceholder")} allowClear className="max-w-sm" aria-label={t("common.search")} />
        <Select allowClear value={department} onChange={setDepartment} placeholder={t("people.department")} className="min-w-44" options={departmentOptions(departments.data)} aria-label={t("people.department")} />
        <Select value={status} onChange={setStatus} className="w-36" aria-label={t("common.status")} options={[...STATUSES, "all"].map((s) => ({ value: s, label: s === "all" ? t("common.all") : t(`people.status.${s}`) }))} />
        {can("people.manage") ? (
          <Button type="primary" icon={<Plus size={16} />} onClick={() => setEditing("new")} className="ml-auto">
            {t("people.add")}
          </Button>
        ) : null}
      </div>
      {!people.isPending && rows.length === 0 && !q ? (
        <EmptyState icon={UsersRound} title={t("people.empty")} />
      ) : (
        <DataTable<Employee>
          rowKey="id"
          columns={columns}
          dataSource={rows}
          loading={people.isPending}
          pagination={false}
          onRow={(p) => ({
            onClick: () => (can("people.manage") ? setEditing(p) : undefined),
            onKeyDown: (e) => {
              if (e.key === "Enter" && can("people.manage")) setEditing(p);
            },
            tabIndex: can("people.manage") ? 0 : -1,
            className: can("people.manage") ? "cursor-pointer" : "",
          })}
        />
      )}
      {people.hasNextPage ? (
        <div className="mt-3 text-center">
          <Button onClick={() => void people.fetchNextPage()} loading={people.isFetchingNextPage}>
            {t("common.loadMore")}
          </Button>
        </div>
      ) : null}
      {editing ? <PersonDrawer person={editing} onClose={() => setEditing(null)} /> : null}
    </>
  );
}

function DepartmentsTab() {
  const { t } = useTranslation();
  const { can } = useSession();
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const departments = useDepartments();
  const [editing, setEditing] = useState<Department | "new" | null>(null);
  const [form] = Form.useForm<{ name: string; parent_id?: string }>();
  const manage = can("departments.manage");

  const tree = useMemo(() => {
    const list = departments.data ?? [];
    type Node = { key: string; title: React.ReactNode; children: Node[] };
    const nodes = new Map<string, Node>();
    for (const d of list) {
      nodes.set(d.id, {
        key: d.id,
        title: (
          <span className="inline-flex items-center gap-2">
            <span className="font-medium text-ink">{d.name}</span>
            <span className="text-xs text-slate-500">{t("people.peopleCount", { count: d.people })}</span>
          </span>
        ),
        children: [],
      });
    }
    const roots: Node[] = [];
    for (const d of list) {
      const node = nodes.get(d.id)!;
      const parent = d.parent_id ? nodes.get(d.parent_id) : undefined;
      if (parent) parent.children.push(node);
      else roots.push(node);
    }
    return roots;
  }, [departments.data, t]);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["departments"] });
  const save = useMutation({
    mutationFn: (v: { name: string; parent_id?: string }) => {
      if (editing === "new") return api("/v1/departments", { body: { name: v.name, parent_id: v.parent_id || undefined } });
      const d = editing as Department;
      return api(`/v1/departments/${d.id}`, {
        method: "PATCH",
        version: d.version,
        body: { name: v.name, ...(v.parent_id ? { parent_id: v.parent_id } : d.parent_id ? { move_to_top: true } : {}) },
      });
    },
    onSuccess: async () => {
      await invalidate();
      setEditing(null);
    },
    onError: (e) => {
      if (!applyFieldErrors(form, e)) void message.error(errorMessage(e));
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/v1/departments/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      await invalidate();
      setEditing(null);
    },
    onError: (e) => void message.error(errorMessage(e)),
  });

  const open = (d: Department | "new") => {
    setEditing(d);
    form.setFieldsValue(d === "new" ? { name: "", parent_id: undefined } : { name: d.name, parent_id: d.parent_id ?? undefined });
  };

  return (
    <>
      <div className="mb-3 flex justify-end">
        {manage ? (
          <Button type="primary" icon={<Plus size={16} />} onClick={() => open("new")}>
            {t("people.addDepartment")}
          </Button>
        ) : null}
      </div>
      {departments.data?.length === 0 ? (
        <EmptyState icon={FolderTree} title={t("people.noDepartments")} />
      ) : (
        <div className="rounded-2xl border border-slate-200 bg-white p-3">
          <Tree
            treeData={tree}
            defaultExpandAll
            blockNode
            selectable={manage}
            onSelect={(keys) => {
              const d = departments.data?.find((x) => x.id === keys[0]);
              if (d && manage) open(d);
            }}
          />
        </div>
      )}
      <Modal
        open={editing !== null}
        title={editing === "new" ? t("people.addDepartment") : t("common.edit")}
        onCancel={() => setEditing(null)}
        onOk={() => form.submit()}
        okText={t("common.save")}
        cancelText={t("common.cancel")}
        confirmLoading={save.isPending}
        footer={(orig) => (
          <div className="flex justify-between gap-2">
            {editing && editing !== "new" ? (
              <Popconfirm title={t("common.delete")} onConfirm={() => remove.mutate(editing.id)} okButtonProps={{ danger: true }}>
                <Button danger>{t("common.delete")}</Button>
              </Popconfirm>
            ) : (
              <span />
            )}
            <span className="flex gap-2">{orig}</span>
          </div>
        )}
      >
        <Form form={form} layout="vertical" requiredMark={false} onFinish={(v) => save.mutate(v)}>
          <Form.Item name="name" label={t("people.departmentName")} rules={[{ required: true, whitespace: true, max: 120 }]}>
            <Input />
          </Form.Item>
          <Form.Item name="parent_id" label={t("people.parent")}>
            <Select
              allowClear
              placeholder={t("people.topLevel")}
              options={departmentOptions(departments.data).filter((o) => editing === "new" || o.value !== (editing as Department | null)?.id)}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

export default function PeoplePage() {
  const { t } = useTranslation();
  const { can } = useSession();
  const [params, setParams] = useSearchParams();
  if (!can("people.view")) return <EmptyState icon={UsersRound} title={t("common.notAllowed")} />;
  const active = params.get("tab") === "departments" ? "departments" : "people";
  return (
    <>
      <PageHeader title={t("people.title")} sub={t("people.sub")} />
      <Tabs
        activeKey={active}
        onChange={(k) => setParams({ tab: k }, { replace: true })}
        items={[
          { key: "people", label: t("people.tabs.people"), children: <PeopleList /> },
          { key: "departments", label: t("people.tabs.departments"), children: <DepartmentsTab /> },
        ]}
      />
    </>
  );
}
