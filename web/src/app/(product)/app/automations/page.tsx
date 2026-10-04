"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { History, Pencil, Play, Plus, Sparkles, Trash2, Workflow, X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import { departmentOptions, useDepartments, useRoles } from "@/api/hooks";
import type { Automation, AutomationDraft, AutomationRun, Member, Page } from "@/api/types";
import { useSession, useWorkspace } from "@/auth/session";
import { useAIStatus } from "@/components/ai/ai";
import { PageHeader } from "@/components/page";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, EmptyState } from "@/components/ui/card";
import { Switch } from "@/components/ui/choice";
import { ConfirmDialog } from "@/components/ui/confirm";
import { Dialog, SheetContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { errorMessage } from "@/lib/errors";
import { formatDateTime, formatNumber } from "@/lib/format";

const EVENTS = [
  "member.joined",
  "leave.requested",
  "leave.approved",
  "leave.rejected",
  "leave.cancelled",
  "task.assigned",
  "task.completed",
  "task.commented",
  "attendance.correction_requested",
  "document.published",
  "document.acknowledged",
  "announcement.published",
  "payroll.finalized",
] as const;
const ABOUT_SOMEONE = new Set(EVENTS.filter((e) => !["document.published", "announcement.published", "payroll.finalized"].includes(e)));
const KINDS = ["everyone", "role", "department", "people", "subject", "overdue_tasks", "not_clocked_in"] as const;
const OPS = ["eq", "ne", "gte", "lte", "contains"] as const;

interface Who {
  kind: (typeof KINDS)[number];
  role?: string | null;
  department_id?: string | null;
  membership_ids?: string[];
}
interface Step {
  type: "notify" | "create_task";
  to?: Who;
  message?: string;
  title?: string;
  description?: string | null;
  assign_to?: Who | null;
  due_in_days?: number | null;
}
interface Draft {
  name: string;
  enabled: boolean;
  drafted_by_ai?: boolean;
  trigger: { type: "schedule"; every: "day" | "workdays" | "week" | "month"; time: string; weekday: number; day: number } | { type: "event"; event: string };
  conditions: { field: string; op: (typeof OPS)[number]; value: string | number | boolean }[];
  actions: Step[];
}

const blank = (): Draft => ({
  name: "",
  enabled: true,
  trigger: { type: "schedule", every: "week", time: "09:00", weekday: 1, day: 1 },
  conditions: [],
  actions: [{ type: "notify", to: { kind: "everyone" }, message: "" }],
});

function useTemplates(): { key: string; draft: Draft }[] {
  const { t } = useTranslation();
  return [
    {
      key: "overdue",
      draft: {
        ...blank(),
        name: t("automations.templates.overdue"),
        actions: [{ type: "notify", to: { kind: "overdue_tasks" }, message: t("automations.templates.overdueMessage") }],
      },
    },
    {
      key: "clockIn",
      draft: {
        ...blank(),
        name: t("automations.templates.clockIn"),
        trigger: { type: "schedule", every: "workdays", time: "10:00", weekday: 1, day: 1 },
        actions: [{ type: "notify", to: { kind: "not_clocked_in" }, message: t("automations.templates.clockInMessage") }],
      },
    },
    {
      key: "welcome",
      draft: {
        ...blank(),
        name: t("automations.templates.welcome"),
        trigger: { type: "event", event: "member.joined" },
        actions: [
          { type: "notify", to: { kind: "subject" }, message: t("automations.templates.welcomeMessage") },
          { type: "create_task", title: t("automations.templates.welcomeTask"), assign_to: { kind: "subject" }, due_in_days: 3 },
        ],
      },
    },
  ];
}

function fromAutomation(a: Automation): Draft {
  return JSON.parse(JSON.stringify({ name: a.name, enabled: a.enabled, trigger: a.trigger, conditions: a.conditions, actions: a.actions, drafted_by_ai: a.drafted_by_ai })) as Draft;
}

/** One sentence for when it runs. */
function useDescribe() {
  const { t } = useTranslation();
  return (a: Pick<Draft, "trigger">): string => {
    const tr = a.trigger;
    if (tr.type === "event") return t("automations.when.event", { event: t(`automations.events.${tr.event}`) });
    if (tr.every === "week") return t("automations.when.week", { day: t(`automations.weekdays.${tr.weekday}`), time: tr.time });
    if (tr.every === "month") return t("automations.when.month", { day: formatNumber(tr.day), time: tr.time });
    return t(`automations.when.${tr.every}`, { time: tr.time });
  };
}

function WhoPicker({ value, onChange, allowSubject, allowMe, label }: { value: Who | null; onChange: (w: Who | null) => void; allowSubject: boolean; allowMe?: boolean; label: string }) {
  const { t } = useTranslation();
  const roles = useRoles();
  const departments = useDepartments();
  const members = useQuery({ queryKey: ["members", "active"], queryFn: () => api<Page<Member>>("/v1/members", { query: { status: "active", limit: 200 } }) });
  const kinds = KINDS.filter((k) => k !== "subject" || allowSubject);
  return (
    <div className="flex flex-col gap-2">
      <Field label={label}>
        <Select value={value?.kind ?? ""} onChange={(e) => onChange(e.target.value ? { kind: e.target.value as Who["kind"] } : null)}>
          {allowMe && <option value="">{t("automations.who.me")}</option>}
          {kinds.map((k) => (
            <option key={k} value={k}>
              {t(`automations.who.${k}`)}
            </option>
          ))}
        </Select>
      </Field>
      {value?.kind === "role" && (
        <Field label={t("automations.role")}>
          <Select value={value.role ?? ""} onChange={(e) => onChange({ ...value, role: e.target.value })}>
            <option value="">–</option>
            {(roles.data ?? []).map((r) => (
              <option key={r.id} value={r.key}>
                {r.name}
              </option>
            ))}
          </Select>
        </Field>
      )}
      {value?.kind === "department" && (
        <Field label={t("automations.department")}>
          <Select value={value.department_id ?? ""} onChange={(e) => onChange({ ...value, department_id: e.target.value })}>
            <option value="">–</option>
            {departmentOptions(departments.data).map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
        </Field>
      )}
      {value?.kind === "people" && (
        <fieldset className="max-h-48 overflow-y-auto rounded-xl border border-border p-2">
          <legend className="sr-only">{t("automations.who.people")}</legend>
          {(members.data?.items ?? []).map((m) => {
            const chosen = value.membership_ids ?? [];
            return (
              <label key={m.id} className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-surface-2">
                <input
                  type="checkbox"
                  checked={chosen.includes(m.id)}
                  onChange={(e) => onChange({ ...value, membership_ids: e.target.checked ? [...chosen, m.id] : chosen.filter((x) => x !== m.id) })}
                />
                {m.name}
              </label>
            );
          })}
        </fieldset>
      )}
    </div>
  );
}

function Editor({ initial, id, version, onClose }: { initial: Draft; id: string | null; version?: number; onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Draft>(initial);
  const set = (patch: Partial<Draft>) => setDraft((d) => ({ ...d, ...patch }));
  const setAction = (i: number, patch: Partial<Step>) => set({ actions: draft.actions.map((a, j) => (j === i ? { ...a, ...patch } : a)) });
  const aboutSomeone = draft.trigger.type === "event" && ABOUT_SOMEONE.has(draft.trigger.event as (typeof EVENTS)[number]);
  const save = useMutation({
    mutationFn: () =>
      id
        ? api<Automation>(`/v1/automations/${id}`, { method: "PUT", body: draft, version })
        : api<Automation>("/v1/automations", { method: "POST", body: draft }),
    onSuccess: () => {
      toast.success(t("common.saved"));
      void queryClient.invalidateQueries({ queryKey: ["automations"] });
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const tr = draft.trigger;
  return (
    <SheetContent
      title={id ? t("automations.edit") : t("automations.new")}
      closeLabel={t("common.close")}
      footer={
        <>
          <Button onClick={onClose}>{t("common.cancel")}</Button>
          <Button variant="primary" loading={save.isPending} disabled={!draft.name.trim() || !draft.actions.length} onClick={() => save.mutate()}>
            {t("common.save")}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-5">
        {draft.drafted_by_ai && <Alert tone="info">{t("automations.draftedNote")}</Alert>}
        <Field label={t("automations.name")}>
          <Input value={draft.name} maxLength={200} onChange={(e) => set({ name: e.target.value })} />
        </Field>

        <fieldset className="flex flex-col gap-3">
          <legend className="mb-1 text-sm font-semibold">{t("automations.whenTitle")}</legend>
          <Field label={t("automations.startsFrom")}>
            <Select
              value={tr.type}
              onChange={(e) =>
                set(
                  e.target.value === "event"
                    ? { trigger: { type: "event", event: "leave.requested" } }
                    : { trigger: { type: "schedule", every: "week", time: "09:00", weekday: 1, day: 1 }, conditions: [] },
                )
              }
            >
              <option value="schedule">{t("automations.schedule")}</option>
              <option value="event">{t("automations.event")}</option>
            </Select>
          </Field>
          {tr.type === "schedule" ? (
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label={t("automations.every")}>
                <Select value={tr.every} onChange={(e) => set({ trigger: { ...tr, every: e.target.value as typeof tr.every } })}>
                  {(["day", "workdays", "week", "month"] as const).map((v) => (
                    <option key={v} value={v}>
                      {t(`automations.everyOptions.${v}`)}
                    </option>
                  ))}
                </Select>
              </Field>
              {tr.every === "week" && (
                <Field label={t("automations.weekday")}>
                  <Select value={String(tr.weekday)} onChange={(e) => set({ trigger: { ...tr, weekday: Number(e.target.value) } })}>
                    {[1, 2, 3, 4, 5, 6, 7].map((d) => (
                      <option key={d} value={d}>
                        {t(`automations.weekdays.${d}`)}
                      </option>
                    ))}
                  </Select>
                </Field>
              )}
              {tr.every === "month" && (
                <Field label={t("automations.dayOfMonth")}>
                  <Input type="number" min={1} max={28} value={tr.day} onChange={(e) => set({ trigger: { ...tr, day: Number(e.target.value) } })} />
                </Field>
              )}
              <Field label={t("automations.time")}>
                <Input type="time" value={tr.time} onChange={(e) => set({ trigger: { ...tr, time: e.target.value } })} />
              </Field>
            </div>
          ) : (
            <>
              <Field label={t("automations.event")}>
                <Select value={tr.event} onChange={(e) => set({ trigger: { type: "event", event: e.target.value } })}>
                  {EVENTS.map((ev) => (
                    <option key={ev} value={ev}>
                      {t(`automations.events.${ev}`)}
                    </option>
                  ))}
                </Select>
              </Field>
              <div className="flex flex-col gap-2">
                <span className="text-sm font-medium">{t("automations.onlyIf")}</span>
                {draft.conditions.map((c, i) => (
                  <div key={i} className="grid grid-cols-[1fr_auto_1fr_auto] items-end gap-2">
                    <Field label={t("automations.field")} hideLabel>
                      <Input value={c.field} placeholder={t("automations.fieldPlaceholder")} onChange={(e) => set({ conditions: draft.conditions.map((x, j) => (j === i ? { ...x, field: e.target.value } : x)) })} />
                    </Field>
                    <Field label={t("automations.op")} hideLabel>
                      <Select value={c.op} onChange={(e) => set({ conditions: draft.conditions.map((x, j) => (j === i ? { ...x, op: e.target.value as (typeof OPS)[number] } : x)) })}>
                        {OPS.map((o) => (
                          <option key={o} value={o}>
                            {t(`automations.ops.${o}`)}
                          </option>
                        ))}
                      </Select>
                    </Field>
                    <Field label={t("automations.value")} hideLabel>
                      <Input value={String(c.value)} onChange={(e) => set({ conditions: draft.conditions.map((x, j) => (j === i ? { ...x, value: e.target.value } : x)) })} />
                    </Field>
                    <Button variant="ghost" size="icon" aria-label={t("automations.removeCondition")} onClick={() => set({ conditions: draft.conditions.filter((_, j) => j !== i) })}>
                      <X aria-hidden="true" />
                    </Button>
                  </div>
                ))}
                {draft.conditions.length < 10 && (
                  <Button size="sm" className="self-start" onClick={() => set({ conditions: [...draft.conditions, { field: "", op: "eq", value: "" }] })}>
                    <Plus aria-hidden="true" />
                    {t("automations.addCondition")}
                  </Button>
                )}
              </div>
            </>
          )}
        </fieldset>

        <fieldset className="flex flex-col gap-3">
          <legend className="mb-1 text-sm font-semibold">{t("automations.thenTitle")}</legend>
          {draft.actions.map((a, i) => (
            <Card key={i} className="flex flex-col gap-3 p-4">
              <div className="flex items-end gap-2">
                <Field label={t("automations.do")} className="flex-1">
                  <Select
                    value={a.type}
                    onChange={(e) =>
                      setAction(i, e.target.value === "notify" ? { type: "notify", to: { kind: "everyone" }, message: "" } : { type: "create_task", title: "", assign_to: null, due_in_days: null })
                    }
                  >
                    <option value="notify">{t("automations.notify")}</option>
                    <option value="create_task">{t("automations.createTask")}</option>
                  </Select>
                </Field>
                {draft.actions.length > 1 && (
                  <Button variant="ghost" size="icon" aria-label={t("automations.removeStep")} onClick={() => set({ actions: draft.actions.filter((_, j) => j !== i) })}>
                    <Trash2 aria-hidden="true" />
                  </Button>
                )}
              </div>
              {a.type === "notify" ? (
                <>
                  <WhoPicker label={t("automations.tell")} value={a.to ?? { kind: "everyone" }} onChange={(w) => setAction(i, { to: w ?? { kind: "everyone" } })} allowSubject={aboutSomeone} />
                  <Field label={t("automations.message")} help={t("automations.placeholders")}>
                    <Textarea dir="auto" rows={2} maxLength={500} value={a.message ?? ""} onChange={(e) => setAction(i, { message: e.target.value })} />
                  </Field>
                </>
              ) : (
                <>
                  <Field label={t("automations.taskTitle")}>
                    <Input dir="auto" maxLength={200} value={a.title ?? ""} onChange={(e) => setAction(i, { title: e.target.value })} />
                  </Field>
                  <WhoPicker label={t("automations.for")} value={a.assign_to ?? null} onChange={(w) => setAction(i, { assign_to: w })} allowSubject={aboutSomeone} allowMe />
                  <Field label={t("automations.dueIn")} optional={t("common.optional")}>
                    <Input type="number" min={0} max={365} value={a.due_in_days ?? ""} onChange={(e) => setAction(i, { due_in_days: e.target.value === "" ? null : Number(e.target.value) })} />
                  </Field>
                </>
              )}
            </Card>
          ))}
          {draft.actions.length < 5 && (
            <Button size="sm" className="self-start" onClick={() => set({ actions: [...draft.actions, { type: "notify", to: { kind: "everyone" }, message: "" }] })}>
              <Plus aria-hidden="true" />
              {t("automations.addStep")}
            </Button>
          )}
        </fieldset>

        <label className="flex items-center gap-3 text-sm">
          <Switch checked={draft.enabled} onCheckedChange={(on) => set({ enabled: on })} aria-label={t("automations.on")} />
          {t("automations.onHelp")}
        </label>
      </div>
    </SheetContent>
  );
}

function Runs({ id }: { id: string }) {
  const { t } = useTranslation();
  const workspace = useWorkspace();
  const runs = useQuery({ queryKey: ["automations", id, "runs"], queryFn: () => api<AutomationRun[]>(`/v1/automations/${id}/runs`) });
  if (runs.isPending) return <Spinner />;
  if (!runs.data?.length) return <p className="text-sm text-muted">{t("automations.noRuns")}</p>;
  return (
    <ul className="flex flex-col gap-2">
      {runs.data.map((r) => (
        <li key={r.id} className="flex flex-col gap-1 rounded-xl border border-border p-3 text-sm">
          <span className="flex flex-wrap items-center gap-2">
            <Badge tone={r.status === "ok" ? "success" : r.status === "failed" ? "danger" : "warn"}>{t(`automations.runStatus.${r.status}`)}</Badge>
            <span className="tabular-nums text-muted">{formatDateTime(r.created_at, workspace.timezone)}</span>
          </span>
          {r.detail.map((d, i) => (
            <span key={i} className="text-muted">
              {t(`automations.did.${String(d.action)}`, { count: Number(d.count ?? 0), formatted: formatNumber(Number(d.count ?? 0)) })}
              {d.error ? ` – ${String(d.error)}` : ""}
            </span>
          ))}
          {r.error && <span className="text-danger-text">{r.error}</span>}
        </li>
      ))}
    </ul>
  );
}

function Describe({ onDraft }: { onDraft: (d: Draft) => void }) {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const draft = useMutation({
    mutationFn: () => api<AutomationDraft>("/v1/ai/automations/draft", { method: "POST", body: { text } }),
    onSuccess: (r) => {
      if (r.automation) onDraft(r.automation as unknown as Draft);
      else toast.error(r.note || t("automations.couldntDraft"));
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Card className="flex flex-col gap-3 p-4">
      <label htmlFor="describe" className="flex items-center gap-2 text-sm font-semibold">
        <Sparkles className="size-4 text-accent-soft-text" aria-hidden="true" />
        {t("automations.describe")}
      </label>
      <Textarea id="describe" dir="auto" rows={2} maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} placeholder={t("automations.describePlaceholder")} />
      <Button className="self-start" loading={draft.isPending} disabled={!text.trim()} onClick={() => draft.mutate()}>
        {t("automations.draftIt")}
      </Button>
    </Card>
  );
}

export default function AutomationsPage() {
  const { t } = useTranslation();
  const { can } = useSession();
  const workspace = useWorkspace();
  const queryClient = useQueryClient();
  const allowed = can("automations.manage");
  const ai = useAIStatus();
  const templates = useTemplates();
  const describe = useDescribe();
  const list = useQuery({ queryKey: ["automations"], queryFn: () => api<Automation[]>("/v1/automations"), enabled: allowed });
  const [editing, setEditing] = useState<{ draft: Draft; id: string | null; version?: number } | null>(null);
  const [history, setHistory] = useState<Automation | null>(null);
  const [deleting, setDeleting] = useState<Automation | null>(null);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["automations"] });
  const toggle = useMutation({
    mutationFn: (a: Automation) => api<Automation>(`/v1/automations/${a.id}`, { method: "PATCH", body: { enabled: !a.enabled } }),
    onSuccess: refresh,
    onError: (e) => toast.error(errorMessage(e)),
  });
  const runNow = useMutation({
    mutationFn: (a: Automation) => api<AutomationRun>(`/v1/automations/${a.id}/run`, { method: "POST" }),
    onSuccess: (r) => {
      if (r.status === "ok") toast.success(t("automations.ran"));
      else toast.error(r.error ?? t(`automations.runStatus.${r.status}`));
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const remove = useMutation({
    mutationFn: (a: Automation) => api(`/v1/automations/${a.id}`, { method: "DELETE" }),
    onSuccess: () => {
      setDeleting(null);
      refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (!allowed) return <EmptyState icon={<Workflow />} title={t("common.notAllowed")} />;
  const aiDrafts = !!ai.data && ai.data.available && ai.data.enabled && ai.data.features.includes("automations");
  return (
    <>
      <PageHeader
        title={t("automations.title")}
        sub={t("automations.sub")}
        actions={
          <Button variant="primary" onClick={() => setEditing({ draft: blank(), id: null })}>
            <Plus aria-hidden="true" />
            {t("automations.new")}
          </Button>
        }
      />
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        {aiDrafts && <Describe onDraft={(d) => setEditing({ draft: { ...blank(), ...d }, id: null })} />}
        {list.isPending ? (
          <div className="grid place-items-center py-16">
            <Spinner />
          </div>
        ) : !list.data?.length ? (
          <Card className="flex flex-col gap-3 p-5">
            <p className="text-sm text-muted">{t("automations.empty")}</p>
            <div className="flex flex-wrap gap-2">
              {templates.map((tpl) => (
                <Button key={tpl.key} size="sm" onClick={() => setEditing({ draft: tpl.draft, id: null })}>
                  {tpl.draft.name}
                </Button>
              ))}
            </div>
          </Card>
        ) : (
          <ul className="flex flex-col gap-3">
            {list.data.map((a) => (
              <li key={a.id}>
                <Card className="flex flex-col gap-3 p-4">
                  <div className="flex items-start gap-3">
                    <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                      <span className="flex flex-wrap items-center gap-2 font-medium">
                        {a.name}
                        {a.drafted_by_ai && <Badge tone="accent">{t("automations.drafted")}</Badge>}
                      </span>
                      <span className="text-sm text-muted">{describe(fromAutomation(a))}</span>
                      <span className="text-xs text-muted">
                        {a.next_run_at ? t("automations.next", { when: formatDateTime(a.next_run_at, workspace.timezone) }) : null}
                        {a.last_run_at ? ` ${t("automations.last", { when: formatDateTime(a.last_run_at, workspace.timezone) })}` : null}
                        {a.owner_name ? ` ${t("automations.runsAs", { name: a.owner_name })}` : null}
                      </span>
                    </span>
                    <Switch checked={a.enabled} disabled={toggle.isPending} onCheckedChange={() => toggle.mutate(a)} aria-label={t("automations.switchFor", { name: a.name })} />
                  </div>
                  {a.paused_reason && <Alert tone="warn">{a.paused_reason}</Alert>}
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" onClick={() => setEditing({ draft: fromAutomation(a), id: a.id, version: a.version })}>
                      <Pencil aria-hidden="true" />
                      {t("common.edit")}
                    </Button>
                    {a.trigger.type === "schedule" && (
                      <Button size="sm" loading={runNow.isPending && runNow.variables?.id === a.id} onClick={() => runNow.mutate(a)}>
                        <Play aria-hidden="true" />
                        {t("automations.runNow")}
                      </Button>
                    )}
                    <Button size="sm" onClick={() => setHistory(a)}>
                      <History aria-hidden="true" />
                      {t("automations.history")}
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setDeleting(a)}>
                      <Trash2 aria-hidden="true" />
                      {t("common.delete")}
                    </Button>
                  </div>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </div>
      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        {editing && <Editor key={editing.id ?? "new"} initial={editing.draft} id={editing.id} version={editing.version} onClose={() => setEditing(null)} />}
      </Dialog>
      <Dialog open={!!history} onOpenChange={(o) => !o && setHistory(null)}>
        {history && (
          <SheetContent title={t("automations.historyOf", { name: history.name })} closeLabel={t("common.close")}>
            <Runs id={history.id} />
          </SheetContent>
        )}
      </Dialog>
      <ConfirmDialog
        open={!!deleting}
        title={t("automations.deleteTitle", { name: deleting?.name ?? "" })}
        confirmLabel={t("common.delete")}
        busy={remove.isPending}
        onConfirm={() => deleting && remove.mutate(deleting)}
        onClose={() => setDeleting(null)}
      >
        {t("automations.deleteBody")}
      </ConfirmDialog>
    </>
  );
}
