import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Checkbox, Dropdown, Form, Input, Modal, Select, Tabs, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Mail, MoreVertical, Shield, UserPlus, Users } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import { api } from "@/api/client";
import { departmentOptions, keys, useDepartments, useRoles } from "@/api/hooks";
import type { Invite, Member, Page, Permission, Role, StaffCreated } from "@/api/types";
import { useSession, useWorkspace } from "@/auth/session";
import DataTable from "@/components/DataTable";
import { Banner, EmptyState, PageHeader, Pill } from "@/components/ui";
import { applyFieldErrors, errorMessage } from "@/lib/errors";
import { formatDay } from "@/lib/format";

function useInvalidateTeam() {
  const queryClient = useQueryClient();
  return () => Promise.all(["members", "invites", "roles", "people"].map((k) => queryClient.invalidateQueries({ queryKey: [k] })));
}

function RoleScopeFields({ roles }: { roles: Role[] }) {
  const { t } = useTranslation();
  const departments = useDepartments();
  return (
    <>
      <Form.Item name="role_id" label={t("common.role")} rules={[{ required: true }]}>
        <Select options={roles.filter((r) => r.key !== "owner" || true).map((r) => ({ value: r.id, label: r.name }))} />
      </Form.Item>
      <Form.Item name="scope_department_id" label={t("team.scope")} extra={t("team.onlyDepartment")}>
        <Select allowClear placeholder={t("team.wholeWorkspace")} options={departmentOptions(departments.data)} />
      </Form.Item>
    </>
  );
}

function InviteModal({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const { message } = App.useApp();
  const roles = useRoles();
  const invalidate = useInvalidateTeam();
  const [form] = Form.useForm();
  const employee = roles.data?.find((r) => r.key === "employee")?.id;
  const send = useMutation({
    mutationFn: (v: Record<string, unknown>) => api<Invite>("/v1/invites", { body: v }),
    onSuccess: async (invite) => {
      void message.success(t("team.inviteSent", { email: invite.email }));
      await invalidate();
      onClose();
    },
    onError: (e) => {
      if (!applyFieldErrors(form, e)) void message.error(errorMessage(e));
    },
  });
  return (
    <Modal open title={t("team.invite")} onCancel={onClose} onOk={() => form.submit()} okText={t("team.invite")} cancelText={t("common.cancel")} confirmLoading={send.isPending}>
      <Form form={form} layout="vertical" requiredMark={false} initialValues={{ role_id: employee }} onFinish={(v) => send.mutate(v)} key={employee}>
        <Form.Item name="email" label={t("common.email")} rules={[{ required: true, type: "email" }]}>
          <Input inputMode="email" autoComplete="off" />
        </Form.Item>
        <Form.Item name="name" label={`${t("common.name")} (${t("common.optional")})`}>
          <Input />
        </Form.Item>
        <RoleScopeFields roles={roles.data ?? []} />
      </Form>
    </Modal>
  );
}

function Secret({ label, value, testId }: { label: string; value: string; testId?: string }) {
  return (
    <div className="rounded-xl bg-slate-50 px-3 py-2" data-testid={testId}>
      <p className="text-xs text-slate-500">{label}</p>
      <Typography.Text copyable className="font-mono text-base">
        {value}
      </Typography.Text>
    </div>
  );
}

function StaffModal({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const { message } = App.useApp();
  const roles = useRoles();
  const invalidate = useInvalidateTeam();
  const [form] = Form.useForm();
  const [created, setCreated] = useState<StaffCreated | null>(null);
  const employee = roles.data?.find((r) => r.key === "employee")?.id;
  const add = useMutation({
    mutationFn: (v: Record<string, unknown>) => api<StaffCreated>("/v1/members/staff", { body: { ...v, password: v.password || undefined } }),
    onSuccess: async (result) => {
      await invalidate();
      setCreated(result);
    },
    onError: (e) => {
      if (!applyFieldErrors(form, e)) void message.error(errorMessage(e));
    },
  });
  if (created) {
    return (
      <Modal open title={t("team.staffCreated")} onCancel={onClose} footer={<Button type="primary" onClick={onClose}>{t("common.close")}</Button>}>
        <p className="mb-3 text-slate-600">{t("team.staffShare")}</p>
        <div className="flex flex-col gap-2">
          <Secret label={t("team.workspaceCode")} value={created.workspace_code} testId="workspace-code" />
          <Secret label={t("team.username")} value={created.member.username ?? ""} testId="username" />
          {created.temporary_password ? <Secret label={t("team.temporaryPassword")} value={created.temporary_password} testId="temporary-password" /> : null}
        </div>
      </Modal>
    );
  }
  return (
    <Modal open title={t("team.addStaff")} onCancel={onClose} onOk={() => form.submit()} okText={t("common.add")} cancelText={t("common.cancel")} confirmLoading={add.isPending}>
      <p className="mb-4 text-sm text-slate-500">{t("team.staffHelp")}</p>
      <Form form={form} layout="vertical" requiredMark={false} initialValues={{ role_id: employee }} onFinish={(v) => add.mutate(v)} key={employee}>
        <Form.Item name="name" label={t("common.name")} rules={[{ required: true, whitespace: true }]}>
          <Input autoComplete="off" />
        </Form.Item>
        <Form.Item name="username" label={t("team.username")} rules={[{ required: true, pattern: /^[A-Za-z0-9][A-Za-z0-9._-]{2,39}$/ }]}>
          <Input autoComplete="off" autoCapitalize="none" />
        </Form.Item>
        <Form.Item name="password" label={t("team.passwordOptional")}>
          <Input.Password autoComplete="new-password" />
        </Form.Item>
        <RoleScopeFields roles={roles.data ?? []} />
      </Form>
    </Modal>
  );
}

function Members() {
  const { t } = useTranslation();
  const { can, workspace } = useSession();
  const { message, modal } = App.useApp();
  const roles = useRoles();
  const departments = useDepartments();
  const invalidate = useInvalidateTeam();
  const [status, setStatus] = useState("active");
  const members = useQuery({ queryKey: keys.members(status), queryFn: () => api<Page<Member>>("/v1/members", { query: { status, limit: 200 } }) });
  const manage = can("members.manage");
  const deptNames = new Map((departments.data ?? []).map((d) => [d.id, d.name]));

  const update = useMutation({
    mutationFn: ({ m, body }: { m: Member; body: Record<string, unknown> }) => api(`/v1/members/${m.id}`, { method: "PATCH", body, version: m.version }),
    onSuccess: invalidate,
    onError: async (e) => {
      void message.error(errorMessage(e));
      await invalidate();
    },
  });
  const remove = useMutation({
    mutationFn: (m: Member) => api(`/v1/members/${m.id}`, { method: "DELETE" }),
    onSuccess: invalidate,
    onError: (e) => void message.error(errorMessage(e)),
  });
  const reset = async (m: Member) => {
    try {
      const r = await api<{ temporary_password: string }>(`/v1/members/${m.id}/reset-password`, { method: "POST" });
      modal.info({ title: t("team.newTemporary"), content: <Secret label={m.username ?? m.name} value={r.temporary_password} /> });
    } catch (e) {
      void message.error(errorMessage(e));
    }
  };

  const columns: ColumnsType<Member> = [
    {
      title: t("common.name"),
      dataIndex: "name",
      render: (name: string, m) => (
        <span className="flex flex-col">
          <span dir="auto" className="font-medium text-ink">
            {name} {m.id === workspace?.membership_id ? <span className="text-slate-400">({t("team.you")})</span> : null}
          </span>
          <span className="text-xs text-slate-500">{m.email ?? `@${m.username}`}</span>
          <span className="mt-1 flex flex-wrap gap-1">
            {m.staff_account ? <Pill>{t("team.staffBadge")}</Pill> : null}
            {m.mfa_enabled ? <Pill tone="green">{t("team.mfaBadge")}</Pill> : null}
            {m.status !== "active" ? <Pill tone="amber">{t(`team.status.${m.status}`)}</Pill> : null}
          </span>
        </span>
      ),
    },
    {
      title: t("common.role"),
      dataIndex: "role_id",
      render: (roleId: string, m) =>
        manage && m.id !== workspace?.membership_id && m.status !== "removed" ? (
          <Select
            size="small"
            value={roleId}
            className="min-w-36"
            aria-label={t("team.changeRole")}
            onChange={(value) => update.mutate({ m, body: { role_id: value } })}
            options={(roles.data ?? []).map((r) => ({ value: r.id, label: r.name }))}
          />
        ) : (
          m.role
        ),
    },
    {
      title: t("team.scope"),
      dataIndex: "scope_department_id",
      responsive: ["md"],
      render: (id: string | null, m) =>
        manage && m.id !== workspace?.membership_id && m.status !== "removed" ? (
          <Select
            size="small"
            allowClear
            value={id ?? undefined}
            placeholder={t("team.wholeWorkspace")}
            className="min-w-40"
            aria-label={t("team.scope")}
            onChange={(value?: string) => update.mutate({ m, body: value ? { scope_department_id: value } : { clear_scope: true } })}
            options={departmentOptions(departments.data)}
          />
        ) : id ? (
          deptNames.get(id)
        ) : (
          t("team.wholeWorkspace")
        ),
    },
    {
      title: <span className="sr-only">{t("common.actions")}</span>,
      key: "actions",
      width: 56,
      render: (_: unknown, m) =>
        manage && m.id !== workspace?.membership_id && m.status !== "removed" ? (
          <Dropdown
            trigger={["click"]}
            menu={{
              items: [
                m.status === "active"
                  ? { key: "pause", label: t("team.disable"), onClick: () => update.mutate({ m, body: { status: "disabled" } }) }
                  : { key: "resume", label: t("team.enable"), onClick: () => update.mutate({ m, body: { status: "active" } }) },
                ...(m.staff_account ? [{ key: "reset", label: t("team.resetPassword"), onClick: () => void reset(m) }] : []),
                { type: "divider" as const },
                {
                  key: "remove",
                  danger: true,
                  label: t("common.remove"),
                  onClick: () =>
                    modal.confirm({
                      title: t("team.removeConfirm", { name: m.name }),
                      okText: t("common.remove"),
                      okButtonProps: { danger: true },
                      cancelText: t("common.cancel"),
                      onOk: () => remove.mutateAsync(m),
                    }),
                },
              ],
            }}
          >
            <Button type="text" icon={<MoreVertical size={16} />} aria-label={t("common.actions")} />
          </Dropdown>
        ) : null,
    },
  ];

  return (
    <>
      <Select
        value={status}
        onChange={setStatus}
        className="mb-3 w-40"
        aria-label={t("common.status")}
        options={["active", "disabled", "removed"].map((s) => ({ value: s, label: t(`team.status.${s}`) }))}
      />
      <DataTable<Member> rowKey="id" columns={columns} dataSource={members.data?.items ?? []} loading={members.isPending} pagination={false} />
    </>
  );
}

function Invitations() {
  const { t } = useTranslation();
  const { message } = App.useApp();
  const invalidate = useInvalidateTeam();
  const invites = useQuery({ queryKey: keys.invites, queryFn: () => api<Invite[]>("/v1/invites") });
  const revoke = useMutation({
    mutationFn: (id: string) => api(`/v1/invites/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
    onError: (e) => void message.error(errorMessage(e)),
  });
  if (invites.data?.length === 0) return <EmptyState icon={Mail} title={t("team.noInvites")} />;
  return (
    <ul className="flex flex-col gap-2">
      {(invites.data ?? []).map((i) => (
        <li key={i.id} className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3">
          <span className="min-w-0">
            <span className="block truncate font-medium text-ink">{i.name ? `${i.name} · ${i.email}` : i.email}</span>
            <span className="text-xs text-slate-500">{t("team.expires", { date: formatDay(i.expires_at.slice(0, 10)) })}</span>
          </span>
          <Button size="small" onClick={() => revoke.mutate(i.id)}>
            {t("team.revoke")}
          </Button>
        </li>
      ))}
    </ul>
  );
}

function Roles() {
  const { t } = useTranslation();
  const { can } = useSession();
  const workspace = useWorkspace();
  const { message } = App.useApp();
  const roles = useRoles();
  const invalidate = useInvalidateTeam();
  const catalog = useQuery({ queryKey: ["permissions"], queryFn: () => api<Permission[]>("/v1/permissions") });
  const [editing, setEditing] = useState<Role | "new" | null>(null);
  const [form] = Form.useForm();
  const allowed = Boolean(workspace.plan.features.custom_roles);
  const labels = new Map((catalog.data ?? []).map((p) => [p.key, p.label]));
  const save = useMutation({
    mutationFn: (v: Record<string, unknown>) =>
      editing === "new" ? api("/v1/roles", { body: v }) : api(`/v1/roles/${(editing as Role).id}`, { method: "PATCH", body: v }),
    onSuccess: async () => {
      await invalidate();
      setEditing(null);
    },
    onError: (e) => {
      if (!applyFieldErrors(form, e)) void message.error(errorMessage(e));
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/v1/roles/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      await invalidate();
      setEditing(null);
    },
    onError: (e) => void message.error(errorMessage(e)),
  });
  const groups = new Map<string, Permission[]>();
  for (const p of catalog.data ?? []) {
    if (p.owner_only) continue;
    groups.set(p.module, [...(groups.get(p.module) ?? []), p]);
  }
  return (
    <>
      {can("roles.manage") ? (
        allowed ? (
          <div className="mb-3 flex justify-end">
            <Button
              type="primary"
              icon={<Shield size={16} />}
              onClick={() => {
                setEditing("new");
                form.setFieldsValue({ name: "", description: "", permissions: [] });
              }}
            >
              {t("team.customRole")}
            </Button>
          </div>
        ) : (
          <Banner icon={Shield}>{t("team.customRolesPlan")}</Banner>
        )
      ) : null}
      <ul className="grid gap-3 md:grid-cols-2">
        {(roles.data ?? []).map((r) => (
          <li key={r.id}>
            <button
              type="button"
              disabled={r.is_builtin || !can("roles.manage")}
              onClick={() => {
                setEditing(r);
                form.setFieldsValue({ name: r.name, description: r.description ?? "", permissions: r.permissions });
              }}
              className="h-full w-full rounded-2xl border border-slate-200 bg-white p-4 text-left transition enabled:hover:border-brand disabled:cursor-default"
            >
              <span className="flex items-center justify-between gap-2">
                <span className="font-semibold text-ink">{r.name}</span>
                <span className="flex gap-1">
                  {r.is_builtin ? <Pill>{t("team.builtin")}</Pill> : null}
                  <Pill tone="brand">{t("team.membersCount", { count: r.members })}</Pill>
                </span>
              </span>
              {r.description ? <span className="mt-1 block text-sm text-slate-500">{r.description}</span> : null}
              <span className="mt-2 block text-xs text-slate-500">{r.permissions.length > 12 ? `${r.permissions.length} ${t("team.permissions").toLowerCase()}` : r.permissions.map((p) => labels.get(p) ?? p).join(" · ")}</span>
            </button>
          </li>
        ))}
      </ul>
      <Modal
        open={editing !== null}
        title={editing === "new" ? t("team.customRole") : t("common.edit")}
        onCancel={() => setEditing(null)}
        onOk={() => form.submit()}
        okText={t("common.save")}
        cancelText={t("common.cancel")}
        confirmLoading={save.isPending}
        footer={(orig) => (
          <div className="flex justify-between gap-2">
            {editing && editing !== "new" ? (
              <Button danger onClick={() => remove.mutate(editing.id)}>
                {t("common.delete")}
              </Button>
            ) : (
              <span />
            )}
            <span className="flex gap-2">{orig}</span>
          </div>
        )}
        styles={{ body: { maxHeight: "65vh", overflowY: "auto" } }}
      >
        <Form form={form} layout="vertical" requiredMark={false} onFinish={(v) => save.mutate(v)}>
          <Form.Item name="name" label={t("team.roleName")} rules={[{ required: true, whitespace: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label={t("team.description")}>
            <Input maxLength={300} />
          </Form.Item>
          <Form.Item name="permissions" label={t("team.permissions")}>
            <Checkbox.Group className="flex w-full flex-col gap-3">
              {[...groups.entries()].map(([module, perms]) => (
                <fieldset key={module} className="rounded-xl border border-slate-200 p-3">
                  <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{module}</legend>
                  <div className="flex flex-col gap-1">
                    {perms.map((p) => (
                      <Checkbox key={p.key} value={p.key}>
                        {p.label}
                      </Checkbox>
                    ))}
                  </div>
                </fieldset>
              ))}
            </Checkbox.Group>
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

export default function TeamPage() {
  const { t } = useTranslation();
  const { can, me } = useSession();
  const [params, setParams] = useSearchParams();
  const [modal, setModal] = useState<"invite" | "staff" | null>(null);
  if (!can("members.view")) return <EmptyState icon={Users} title={t("common.notAllowed")} />;
  const tabs = ["members", "invites", "roles"];
  const active = tabs.includes(params.get("tab") ?? "") ? (params.get("tab") as string) : "members";
  const canInvite = can("members.invite");
  return (
    <>
      <PageHeader
        title={t("team.title")}
        sub={t("team.sub")}
        actions={
          canInvite ? (
            <>
              <Button icon={<UserPlus size={16} />} onClick={() => setModal("staff")}>
                {t("team.addStaff")}
              </Button>
              <Button type="primary" icon={<Mail size={16} />} onClick={() => setModal("invite")} disabled={Boolean(me?.email && !me.email_verified)}>
                {t("team.invite")}
              </Button>
            </>
          ) : null
        }
      />
      {canInvite && me?.email && !me.email_verified ? <Banner icon={Mail} tone="amber">{t("team.verifyFirst")}</Banner> : null}
      <Tabs
        activeKey={active}
        onChange={(k) => setParams({ tab: k }, { replace: true })}
        items={[
          { key: "members", label: t("team.tabs.members"), children: <Members /> },
          { key: "invites", label: t("team.tabs.invites"), children: <Invitations /> },
          { key: "roles", label: t("team.tabs.roles"), children: <Roles /> },
        ]}
      />
      {modal === "invite" ? <InviteModal onClose={() => setModal(null)} /> : null}
      {modal === "staff" ? <StaffModal onClose={() => setModal(null)} /> : null}
    </>
  );
}
