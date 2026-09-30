"use client";

import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, FolderTree, KeyRound, Plus, Search, UsersRound } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import { departmentOptions, useBranches, useDepartments } from "@/api/hooks";
import type { Department, Employee, Page } from "@/api/types";
import { useSession } from "@/auth/session";
import { PageHeader } from "@/components/page";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, EmptyState } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm";
import { Dialog, DialogContent, SheetContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Table, Td, Th } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { applyFieldErrors, errorMessage } from "@/lib/errors";
import { formatDay, formatNumber, normalizeDigits } from "@/lib/format";
import { useTab } from "@/lib/use-tab";

const TYPES = ["full_time", "part_time", "contract", "intern", "daily"];
const STATUSES = ["active", "inactive", "left"];
const FIELDS = [
  "full_name",
  "preferred_name",
  "employee_code",
  "phone",
  "email",
  "department_id",
  "branch_id",
  "job_title",
  "employment_type",
  "joined_on",
  "date_of_birth",
  "status",
  "left_on",
  "national_id",
  "notes",
] as const;
type PersonValues = Record<(typeof FIELDS)[number], string>;

function PersonSheet({ person, onClose }: { person: Employee | "new"; onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const departments = useDepartments();
  const branches = useBranches();
  const isNew = person === "new";
  const initial = useMemo(() => {
    const values = Object.fromEntries(FIELDS.map((f) => [f, ""])) as PersonValues;
    if (isNew) return { ...values, employment_type: "full_time", status: "active" };
    for (const f of FIELDS) {
      const v = (person as unknown as Record<string, unknown>)[f];
      if (typeof v === "string") values[f] = v;
    }
    values.national_id = "";
    return values;
  }, [person, isNew]);
  const { register, handleSubmit, setError, formState } = useForm<PersonValues>({ defaultValues: initial });

  const save = useMutation({
    mutationFn: (values: PersonValues) => {
      const body: Record<string, unknown> = {};
      const clear: string[] = [];
      for (const key of FIELDS) {
        let value: string | null = values[key].trim();
        if (key === "phone" && value) value = normalizeDigits(value);
        if (value === "") value = null;
        if (isNew) {
          if (value !== null) body[key] = value;
        } else if (value === null) {
          const before = (person as unknown as Record<string, unknown>)[key];
          if (before !== null && before !== undefined && key !== "national_id") clear.push(key);
        } else if (value !== (person as unknown as Record<string, unknown>)[key]) body[key] = value;
      }
      if (!isNew && clear.length) body.clear = clear;
      return isNew ? api<Employee>("/v1/people", { body }) : api<Employee>(`/v1/people/${person.id}`, { method: "PATCH", body, version: person.version });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["people"] });
      await queryClient.invalidateQueries({ queryKey: ["departments"] });
      toast.success(t("common.saved"));
      onClose();
    },
    onError: (e) => {
      if (!applyFieldErrors(setError, FIELDS, e)) toast.error(errorMessage(e));
    },
  });
  const errors = formState.errors;

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <SheetContent
        title={isNew ? t("people.add") : t("people.editTitle", { name: person.full_name })}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" type="submit" form="person-form" loading={save.isPending}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <form id="person-form" onSubmit={handleSubmit((v) => save.mutate(v))} className="flex flex-col gap-4" noValidate>
          <Field label={t("people.fullName")} error={errors.full_name?.message}>
            <Input autoComplete="off" dir="auto" maxLength={200} {...register("full_name", { validate: (v) => v.trim().length > 0 || t("common.required") })} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("people.preferredName")} optional={t("common.optional")}>
              <Input dir="auto" maxLength={100} {...register("preferred_name")} />
            </Field>
            <Field label={t("people.code")} optional={t("common.optional")} error={errors.employee_code?.message}>
              <Input maxLength={40} {...register("employee_code")} />
            </Field>
            <Field label={t("people.phone")} optional={t("common.optional")} error={errors.phone?.message}>
              <Input inputMode="tel" maxLength={40} {...register("phone")} />
            </Field>
            <Field label={t("common.email")} optional={t("common.optional")} error={errors.email?.message}>
              <Input type="email" inputMode="email" {...register("email")} />
            </Field>
            <Field label={t("people.department")} optional={t("common.optional")}>
              <Select {...register("department_id")}>
                <option value="">–</option>
                {departmentOptions(departments.data).map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("people.branch")} optional={t("common.optional")}>
              <Select {...register("branch_id")}>
                <option value="">–</option>
                {(branches.data ?? [])
                  .filter((b) => b.is_active)
                  .map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
              </Select>
            </Field>
            <Field label={t("people.jobTitle")} optional={t("common.optional")}>
              <Input maxLength={120} {...register("job_title")} />
            </Field>
            <Field label={t("people.employmentType")}>
              <Select {...register("employment_type")}>
                {TYPES.map((v) => (
                  <option key={v} value={v}>
                    {t(`people.types.${v}`)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("people.joinedOn")} optional={t("common.optional")} error={errors.joined_on?.message}>
              <Input type="date" {...register("joined_on")} />
            </Field>
            <Field label={t("people.dateOfBirth")} optional={t("common.optional")} error={errors.date_of_birth?.message}>
              <Input type="date" max={new Date().toISOString().slice(0, 10)} {...register("date_of_birth")} />
            </Field>
            {!isNew && (
              <>
                <Field label={t("common.status")}>
                  <Select {...register("status")}>
                    {STATUSES.map((v) => (
                      <option key={v} value={v}>
                        {t(`people.status.${v}`)}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label={t("people.leftOn")} optional={t("common.optional")} error={errors.left_on?.message}>
                  <Input type="date" {...register("left_on")} />
                </Field>
              </>
            )}
          </div>
          <Field
            label={t("people.nationalId")}
            optional={t("common.optional")}
            help={!isNew && person.national_id_last4 ? t("people.nationalIdSaved", { last4: person.national_id_last4 }) : t("people.nationalIdHelp")}
            error={errors.national_id?.message}
          >
            <Input autoComplete="off" maxLength={40} {...register("national_id")} />
          </Field>
          <Field label={t("people.notes")} optional={t("common.optional")}>
            <Textarea rows={3} maxLength={5000} dir="auto" {...register("notes")} />
          </Field>
        </form>
      </SheetContent>
    </Dialog>
  );
}

const statusTone = { active: "success", inactive: "neutral", left: "warn" } as const;

function PeopleList() {
  const { t } = useTranslation();
  const { can } = useSession();
  const [q, setQ] = useState("");
  const query = useDeferredValue(q.trim());
  const [department, setDepartment] = useState("");
  const [status, setStatus] = useState("active");
  const [editing, setEditing] = useState<Employee | "new" | null>(null);
  const departments = useDepartments();
  const names = new Map((departments.data ?? []).map((d) => [d.id, d.name]));
  const manage = can("people.manage");
  const people = useInfiniteQuery({
    queryKey: ["people", { q: query, department, status }],
    queryFn: ({ pageParam }) =>
      api<Page<Employee>>("/v1/people", { query: { q: query, department_id: department || undefined, status, cursor: pageParam, limit: 50 } }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
  const rows = people.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <Field label={t("common.search")} hideLabel className="w-full sm:w-80">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden="true" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("people.searchPlaceholder")} className="pl-9" type="search" aria-label={t("common.search")} />
          </div>
        </Field>
        <Field label={t("people.department")} hideLabel className="w-full sm:w-52">
          <Select value={department} onChange={(e) => setDepartment(e.target.value)} aria-label={t("people.department")}>
            <option value="">{t("people.allDepartments")}</option>
            {departmentOptions(departments.data).map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("common.status")} hideLabel className="w-full sm:w-40">
          <Select value={status} onChange={(e) => setStatus(e.target.value)} aria-label={t("common.status")}>
            {[...STATUSES, "all"].map((s) => (
              <option key={s} value={s}>
                {s === "all" ? t("common.all") : t(`people.status.${s}`)}
              </option>
            ))}
          </Select>
        </Field>
        {manage && (
          <Button variant="primary" className="sm:ml-auto" onClick={() => setEditing("new")}>
            <Plus aria-hidden="true" />
            {t("people.add")}
          </Button>
        )}
      </div>

      {people.data && rows.length === 0 ? (
        <Card>
          <EmptyState icon={<UsersRound />} title={query ? t("people.noMatch") : t("people.empty")} />
        </Card>
      ) : (
        <Card className="overflow-hidden">
          <Table label={t("people.title")}>
            <thead>
              <tr>
                <Th>{t("common.name")}</Th>
                <Th className="hidden md:table-cell">{t("people.department")}</Th>
                <Th className="hidden lg:table-cell">{t("people.phone")}</Th>
                <Th className="hidden lg:table-cell">{t("people.joinedOn")}</Th>
                <Th>{t("common.status")}</Th>
                {manage && (
                  <Th>
                    <span className="sr-only">{t("common.actions")}</span>
                  </Th>
                )}
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.id} className="hover:bg-surface-2/60">
                  <Td>
                    <span className="flex items-center gap-3">
                      <Avatar name={p.full_name} />
                      <span className="flex min-w-0 flex-col">
                        <span dir="auto" className="truncate font-medium">
                          {p.full_name}
                        </span>
                        <span className="truncate text-xs text-muted">{[p.job_title, p.employee_code].filter(Boolean).join(" · ")}</span>
                      </span>
                    </span>
                  </Td>
                  <Td className="hidden md:table-cell">{p.department_id ? names.get(p.department_id) : "–"}</Td>
                  <Td className="hidden tabular-nums lg:table-cell">{p.phone ?? "–"}</Td>
                  <Td className="hidden lg:table-cell">{formatDay(p.joined_on) || "–"}</Td>
                  <Td>
                    <span className="flex flex-wrap gap-1">
                      <Badge tone={statusTone[p.status as keyof typeof statusTone] ?? "neutral"}>{t(`people.status.${p.status}`)}</Badge>
                      {p.membership_id && (
                        <Badge tone="accent">
                          <KeyRound className="size-3" aria-hidden="true" />
                          {t("people.hasLogin")}
                        </Badge>
                      )}
                    </span>
                  </Td>
                  {manage && (
                    <Td className="text-right">
                      <Button size="sm" variant="ghost" onClick={() => setEditing(p)} aria-label={t("people.editTitle", { name: p.full_name })}>
                        {t("common.edit")}
                        <ChevronRight aria-hidden="true" />
                      </Button>
                    </Td>
                  )}
                </tr>
              ))}
            </tbody>
          </Table>
          {people.hasNextPage && (
            <div className="border-t border-border p-3 text-center">
              <Button onClick={() => void people.fetchNextPage()} loading={people.isFetchingNextPage}>
                {t("common.loadMore")}
              </Button>
            </div>
          )}
        </Card>
      )}
      {editing && <PersonSheet person={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

interface DepartmentNode {
  department: Department;
  children: DepartmentNode[];
}

function DepartmentTree({ nodes, depth, onOpen }: { nodes: DepartmentNode[]; depth: number; onOpen?: (d: Department) => void }) {
  const { t } = useTranslation();
  return (
    <ul className={depth ? "ml-5 border-l border-border pl-3" : ""}>
      {nodes.map(({ department: d, children }) => (
        <li key={d.id}>
          <div className="flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-surface-2">
            <FolderTree className="size-4 shrink-0 text-muted" aria-hidden="true" />
            <span className="min-w-0 flex-1 truncate font-medium">{d.name}</span>
            <span className="shrink-0 text-xs text-muted">{t("people.peopleCount", { count: d.people, formatted: formatNumber(d.people) })}</span>
            {onOpen && (
              <Button size="sm" variant="ghost" onClick={() => onOpen(d)} aria-label={`${t("common.edit")}: ${d.name}`}>
                {t("common.edit")}
              </Button>
            )}
          </div>
          {children.length > 0 && <DepartmentTree nodes={children} depth={depth + 1} onOpen={onOpen} />}
        </li>
      ))}
    </ul>
  );
}

function DepartmentsTab() {
  const { t } = useTranslation();
  const { can } = useSession();
  const queryClient = useQueryClient();
  const departments = useDepartments();
  const [editing, setEditing] = useState<Department | "new" | null>(null);
  const [confirming, setConfirming] = useState(false);
  const manage = can("departments.manage");
  const { register, handleSubmit, reset, setError, formState } = useForm<{ name: string; parent_id: string }>({ defaultValues: { name: "", parent_id: "" } });

  const tree = useMemo(() => {
    const list = departments.data ?? [];
    const nodes = new Map<string, DepartmentNode>(list.map((d) => [d.id, { department: d, children: [] }]));
    const roots: DepartmentNode[] = [];
    for (const d of [...list].sort((a, b) => a.name.localeCompare(b.name))) {
      const node = nodes.get(d.id)!;
      const parent = d.parent_id ? nodes.get(d.parent_id) : undefined;
      if (parent) parent.children.push(node);
      else roots.push(node);
    }
    return roots;
  }, [departments.data]);

  const close = () => {
    setEditing(null);
    setConfirming(false);
  };
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["departments"] });
  const save = useMutation({
    mutationFn: (v: { name: string; parent_id: string }) => {
      if (editing === "new") return api("/v1/departments", { body: { name: v.name.trim(), parent_id: v.parent_id || undefined } });
      const d = editing as Department;
      return api(`/v1/departments/${d.id}`, {
        method: "PATCH",
        version: d.version,
        body: { name: v.name.trim(), ...(v.parent_id ? { parent_id: v.parent_id } : d.parent_id ? { move_to_top: true } : {}) },
      });
    },
    onSuccess: async () => {
      await invalidate();
      close();
    },
    onError: (e) => {
      if (!applyFieldErrors(setError, ["name", "parent_id"], e)) toast.error(errorMessage(e));
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/v1/departments/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      await invalidate();
      close();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const open = (d: Department | "new") => {
    reset(d === "new" ? { name: "", parent_id: "" } : { name: d.name, parent_id: d.parent_id ?? "" });
    setEditing(d);
  };

  return (
    <div className="flex flex-col gap-4">
      {manage && (
        <div className="flex justify-end">
          <Button variant="primary" onClick={() => open("new")}>
            <Plus aria-hidden="true" />
            {t("people.addDepartment")}
          </Button>
        </div>
      )}
      <Card className="p-3">
        {departments.data?.length === 0 ? <EmptyState icon={<FolderTree />} title={t("people.noDepartments")} /> : <DepartmentTree nodes={tree} depth={0} onOpen={manage ? open : undefined} />}
      </Card>
      <Dialog open={editing !== null} onOpenChange={(o) => !o && close()}>
        {editing !== null && (
          <DialogContent
            title={editing === "new" ? t("people.addDepartment") : t("common.edit")}
            closeLabel={t("common.close")}
            footer={
              <>
                {editing !== "new" && (
                  <Button variant="ghost" className="mr-auto text-danger" onClick={() => setConfirming(true)}>
                    {t("common.delete")}
                  </Button>
                )}
                <Button onClick={close}>{t("common.cancel")}</Button>
                <Button variant="primary" type="submit" form="department-form" loading={save.isPending}>
                  {t("common.save")}
                </Button>
              </>
            }
          >
            <form id="department-form" onSubmit={handleSubmit((v) => save.mutate(v))} className="flex flex-col gap-4" noValidate>
              <Field label={t("people.departmentName")} error={formState.errors.name?.message}>
                <Input maxLength={120} {...register("name", { validate: (v) => v.trim().length > 0 || t("common.required") })} />
              </Field>
              <Field label={t("people.parent")} error={formState.errors.parent_id?.message}>
                <Select {...register("parent_id")}>
                  <option value="">{t("people.topLevel")}</option>
                  {departmentOptions(departments.data)
                    .filter((o) => editing === "new" || o.value !== editing.id)
                    .map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                </Select>
              </Field>
            </form>
          </DialogContent>
        )}
      </Dialog>
      <ConfirmDialog
        open={confirming}
        title={t("people.deleteDepartment", { name: editing && editing !== "new" ? editing.name : "" })}
        confirmLabel={t("common.delete")}
        busy={remove.isPending}
        onConfirm={() => editing && editing !== "new" && remove.mutate(editing.id)}
        onClose={() => setConfirming(false)}
      />
    </div>
  );
}

export default function PeoplePage() {
  const { t } = useTranslation();
  const { can } = useSession();
  const [active, setActive] = useTab(["people", "departments"]);
  if (!can("people.view")) return <EmptyState icon={<UsersRound />} title={t("common.notAllowed")} />;
  return (
    <>
      <PageHeader title={t("people.title")} sub={t("people.sub")} />
      <Tabs value={active} onValueChange={setActive}>
        <TabsList className="mb-5 w-fit">
          <TabsTrigger value="people">{t("people.tabs.people")}</TabsTrigger>
          <TabsTrigger value="departments">{t("people.tabs.departments")}</TabsTrigger>
        </TabsList>
        <TabsContent value="people">{active === "people" && <PeopleList />}</TabsContent>
        <TabsContent value="departments">{active === "departments" && <DepartmentsTab />}</TabsContent>
      </Tabs>
    </>
  );
}
