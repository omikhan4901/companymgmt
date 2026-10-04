"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, MapPin, Plus, Settings as SettingsIcon, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import { useAttendanceSettings, useBranches } from "@/api/hooks";
import { AddressCard } from "@/components/address-card";
import { AIAllowances, AISettings, useIsOperator } from "@/components/ai/settings";
import type { AuditEvent, Branch, Page, Workspace } from "@/api/types";
import { useSession, useWorkspace } from "@/auth/session";
import { BranchSheet } from "@/components/branch-sheet";
import { PageHeader } from "@/components/page";
import { PlanCards } from "@/components/plan-cards";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, EmptyState } from "@/components/ui/card";
import { Choice, ChoiceGroup, Switch } from "@/components/ui/choice";
import { Field } from "@/components/ui/field";
import { Input, Select } from "@/components/ui/input";
import { Table, Td, Th } from "@/components/ui/table";
import { WorkspaceData } from "@/components/privacy";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { intlLocale } from "@/i18n";
import { applyFieldErrors, errorMessage } from "@/lib/errors";
import { formatDateTime, formatDay, formatNumber } from "@/lib/format";
import { formatDistance } from "@/lib/geolocation";
import { countryOptions, CURRENCIES, timezoneOptions } from "@/lib/places";
import { useTab } from "@/lib/use-tab";

type WorkspaceValues = Pick<Workspace, "name" | "country" | "currency" | "timezone" | "locale" | "ui_mode"> & { week_start: string; fiscal_year_start_month: string };

function WorkspaceForm() {
  const { t } = useTranslation();
  const { reload } = useSession();
  const current = useQuery({ queryKey: ["workspace"], queryFn: () => api<Workspace>("/v1/workspace") });
  const { register, handleSubmit, reset, setError, formState } = useForm<WorkspaceValues>();
  useEffect(() => {
    if (current.data) reset({ ...current.data, week_start: String(current.data.week_start), fiscal_year_start_month: String(current.data.fiscal_year_start_month) });
  }, [current.data, reset]);
  const save = useMutation({
    mutationFn: (v: WorkspaceValues) =>
      api<Workspace>("/v1/workspace", {
        method: "PATCH",
        body: { ...v, name: v.name.trim(), country: v.country || undefined, week_start: Number(v.week_start), fiscal_year_start_month: Number(v.fiscal_year_start_month) },
      }),
    onSuccess: async () => {
      toast.success(t("common.saved"));
      await reload();
    },
    onError: (e) => {
      if (!applyFieldErrors(setError, ["name", "country", "currency", "timezone", "locale", "ui_mode", "week_start", "fiscal_year_start_month"], e)) toast.error(errorMessage(e));
    },
  });
  if (!current.data) return null;
  const months = Array.from({ length: 12 }, (_, i) => ({
    value: String(i + 1),
    label: new Intl.DateTimeFormat(intlLocale(), { month: "long", timeZone: "UTC" }).format(new Date(Date.UTC(2026, i, 1))),
  }));
  // ISO weekdays: 1 = Monday … 7 = Sunday (2 Feb 2026 is a Monday).
  const days = Array.from({ length: 7 }, (_, i) => ({
    value: String(i + 1),
    label: new Intl.DateTimeFormat(intlLocale(), { weekday: "long", timeZone: "UTC" }).format(new Date(Date.UTC(2026, 1, 2 + i))),
  }));
  return (
    <Card className="max-w-2xl p-5">
      <form onSubmit={handleSubmit((v) => save.mutate(v))} className="flex flex-col gap-4" noValidate>
        <Field label={t("settings.workspaceName")} error={formState.errors.name?.message}>
          <Input {...register("name", { validate: (v) => v.trim().length > 0 || t("common.required") })} />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t("signup.country")}>
            <Select {...register("country")}>
              <option value="">–</option>
              {countryOptions().map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("settings.currency")}>
            <Select {...register("currency")}>
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("settings.timezone")}>
            <Select {...register("timezone")}>
              {timezoneOptions().map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("settings.language")}>
            <Select {...register("locale")}>
              <option value="en">English</option>
              <option value="bn">বাংলা</option>
            </Select>
          </Field>
          <Field label={t("settings.weekStart")}>
            <Select {...register("week_start")}>
              {days.map((d) => (
                <option key={d.value} value={d.value}>
                  {d.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("settings.fiscalYear")}>
            <Select {...register("fiscal_year_start_month")}>
              {months.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <Field label={t("settings.uiMode")} help={t("settings.uiModeHelp")}>
          <Select {...register("ui_mode")}>
            {["simple", "standard", "advanced"].map((m) => (
              <option key={m} value={m}>
                {t(`settings.uiModes.${m}`)}
              </option>
            ))}
          </Select>
        </Field>
        <Button type="submit" variant="primary" loading={save.isPending} className="self-start">
          {t("common.save")}
        </Button>
      </form>
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
  const { reload } = useSession();
  const workspace = useWorkspace();
  const modules = useQuery({ queryKey: ["modules"], queryFn: () => api<ModuleInfo[]>("/v1/modules"), staleTime: 3_600_000 });
  const enabled = new Set([...workspace.plan.modules, ...workspace.plan.locked_modules]);
  const save = useMutation({
    mutationFn: (list: string[]) => api<string[]>("/v1/workspace/modules", { method: "PUT", body: { modules: list } }),
    onSuccess: reload,
    onError: (e) => toast.error(errorMessage(e)),
  });
  const names = new Map((modules.data ?? []).map((m) => [m.key, m.name]));
  const toggle = (key: string, on: boolean) => {
    const optional = [...enabled].filter((k) => !(modules.data ?? []).find((m) => m.key === k)?.core);
    save.mutate(on ? [...optional, key] : optional.filter((k) => k !== key));
  };
  return (
    <div className="flex max-w-2xl flex-col gap-3">
      <p className="text-sm text-muted">{t("settings.modulesSub")}</p>
      {workspace.plan.max_modules !== null && <p className="text-sm text-muted">{t("settings.modulesLimit", { limit: formatNumber(workspace.plan.max_modules) })}</p>}
      <ul className="flex flex-col gap-2">
        {(modules.data ?? []).map((m) => (
          <li key={m.key}>
            <Card className="flex items-center gap-3 px-4 py-3">
              <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{m.name}</span>
                  {m.core && <Badge tone="accent">{t("settings.core")}</Badge>}
                  {!m.available && <Badge>{t("common.comingSoon")}</Badge>}
                  {workspace.plan.locked_modules.includes(m.key) && <Badge tone="warn">{t("settings.locked")}</Badge>}
                </span>
                {m.requires.length > 0 && <span className="text-xs text-muted">{t("settings.needs", { names: m.requires.map((r) => names.get(r) ?? r).join(", ") })}</span>}
              </span>
              <Switch checked={m.core || enabled.has(m.key)} disabled={m.core || !m.available || save.isPending} onCheckedChange={(on) => toggle(m.key, on)} aria-label={m.name} />
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}

function LocationCheck() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const settings = useAttendanceSettings();
  const save = useMutation({
    mutationFn: (body: { location_mode: string; max_accuracy_m: number }) => api("/v1/attendance/settings", { method: "PUT", body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["attendance"] }),
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (!settings.data) return null;
  const s = settings.data;
  const unplaced = s.branches_total - s.branches_located;
  return (
    <Card>
      <CardHeader title={t("location.settingsTitle")} sub={t("location.settingsSub")} />
      <div className="flex flex-col gap-4 p-5 pt-4">
        <ChoiceGroup
          value={s.location_mode}
          onValueChange={(mode) => save.mutate({ location_mode: mode, max_accuracy_m: s.max_accuracy_m })}
          className="md:grid-cols-3"
          aria-label={t("location.settingsTitle")}
          disabled={save.isPending}
        >
          {(["off", "record", "require"] as const).map((m) => (
            <Choice key={m} value={m} label={t(`location.modes.${m}`)} hint={t(`location.modeHelp.${m}`)} />
          ))}
        </ChoiceGroup>
        {s.location_mode !== "off" && (
          <Field label={t("location.maxAccuracy")} help={t("branch.accuracyHelp")} className="max-w-xs">
            <Select value={String(s.max_accuracy_m)} onChange={(e) => save.mutate({ location_mode: s.location_mode, max_accuracy_m: Number(e.target.value) })}>
              {[25, 50, 100, 200, 500].map((m) => (
                <option key={m} value={m}>
                  {formatDistance(m, intlLocale())}
                </option>
              ))}
            </Select>
          </Field>
        )}
        {s.location_mode !== "off" && unplaced > 0 && <Alert tone="warn">{t("location.unplaced", { count: formatNumber(unplaced), total: formatNumber(s.branches_total) })}</Alert>}
      </div>
    </Card>
  );
}

function Lateness() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const settings = useAttendanceSettings();
  const save = useMutation({
    mutationFn: (body: { day_starts_at?: string; late_after_minutes?: number }) =>
      api("/v1/attendance/settings", { method: "PUT", body: { location_mode: settings.data?.location_mode, max_accuracy_m: settings.data?.max_accuracy_m, ...body } }),
    onSuccess: () => {
      toast.success(t("common.saved"));
      void queryClient.invalidateQueries({ queryKey: ["attendance"] });
      void queryClient.invalidateQueries({ queryKey: ["reports"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const [starts, setStarts] = useState("");
  const current = settings.data?.day_starts_at.slice(0, 5) ?? "";
  useEffect(() => setStarts(current), [current]);
  if (!settings.data) return null;
  return (
    <Card>
      <CardHeader title={t("lateness.title")} sub={t("lateness.sub")} />
      <div className="grid gap-4 p-5 pt-4 sm:grid-cols-2">
        <Field label={t("lateness.startsAt")}>
          <Input type="time" value={starts} onChange={(e) => setStarts(e.target.value)} onBlur={() => starts && starts !== current && save.mutate({ day_starts_at: starts })} />
        </Field>
        <Field label={t("lateness.grace")} help={t("lateness.graceHelp")}>
          <Select value={String(settings.data.late_after_minutes)} onChange={(e) => save.mutate({ late_after_minutes: Number(e.target.value) })}>
            {[0, 5, 10, 15, 20, 30, 45, 60].map((m) => (
              <option key={m} value={m}>
                {t("lateness.minutes", { count: m, formatted: formatNumber(m) })}
              </option>
            ))}
          </Select>
        </Field>
      </div>
    </Card>
  );
}

function Branches() {
  const { t } = useTranslation();
  const { can, hasModule } = useSession();
  const branches = useBranches();
  const [editing, setEditing] = useState<Branch | "new" | null>(null);
  return (
    <div className="flex max-w-3xl flex-col gap-5">
      {can("workspace.manage") && <LocationCheck />}
      {can("workspace.manage") && hasModule("attendance") && <Lateness />}
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">{t("settings.tabs.branches")}</h2>
        <Button variant="primary" onClick={() => setEditing("new")}>
          <Plus aria-hidden="true" />
          {t("settings.addBranch")}
        </Button>
      </div>
      <ul className="flex flex-col gap-2">
        {(branches.data ?? []).map((b) => (
          <li key={b.id}>
            <Card className="flex flex-wrap items-center gap-3 px-4 py-3">
              <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent-soft-text">
                <Building2 className="size-5" aria-hidden="true" />
              </span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="font-medium">{b.name}</span>
                <span className="truncate text-xs text-muted">{[b.timezone.replace(/_/g, " "), b.address].filter(Boolean).join(" · ")}</span>
              </span>
              <span className="flex flex-wrap gap-1">
                {b.latitude !== null ? (
                  <Badge tone="success">
                    <MapPin className="size-3" aria-hidden="true" />
                    {t("location.placed")} · {formatDistance(b.geofence_m, intlLocale())}
                  </Badge>
                ) : (
                  <Badge tone="warn">
                    <MapPin className="size-3" aria-hidden="true" />
                    {t("location.notPlaced")}
                  </Badge>
                )}
                <Badge tone={b.is_active ? "neutral" : "warn"}>{b.is_active ? t("settings.open") : t("settings.closed")}</Badge>
              </span>
              <Button size="sm" onClick={() => setEditing(b)} aria-label={`${t("common.edit")}: ${b.name}`}>
                {t("common.edit")}
              </Button>
            </Card>
          </li>
        ))}
      </ul>
      {editing && <BranchSheet branch={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function PlanTab() {
  const { t } = useTranslation();
  const workspace = useWorkspace();
  const plan = workspace.plan;
  return (
    <div className="flex flex-col gap-4">
      <Alert tone="info" title={`${t("settings.currentPlan")}: ${plan.name}`}>
        {plan.status === "trialing" && plan.trial_ends_at ? `${t("settings.trialUntil", { date: formatDay(plan.trial_ends_at.slice(0, 10)) })}. ` : ""}
        {t("settings.paymentsSoon")}
      </Alert>
      <PlanCards current={plan.key} />
    </div>
  );
}

function Audit() {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const [action, setAction] = useState("");
  const events = useInfiniteQuery({
    queryKey: ["audit", { action }],
    queryFn: ({ pageParam }) => api<Page<AuditEvent>>("/v1/audit", { query: { action: action || undefined, cursor: pageParam, limit: 50 } }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
  const verify = async () => {
    try {
      const r = await api<{ ok: boolean; first_bad_seq: number | null }>("/v1/audit/verify");
      if (r.ok) toast.success(t("settings.chainOk"));
      else toast.error(t("settings.chainBroken", { seq: r.first_bad_seq }));
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };
  const rows = events.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted">{t("settings.auditSub")}</p>
      <div className="flex flex-wrap items-end gap-3">
        <Field label={t("settings.filterAction")} className="w-56">
          <Select value={action} onChange={(e) => setAction(e.target.value)}>
            <option value="">{t("common.all")}</option>
            {["workspace.", "member.", "invite.", "role.", "branch.", "department.", "person.", "attendance."].map((a) => (
              <option key={a} value={a}>
                {a.replace(".", "")}
              </option>
            ))}
          </Select>
        </Field>
        <Button className="ml-auto" onClick={() => void verify()}>
          <ShieldCheck aria-hidden="true" />
          {t("settings.verifyChain")}
        </Button>
      </div>
      <Card className="overflow-hidden">
        <Table label={t("settings.tabs.audit")}>
          <thead>
            <tr>
              <Th>#</Th>
              <Th>{t("common.date")}</Th>
              <Th>{t("common.name")}</Th>
              <Th>{t("settings.action")}</Th>
              <Th className="hidden lg:table-cell">{t("settings.details")}</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <tr key={e.id}>
                <Td className="text-muted tabular-nums">{formatNumber(e.seq)}</Td>
                <Td className="whitespace-nowrap tabular-nums">{formatDateTime(e.occurred_at, timezone)}</Td>
                <Td className="max-w-44 truncate">{e.actor_name ?? "–"}</Td>
                <Td>
                  <code className="rounded bg-surface-2 px-1.5 py-0.5 text-xs">{e.action}</code>
                </Td>
                <Td className="hidden max-w-md lg:table-cell">
                  <span className="line-clamp-2 break-all text-xs text-muted">{JSON.stringify(e.data)}</span>
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
        {events.hasNextPage && (
          <div className="border-t border-border p-3 text-center">
            <Button onClick={() => void events.fetchNextPage()} loading={events.isFetchingNextPage}>
              {t("common.loadMore")}
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}

export default function SettingsPage() {
  const { t } = useTranslation();
  const { can } = useSession();
  const operator = useIsOperator();
  const tabs = [
    {
      key: "workspace",
      label: t("settings.tabs.workspace"),
      content: (
        <>
          <WorkspaceForm />
          <AddressCard />
        </>
      ),
      show: can("workspace.manage"),
    },
    { key: "modules", label: t("settings.tabs.modules"), content: <Modules />, show: can("workspace.manage") },
    { key: "branches", label: t("settings.tabs.branches"), content: <Branches />, show: can("branches.manage") },
    { key: "plan", label: t("settings.tabs.plan"), content: <PlanTab />, show: can("workspace.manage") },
    { key: "ai", label: t("settings.tabs.ai"), content: <AISettings />, show: can("ai.manage") },
    { key: "audit", label: t("settings.tabs.audit"), content: <Audit />, show: can("audit.view") },
    {
      key: "data",
      label: t("privacy.tab"),
      content: <WorkspaceData />,
      show: can("workspace.manage") || can("workspace.export") || can("workspace.delete"),
    },
    { key: "operator", label: t("settings.tabs.operator"), content: <AIAllowances />, show: operator.data?.operator === true },
  ].filter((x) => x.show);
  const [active, setActive] = useTab(tabs.map((x) => x.key));
  if (!tabs.length) return <EmptyState icon={<SettingsIcon />} title={t("common.notAllowed")} />;
  return (
    <>
      <PageHeader title={t("settings.title")} />
      <Tabs value={active} onValueChange={setActive}>
        <TabsList className="mb-5 w-fit max-w-full overflow-x-auto">
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
