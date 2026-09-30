import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Form, Input, Modal, Select, Switch, Tabs } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Plus, Settings as SettingsIcon, ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import { api } from "@/api/client";
import { useBranches } from "@/api/hooks";
import type { AuditEvent, Branch, Page, Workspace } from "@/api/types";
import { useSession, useWorkspace } from "@/auth/session";
import PlanCards from "@/components/PlanCards";
import DataTable from "@/components/DataTable";
import { Banner, Card, EmptyState, PageHeader, Pill } from "@/components/ui";
import { applyFieldErrors, errorMessage } from "@/lib/errors";
import { formatDateTime, formatDay } from "@/lib/format";
import { countryOptions, CURRENCIES, timezoneOptions } from "@/lib/places";

function WorkspaceForm() {
  const { t } = useTranslation();
  const { message } = App.useApp();
  const { reload } = useSession();
  const [form] = Form.useForm();
  const current = useQuery({ queryKey: ["workspace"], queryFn: () => api<Workspace>("/v1/workspace") });
  const save = useMutation({
    mutationFn: (v: Record<string, unknown>) => api<Workspace>("/v1/workspace", { method: "PATCH", body: v }),
    onSuccess: async () => {
      void message.success(t("common.save"));
      await reload();
    },
    onError: (e) => {
      if (!applyFieldErrors(form, e)) void message.error(errorMessage(e));
    },
  });
  if (!current.data) return null;
  const months = Array.from({ length: 12 }, (_, i) => ({
    value: i + 1,
    label: new Intl.DateTimeFormat(undefined, { month: "long", timeZone: "UTC" }).format(new Date(Date.UTC(2026, i, 1))),
  }));
  const days = Array.from({ length: 7 }, (_, i) => ({
    value: i,
    label: new Intl.DateTimeFormat(undefined, { weekday: "long", timeZone: "UTC" }).format(new Date(Date.UTC(2026, 1, 1 + i))),
  }));
  return (
    <Card className="max-w-2xl">
      <Form form={form} layout="vertical" requiredMark={false} initialValues={current.data} onFinish={(v) => save.mutate(v)}>
        <Form.Item name="name" label={t("settings.workspaceName")} rules={[{ required: true, whitespace: true, max: 120 }]}>
          <Input />
        </Form.Item>
        <div className="grid gap-x-3 sm:grid-cols-2">
          <Form.Item name="country" label={t("signup.country")}>
            <Select showSearch optionFilterProp="label" options={countryOptions()} />
          </Form.Item>
          <Form.Item name="currency" label={t("settings.currency")}>
            <Select showSearch options={CURRENCIES.map((c) => ({ value: c, label: c }))} />
          </Form.Item>
          <Form.Item name="timezone" label={t("settings.timezone")}>
            <Select showSearch optionFilterProp="label" options={timezoneOptions()} />
          </Form.Item>
          <Form.Item name="locale" label={t("settings.language")}>
            <Select options={[{ value: "en", label: "English" }, { value: "bn", label: "বাংলা" }]} />
          </Form.Item>
          <Form.Item name="week_start" label={t("settings.weekStart")}>
            <Select options={days} />
          </Form.Item>
          <Form.Item name="fiscal_year_start_month" label={t("settings.fiscalYear")}>
            <Select options={months} />
          </Form.Item>
        </div>
        <Form.Item name="ui_mode" label={t("settings.uiMode")} extra={t("settings.uiModeHelp")}>
          <Select options={["simple", "standard", "advanced"].map((m) => ({ value: m, label: t(`settings.uiModes.${m}`) }))} />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={save.isPending}>
          {t("common.save")}
        </Button>
      </Form>
    </Card>
  );
}

interface ModuleInfo {
  key: string;
  name: string;
  core: boolean;
  requires: string[];
  available: boolean;
}

function Modules() {
  const { t } = useTranslation();
  const { message } = App.useApp();
  const { reload } = useSession();
  const workspace = useWorkspace();
  const modules = useQuery({ queryKey: ["modules"], queryFn: () => api<ModuleInfo[]>("/v1/modules"), staleTime: 3_600_000 });
  const enabled = new Set([...workspace.plan.modules, ...workspace.plan.locked_modules]);
  const save = useMutation({
    mutationFn: (list: string[]) => api<string[]>("/v1/workspace/modules", { method: "PUT", body: { modules: list } }),
    onSuccess: reload,
    onError: (e) => void message.error(errorMessage(e)),
  });
  const names = new Map((modules.data ?? []).map((m) => [m.key, m.name]));
  const toggle = (key: string, on: boolean) => {
    const optional = [...enabled].filter((k) => !(modules.data ?? []).find((m) => m.key === k)?.core);
    save.mutate(on ? [...optional, key] : optional.filter((k) => k !== key));
  };
  return (
    <div className="max-w-2xl">
      <p className="mb-3 text-slate-600">{t("settings.modulesSub")}</p>
      {workspace.plan.max_modules !== null ? <p className="mb-3 text-sm text-slate-500">{t("settings.modulesLimit", { limit: workspace.plan.max_modules })}</p> : null}
      <ul className="flex flex-col gap-2">
        {(modules.data ?? []).map((m) => (
          <li key={m.key} className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3">
            <span>
              <span className="font-medium text-ink">{m.name}</span>
              <span className="ml-2 inline-flex gap-1 align-middle">
                {m.core ? <Pill tone="brand">{t("settings.core")}</Pill> : null}
                {!m.available ? <Pill>{t("common.comingSoon")}</Pill> : null}
                {workspace.plan.locked_modules.includes(m.key) ? <Pill tone="amber">{t("settings.modulesLimit", { limit: workspace.plan.max_modules })}</Pill> : null}
              </span>
              {m.requires.length ? <span className="block text-xs text-slate-500">{t("settings.needs", { names: m.requires.map((r) => names.get(r) ?? r).join(", ") })}</span> : null}
            </span>
            <Switch
              checked={m.core || enabled.has(m.key)}
              disabled={m.core || !m.available || save.isPending}
              onChange={(on) => toggle(m.key, on)}
              aria-label={m.name}
            />
          </li>
        ))}
      </ul>
    </div>
  );
}

function Branches() {
  const { t } = useTranslation();
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const workspace = useWorkspace();
  const branches = useBranches();
  const [editing, setEditing] = useState<Branch | "new" | null>(null);
  const [form] = Form.useForm();
  const save = useMutation({
    mutationFn: (v: Record<string, unknown>) =>
      editing === "new" ? api("/v1/branches", { body: v }) : api(`/v1/branches/${(editing as Branch).id}`, { method: "PATCH", body: v, version: (editing as Branch).version }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["branches"] });
      setEditing(null);
    },
    onError: (e) => {
      if (!applyFieldErrors(form, e)) void message.error(errorMessage(e));
    },
  });
  const open = (b: Branch | "new") => {
    setEditing(b);
    form.setFieldsValue(b === "new" ? { name: "", timezone: workspace.timezone, address: "" } : { ...b });
  };
  return (
    <div className="max-w-2xl">
      <div className="mb-3 flex justify-end">
        <Button type="primary" icon={<Plus size={16} />} onClick={() => open("new")}>
          {t("settings.addBranch")}
        </Button>
      </div>
      <ul className="flex flex-col gap-2">
        {(branches.data ?? []).map((b) => (
          <li key={b.id}>
            <button type="button" onClick={() => open(b)} className="flex w-full items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left hover:border-brand">
              <span>
                <span className="block font-medium text-ink">{b.name}</span>
                <span className="text-xs text-slate-500">{[b.timezone, b.address].filter(Boolean).join(" · ")}</span>
              </span>
              <Pill tone={b.is_active ? "green" : "slate"}>{b.is_active ? t("settings.open") : t("settings.closed")}</Pill>
            </button>
          </li>
        ))}
      </ul>
      <Modal open={editing !== null} title={editing === "new" ? t("settings.addBranch") : t("common.edit")} onCancel={() => setEditing(null)} onOk={() => form.submit()} okText={t("common.save")} cancelText={t("common.cancel")} confirmLoading={save.isPending}>
        <Form form={form} layout="vertical" requiredMark={false} onFinish={(v) => save.mutate(v)}>
          <Form.Item name="name" label={t("settings.branchName")} rules={[{ required: true, whitespace: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="timezone" label={t("settings.timezone")}>
            <Select showSearch optionFilterProp="label" options={timezoneOptions()} />
          </Form.Item>
          <Form.Item name="address" label={t("settings.address")}>
            <Input.TextArea rows={2} maxLength={500} />
          </Form.Item>
          {editing && editing !== "new" ? (
            <Form.Item name="is_active" label={t("common.status")} valuePropName="checked">
              <Switch checkedChildren={t("settings.open")} unCheckedChildren={t("settings.closed")} />
            </Form.Item>
          ) : null}
        </Form>
      </Modal>
    </div>
  );
}

function PlanTab() {
  const { t } = useTranslation();
  const workspace = useWorkspace();
  const plan = workspace.plan;
  return (
    <>
      <Banner icon={Sparkles}>
        {t("settings.currentPlan")}: <strong>{plan.name}</strong>
        {plan.status === "trialing" && plan.trial_ends_at ? ` · ${t("settings.trialUntil", { date: formatDay(plan.trial_ends_at.slice(0, 10)) })}` : ""}
      </Banner>
      <p className="mb-4 text-sm text-slate-600">{t("settings.paymentsSoon")}</p>
      <PlanCards current={plan.key} />
    </>
  );
}

function Audit() {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const { message } = App.useApp();
  const [action, setAction] = useState<string | undefined>();
  const events = useInfiniteQuery({
    queryKey: ["audit", { action }],
    queryFn: ({ pageParam }) => api<Page<AuditEvent>>("/v1/audit", { query: { action, cursor: pageParam, limit: 50 } }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
  const verify = async () => {
    try {
      const r = await api<{ ok: boolean; first_bad_seq: number | null }>("/v1/audit/verify");
      if (r.ok) void message.success(t("settings.chainOk"));
      else void message.error(t("settings.chainBroken", { seq: r.first_bad_seq }));
    } catch (e) {
      void message.error(errorMessage(e));
    }
  };
  const rows = events.data?.pages.flatMap((p) => p.items) ?? [];
  const columns: ColumnsType<AuditEvent> = [
    { title: "#", dataIndex: "seq", width: 70, render: (n: number) => <span className="tabular text-slate-500">{n}</span> },
    { title: t("common.date"), dataIndex: "occurred_at", width: 150, render: (v: string) => <span className="tabular">{formatDateTime(v, timezone)}</span> },
    { title: t("common.name"), dataIndex: "actor_name", ellipsis: true },
    { title: t("common.actions"), dataIndex: "action", render: (a: string) => <code className="text-xs">{a}</code> },
    {
      title: t("common.note"),
      dataIndex: "data",
      responsive: ["lg"],
      render: (d: Record<string, unknown>) => <span className="line-clamp-2 break-all text-xs text-slate-500">{JSON.stringify(d)}</span>,
    },
  ];
  return (
    <>
      <p className="mb-3 text-slate-600">{t("settings.auditSub")}</p>
      <div className="mb-3 flex flex-wrap gap-2">
        <Select
          allowClear
          value={action}
          onChange={setAction}
          placeholder={t("settings.filterAction")}
          className="min-w-52"
          aria-label={t("settings.filterAction")}
          options={["workspace.", "member.", "invite.", "role.", "branch.", "department.", "person.", "attendance."].map((a) => ({ value: a, label: a.replace(".", "") }))}
        />
        <Button icon={<ShieldCheck size={16} />} onClick={() => void verify()} className="ml-auto">
          {t("settings.verifyChain")}
        </Button>
      </div>
      <DataTable<AuditEvent> rowKey="id" size="small" columns={columns} dataSource={rows} loading={events.isPending} pagination={false} scroll={{ x: 640 }} />
      {events.hasNextPage ? (
        <div className="mt-3 text-center">
          <Button onClick={() => void events.fetchNextPage()} loading={events.isFetchingNextPage}>
            {t("common.loadMore")}
          </Button>
        </div>
      ) : null}
    </>
  );
}

export default function SettingsPage() {
  const { t } = useTranslation();
  const { can } = useSession();
  const [params, setParams] = useSearchParams();
  const tabs = [
    { key: "workspace", label: t("settings.tabs.workspace"), children: <WorkspaceForm />, show: can("workspace.manage") },
    { key: "modules", label: t("settings.tabs.modules"), children: <Modules />, show: can("workspace.manage") },
    { key: "branches", label: t("settings.tabs.branches"), children: <Branches />, show: can("branches.manage") },
    { key: "plan", label: t("settings.tabs.plan"), children: <PlanTab />, show: can("workspace.manage") },
    { key: "audit", label: t("settings.tabs.audit"), children: <Audit />, show: can("audit.view") },
  ].filter((x) => x.show);
  if (!tabs.length) return <EmptyState icon={SettingsIcon} title={t("common.notAllowed")} />;
  const active = tabs.some((x) => x.key === params.get("tab")) ? (params.get("tab") as string) : tabs[0]?.key;
  return (
    <>
      <PageHeader title={t("settings.title")} />
      <Tabs activeKey={active} onChange={(k) => setParams({ tab: k }, { replace: true })} items={tabs} destroyOnHidden />
    </>
  );
}
