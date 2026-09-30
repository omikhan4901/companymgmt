"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Mail, MoreHorizontal, Shield, ShieldCheck, UserPlus, Users } from "lucide-react";
import { DropdownMenu as M } from "radix-ui";
import { useState } from "react";
import { useForm, type UseFormRegister } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import { departmentOptions, keys, useDepartments, useRoles } from "@/api/hooks";
import type { Invite, Member, Page, Permission, Role, StaffCreated } from "@/api/types";
import { useSession, useWorkspace } from "@/auth/session";
import { PageHeader } from "@/components/page";
import { Secret } from "@/components/secret";
import { Alert } from "@/components/ui/alert";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, EmptyState } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select } from "@/components/ui/input";
import { MenuContent, MenuItem, MenuSeparator } from "@/components/ui/menu";
import { PasswordInput } from "@/components/ui/password";
import { Table, Td, Th } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { applyFieldErrors, errorMessage } from "@/lib/errors";
import { formatDay, formatNumber } from "@/lib/format";
import { useTab } from "@/lib/use-tab";

function useInvalidateTeam() {
  const queryClient = useQueryClient();
  return () => Promise.all(["members", "invites", "roles", "people"].map((k) => queryClient.invalidateQueries({ queryKey: [k] })));
}

interface AccessValues {
  role_id: string;
  scope_department_id: string;
}

function RoleScopeFields<T extends AccessValues>({ register }: { register: UseFormRegister<T> }) {
  const { t } = useTranslation();
  const roles = useRoles();
  const departments = useDepartments();
  const reg = register as unknown as UseFormRegister<AccessValues>;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label={t("common.role")}>
        <Select {...reg("role_id", { required: t("common.required") })}>
          {(roles.data ?? []).map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </Select>
      </Field>
      <Field label={t("team.scope")} help={t("team.scopeHelp")}>
        <Select {...reg("scope_department_id")}>
          <option value="">{t("team.wholeWorkspace")}</option>
          {departmentOptions(departments.data).map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </Select>
      </Field>
    </div>
  );
}

function accessBody(v: AccessValues) {
  return { role_id: v.role_id, scope_department_id: v.scope_department_id || undefined };
}

function InviteDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const roles = useRoles();
  const invalidate = useInvalidateTeam();
  const employee = roles.data?.find((r) => r.key === "employee")?.id ?? "";
  const { register, handleSubmit, setError, formState } = useForm<AccessValues & { email: string; name: string }>({
    values: { email: "", name: "", role_id: employee, scope_department_id: "" },
  });
  const send = useMutation({
    mutationFn: (v: AccessValues & { email: string; name: string }) => api<Invite>("/v1/invites", { body: { email: v.email.trim(), name: v.name.trim() || undefined, ...accessBody(v) } }),
    onSuccess: async (invite) => {
      toast.success(t("team.inviteSent", { email: invite.email }));
      await invalidate();
      onClose();
    },
    onError: (e) => {
      if (!applyFieldErrors(setError, ["email", "name", "role_id", "scope_department_id"], e)) toast.error(errorMessage(e));
    },
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={t("team.invite")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" type="submit" form="invite-form" loading={send.isPending}>
              {t("team.sendInvite")}
            </Button>
          </>
        }
      >
        <form id="invite-form" onSubmit={handleSubmit((v) => send.mutate(v))} className="flex flex-col gap-4" noValidate>
          <Field label={t("common.email")} error={formState.errors.email?.message}>
            <Input type="email" inputMode="email" autoComplete="off" {...register("email", { required: t("common.required") })} />
          </Field>
          <Field label={t("common.name")} optional={t("common.optional")}>
            <Input dir="auto" {...register("name")} />
          </Field>
          <RoleScopeFields register={register} />
        </form>
      </DialogContent>
    </Dialog>
  );
}

function StaffDialog({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const roles = useRoles();
  const invalidate = useInvalidateTeam();
  const [created, setCreated] = useState<StaffCreated | null>(null);
  const employee = roles.data?.find((r) => r.key === "employee")?.id ?? "";
  type Values = AccessValues & { name: string; username: string; password: string };
  const { register, handleSubmit, setError, formState } = useForm<Values>({
    values: { name: "", username: "", password: "", role_id: employee, scope_department_id: "" },
  });
  const add = useMutation({
    mutationFn: (v: Values) =>
      api<StaffCreated>("/v1/members/staff", { body: { name: v.name.trim(), username: v.username.trim(), password: v.password || undefined, ...accessBody(v) } }),
    onSuccess: async (result) => {
      await invalidate();
      setCreated(result);
    },
    onError: (e) => {
      if (!applyFieldErrors(setError, ["name", "username", "password", "role_id", "scope_department_id"], e)) toast.error(errorMessage(e));
    },
  });

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      {created ? (
        <DialogContent title={t("team.staffCreated")} description={t("team.staffShare")} closeLabel={t("common.close")} footer={<Button variant="primary" onClick={onClose}>{t("common.done")}</Button>}>
          <div className="flex flex-col gap-2">
            <Secret label={t("team.workspaceCode")} value={created.workspace_code} testId="workspace-code" />
            <Secret label={t("team.username")} value={created.member.username ?? ""} testId="username" />
            {created.temporary_password && <Secret label={t("team.temporaryPassword")} value={created.temporary_password} testId="temporary-password" />}
          </div>
        </DialogContent>
      ) : (
        <DialogContent
          title={t("team.addStaff")}
          description={t("team.staffHelp")}
          closeLabel={t("common.close")}
          footer={
            <>
              <Button onClick={onClose}>{t("common.cancel")}</Button>
              <Button variant="primary" type="submit" form="staff-form" loading={add.isPending}>
                {t("common.add")}
              </Button>
            </>
          }
        >
          <form id="staff-form" onSubmit={handleSubmit((v) => add.mutate(v))} className="flex flex-col gap-4" noValidate>
            <Field label={t("common.name")} error={formState.errors.name?.message}>
              <Input autoComplete="off" dir="auto" {...register("name", { validate: (v) => v.trim().length > 0 || t("common.required") })} />
            </Field>
            <Field label={t("team.username")} help={t("team.usernameHelp")} error={formState.errors.username?.message}>
              <Input
                autoComplete="off"
                autoCapitalize="none"
                {...register("username", { required: t("common.required"), pattern: { value: /^[A-Za-z0-9][A-Za-z0-9._-]{2,39}$/, message: t("team.usernameHelp") } })}
              />
            </Field>
            <Field label={t("team.passwordOptional")} error={formState.errors.password?.message}>
              <PasswordInput autoComplete="new-password" {...register("password")} />
            </Field>
            <RoleScopeFields register={register} />
          </form>
        </DialogContent>
      )}
    </Dialog>
  );
}

function MemberActions({ member, onRemove, onReset, onStatus }: { member: Member; onRemove: () => void; onReset: () => void; onStatus: (status: "active" | "disabled") => void }) {
  const { t } = useTranslation();
  return (
    <M.Root>
      <M.Trigger asChild>
        <Button size="iconSm" variant="ghost" aria-label={`${t("common.actions")}: ${member.name}`}>
          <MoreHorizontal aria-hidden="true" />
        </Button>
      </M.Trigger>
      <MenuContent>
        {member.status === "active" ? (
          <MenuItem onSelect={() => onStatus("disabled")}>{t("team.disable")}</MenuItem>
        ) : (
          <MenuItem onSelect={() => onStatus("active")}>{t("team.enable")}</MenuItem>
        )}
        {member.staff_account && <MenuItem onSelect={onReset}>{t("team.resetPassword")}</MenuItem>}
        <MenuSeparator />
        <MenuItem onSelect={onRemove} className="text-danger">
          {t("common.remove")}
        </MenuItem>
      </MenuContent>
    </M.Root>
  );
}

function Members() {
  const { t } = useTranslation();
  const { can, workspace } = useSession();
  const roles = useRoles();
  const departments = useDepartments();
  const invalidate = useInvalidateTeam();
  const [status, setStatus] = useState("active");
  const [removing, setRemoving] = useState<Member | null>(null);
  const [reset, setReset] = useState<{ member: Member; password: string } | null>(null);
  const members = useQuery({ queryKey: keys.members(status), queryFn: () => api<Page<Member>>("/v1/members", { query: { status, limit: 200 } }) });
  const manage = can("members.manage");
  const deptNames = new Map((departments.data ?? []).map((d) => [d.id, d.name]));

  const update = useMutation({
    mutationFn: ({ m, body }: { m: Member; body: Record<string, unknown> }) => api(`/v1/members/${m.id}`, { method: "PATCH", body, version: m.version }),
    onSuccess: invalidate,
    onError: async (e) => {
      toast.error(errorMessage(e));
      await invalidate();
    },
  });
  const remove = useMutation({
    mutationFn: (m: Member) => api(`/v1/members/${m.id}`, { method: "DELETE" }),
    onSuccess: async () => {
      setRemoving(null);
      await invalidate();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const resetPassword = async (m: Member) => {
    try {
      const r = await api<{ temporary_password: string }>(`/v1/members/${m.id}/reset-password`, { method: "POST" });
      setReset({ member: m, password: r.temporary_password });
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Field label={t("common.status")} className="w-44">
        <Select value={status} onChange={(e) => setStatus(e.target.value)}>
          {["active", "disabled", "removed"].map((s) => (
            <option key={s} value={s}>
              {t(`team.status.${s}`)}
            </option>
          ))}
        </Select>
      </Field>
      <Card className="overflow-hidden">
        <Table label={t("team.tabs.members")}>
          <thead>
            <tr>
              <Th>{t("common.name")}</Th>
              <Th>{t("common.role")}</Th>
              <Th className="hidden md:table-cell">{t("team.scope")}</Th>
              <Th>
                <span className="sr-only">{t("common.actions")}</span>
              </Th>
            </tr>
          </thead>
          <tbody>
            {(members.data?.items ?? []).map((m) => {
              const me = m.id === workspace?.membership_id;
              const editable = manage && !me && m.status !== "removed";
              return (
                <tr key={m.id} className="hover:bg-surface-2/60">
                  <Td>
                    <span className="flex items-center gap-3">
                      <Avatar name={m.name} />
                      <span className="flex min-w-0 flex-col">
                        <span dir="auto" className="truncate font-medium">
                          {m.name} {me && <span className="font-normal text-muted">({t("team.you")})</span>}
                        </span>
                        <span className="truncate text-xs text-muted">{m.email ?? `@${m.username}`}</span>
                        <span className="mt-1 flex flex-wrap gap-1 empty:hidden">
                          {m.staff_account && <Badge>{t("team.staffBadge")}</Badge>}
                          {m.mfa_enabled && (
                            <Badge tone="success">
                              <ShieldCheck className="size-3" aria-hidden="true" />
                              {t("team.mfaBadge")}
                            </Badge>
                          )}
                          {m.status !== "active" && <Badge tone="warn">{t(`team.status.${m.status}`)}</Badge>}
                        </span>
                      </span>
                    </span>
                  </Td>
                  <Td>
                    {editable ? (
                      <Select
                        className="h-9 w-40"
                        value={m.role_id}
                        aria-label={`${t("team.changeRole")}: ${m.name}`}
                        onChange={(e) => update.mutate({ m, body: { role_id: e.target.value } })}
                      >
                        {(roles.data ?? []).map((r) => (
                          <option key={r.id} value={r.id}>
                            {r.name}
                          </option>
                        ))}
                      </Select>
                    ) : (
                      m.role
                    )}
                  </Td>
                  <Td className="hidden md:table-cell">
                    {editable ? (
                      <Select
                        className="h-9 w-48"
                        value={m.scope_department_id ?? ""}
                        aria-label={`${t("team.scope")}: ${m.name}`}
                        onChange={(e) => update.mutate({ m, body: e.target.value ? { scope_department_id: e.target.value } : { clear_scope: true } })}
                      >
                        <option value="">{t("team.wholeWorkspace")}</option>
                        {departmentOptions(departments.data).map((o) => (
                          <option key={o.value} value={o.value}>
                            {o.label}
                          </option>
                        ))}
                      </Select>
                    ) : m.scope_department_id ? (
                      deptNames.get(m.scope_department_id)
                    ) : (
                      t("team.wholeWorkspace")
                    )}
                  </Td>
                  <Td className="w-14 text-right">
                    {editable && (
                      <MemberActions
                        member={m}
                        onRemove={() => setRemoving(m)}
                        onReset={() => void resetPassword(m)}
                        onStatus={(s) => update.mutate({ m, body: { status: s } })}
                      />
                    )}
                  </Td>
                </tr>
              );
            })}
          </tbody>
        </Table>
      </Card>
      <ConfirmDialog
        open={removing !== null}
        title={t("team.removeTitle", { name: removing?.name ?? "" })}
        confirmLabel={t("common.remove")}
        busy={remove.isPending}
        onConfirm={() => removing && remove.mutate(removing)}
        onClose={() => setRemoving(null)}
      >
        {t("team.removeConfirm", { name: removing?.name ?? "" })}
      </ConfirmDialog>
      <Dialog open={reset !== null} onOpenChange={(o) => !o && setReset(null)}>
        {reset && (
          <DialogContent title={t("team.newTemporary")} description={t("team.staffShare")} closeLabel={t("common.close")} footer={<Button variant="primary" onClick={() => setReset(null)}>{t("common.done")}</Button>}>
            <Secret label={reset.member.username ?? reset.member.name} value={reset.password} testId="reset-password" />
          </DialogContent>
        )}
      </Dialog>
    </div>
  );
}

function Invitations() {
  const { t } = useTranslation();
  const invalidate = useInvalidateTeam();
  const invites = useQuery({ queryKey: keys.invites, queryFn: () => api<Invite[]>("/v1/invites") });
  const revoke = useMutation({
    mutationFn: (id: string) => api(`/v1/invites/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (invites.data?.length === 0) {
    return (
      <Card>
        <EmptyState icon={<Mail />} title={t("team.noInvites")} />
      </Card>
    );
  }
  return (
    <ul className="flex flex-col gap-2">
      {(invites.data ?? []).map((i) => (
        <li key={i.id}>
          <Card className="flex flex-wrap items-center gap-3 px-4 py-3">
            <Mail className="size-4 text-muted" aria-hidden="true" />
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="truncate font-medium">{i.name ? `${i.name} · ${i.email}` : i.email}</span>
              <span className="text-xs text-muted">{t("team.expires", { date: formatDay(i.expires_at.slice(0, 10)) })}</span>
            </span>
            <Button size="sm" onClick={() => revoke.mutate(i.id)} aria-label={`${t("team.revoke")}: ${i.email}`}>
              {t("team.revoke")}
            </Button>
          </Card>
        </li>
      ))}
    </ul>
  );
}

function Roles() {
  const { t } = useTranslation();
  const { can } = useSession();
  const workspace = useWorkspace();
  const roles = useRoles();
  const invalidate = useInvalidateTeam();
  const catalog = useQuery({ queryKey: ["permissions"], queryFn: () => api<Permission[]>("/v1/permissions") });
  const [editing, setEditing] = useState<Role | "new" | null>(null);
  const allowed = Boolean(workspace.plan.features.custom_roles);
  const labels = new Map((catalog.data ?? []).map((p) => [p.key, p.label]));
  type Values = { name: string; description: string; permissions: string[] };
  const { register, handleSubmit, reset, setError, formState } = useForm<Values>({ defaultValues: { name: "", description: "", permissions: [] } });
  const close = () => setEditing(null);
  const save = useMutation({
    mutationFn: (v: Values) => {
      const body = { name: v.name.trim(), description: v.description.trim() || undefined, permissions: v.permissions };
      return editing === "new" ? api("/v1/roles", { body }) : api(`/v1/roles/${(editing as Role).id}`, { method: "PATCH", body });
    },
    onSuccess: async () => {
      await invalidate();
      close();
    },
    onError: (e) => {
      if (!applyFieldErrors(setError, ["name", "description", "permissions"], e)) toast.error(errorMessage(e));
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/v1/roles/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      await invalidate();
      close();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const groups = new Map<string, Permission[]>();
  for (const p of catalog.data ?? []) {
    if (p.owner_only) continue;
    groups.set(p.module, [...(groups.get(p.module) ?? []), p]);
  }
  const open = (r: Role | "new") => {
    reset(r === "new" ? { name: "", description: "", permissions: [] } : { name: r.name, description: r.description ?? "", permissions: r.permissions });
    setEditing(r);
  };

  return (
    <div className="flex flex-col gap-4">
      {can("roles.manage") &&
        (allowed ? (
          <div className="flex justify-end">
            <Button variant="primary" onClick={() => open("new")}>
              <Shield aria-hidden="true" />
              {t("team.customRole")}
            </Button>
          </div>
        ) : (
          <Alert tone="info">{t("team.customRolesPlan")}</Alert>
        ))}
      <ul className="grid gap-3 md:grid-cols-2">
        {(roles.data ?? []).map((r) => {
          const editable = !r.is_builtin && can("roles.manage");
          return (
            <li key={r.id}>
              <Card className="flex h-full flex-col gap-2 p-4">
                <div className="flex items-start justify-between gap-2">
                  <span className="font-display text-base font-semibold">{r.name}</span>
                  <span className="flex gap-1">
                    {r.is_builtin && <Badge>{t("team.builtin")}</Badge>}
                    <Badge tone="accent">{t("team.membersCount", { count: r.members, formatted: formatNumber(r.members) })}</Badge>
                  </span>
                </div>
                {r.description && <p className="text-sm text-muted">{r.description}</p>}
                <p className="text-xs leading-relaxed text-muted">
                  {r.permissions.length > 12 ? t("team.permissionCount", { formatted: formatNumber(r.permissions.length) }) : r.permissions.map((p) => labels.get(p) ?? p).join(" · ")}
                </p>
                {editable && (
                  <Button size="sm" className="mt-auto self-start" onClick={() => open(r)} aria-label={`${t("common.edit")}: ${r.name}`}>
                    {t("common.edit")}
                  </Button>
                )}
              </Card>
            </li>
          );
        })}
      </ul>
      <Dialog open={editing !== null} onOpenChange={(o) => !o && close()}>
        {editing !== null && (
          <DialogContent
            title={editing === "new" ? t("team.customRole") : t("common.edit")}
            closeLabel={t("common.close")}
            footer={
              <>
                {editing !== "new" && (
                  <Button variant="ghost" className="mr-auto text-danger" loading={remove.isPending} onClick={() => remove.mutate(editing.id)}>
                    {t("common.delete")}
                  </Button>
                )}
                <Button onClick={close}>{t("common.cancel")}</Button>
                <Button variant="primary" type="submit" form="role-form" loading={save.isPending}>
                  {t("common.save")}
                </Button>
              </>
            }
          >
            <form id="role-form" onSubmit={handleSubmit((v) => save.mutate(v))} className="flex flex-col gap-4" noValidate>
              <Field label={t("team.roleName")} error={formState.errors.name?.message}>
                <Input {...register("name", { validate: (v) => v.trim().length > 0 || t("common.required") })} />
              </Field>
              <Field label={t("team.description")} optional={t("common.optional")}>
                <Input maxLength={300} {...register("description")} />
              </Field>
              <div className="flex flex-col gap-3">
                <span className="text-sm font-medium">{t("team.permissions")}</span>
                {[...groups.entries()].map(([module, perms]) => (
                  <fieldset key={module} className="rounded-xl border border-border p-3">
                    <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-muted">{module}</legend>
                    <div className="flex flex-col gap-1.5">
                      {perms.map((p) => (
                        <label key={p.key} className="flex cursor-pointer items-center gap-2.5 rounded-md px-1 py-1 text-sm hover:bg-surface-2">
                          <input type="checkbox" value={p.key} className="size-4 accent-[var(--accent)]" {...register("permissions")} />
                          {p.label}
                        </label>
                      ))}
                    </div>
                  </fieldset>
                ))}
              </div>
            </form>
          </DialogContent>
        )}
      </Dialog>
    </div>
  );
}

export default function TeamPage() {
  const { t } = useTranslation();
  const { can, me } = useSession();
  const [active, setActive] = useTab(["members", "invites", "roles"]);
  const [dialog, setDialog] = useState<"invite" | "staff" | null>(null);
  if (!can("members.view")) return <EmptyState icon={<Users />} title={t("common.notAllowed")} />;
  const canInvite = can("members.invite");
  const unverified = Boolean(me?.email && !me.email_verified);
  return (
    <>
      <PageHeader
        title={t("team.title")}
        sub={t("team.sub")}
        actions={
          canInvite && (
            <>
              <Button onClick={() => setDialog("staff")}>
                <UserPlus aria-hidden="true" />
                {t("team.addStaff")}
              </Button>
              <Button variant="primary" onClick={() => setDialog("invite")} disabled={unverified}>
                <Mail aria-hidden="true" />
                {t("team.invite")}
              </Button>
            </>
          )
        }
      />
      {canInvite && unverified && (
        <Alert tone="warn" className="mb-5">
          {t("team.verifyFirst")}
        </Alert>
      )}
      <Tabs value={active} onValueChange={setActive}>
        <TabsList className="mb-5 w-fit">
          <TabsTrigger value="members">{t("team.tabs.members")}</TabsTrigger>
          <TabsTrigger value="invites">{t("team.tabs.invites")}</TabsTrigger>
          <TabsTrigger value="roles">{t("team.tabs.roles")}</TabsTrigger>
        </TabsList>
        <TabsContent value="members">{active === "members" && <Members />}</TabsContent>
        <TabsContent value="invites">{active === "invites" && <Invitations />}</TabsContent>
        <TabsContent value="roles">{active === "roles" && <Roles />}</TabsContent>
      </Tabs>
      {dialog === "invite" && <InviteDialog onClose={() => setDialog(null)} />}
      {dialog === "staff" && <StaffDialog onClose={() => setDialog(null)} />}
    </>
  );
}
