"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import { useBranches, useHolidays, useLeavePolicy, useLeaveTypes } from "@/api/hooks";
import type { Holiday, LeavePolicy, LeaveType } from "@/api/types";
import { useWorkspace } from "@/auth/session";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Switch } from "@/components/ui/choice";
import { ConfirmDialog } from "@/components/ui/confirm";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select } from "@/components/ui/input";
import { cn } from "@/lib/cn";
import { applyFieldErrors, errorMessage } from "@/lib/errors";
import { formatDay, formatNumber, formatYear, todayIn } from "@/lib/format";

import { TypeDot } from "./shared";

// ---- Leave types ----------------------------------------------------------------------

interface TypeValues {
  name: string;
  unlimited: boolean;
  days_per_year: string;
  paid: boolean;
  accrual: "yearly" | "monthly";
  carry_over_max: string;
  allow_half_day: boolean;
  calendar_days: boolean;
  prorate: boolean;
  active: boolean;
  color: string;
}

const TYPE_FIELDS = ["name", "days_per_year", "carry_over_max", "color"] as const;

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center justify-between gap-4 py-1 text-sm">
      <span>{label}</span>
      <Switch checked={checked} onCheckedChange={onChange} />
    </label>
  );
}

function TypeDialog({ kind, onClose }: { kind: LeaveType | "new"; onClose: () => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const isNew = kind === "new";
  const { register, handleSubmit, setError, setValue, control, formState } = useForm<TypeValues>({
    defaultValues: isNew
      ? { name: "", unlimited: false, days_per_year: "10", paid: true, accrual: "yearly", carry_over_max: "0", allow_half_day: true, calendar_days: false, prorate: true, active: true, color: "#6d28d9" }
      : {
          name: kind.name,
          unlimited: kind.days_per_year === null,
          days_per_year: String(kind.days_per_year ?? ""),
          paid: kind.paid,
          accrual: kind.accrual,
          carry_over_max: String(kind.carry_over_max),
          allow_half_day: kind.allow_half_day,
          calendar_days: kind.calendar_days,
          prorate: kind.prorate,
          active: kind.active,
          color: kind.color,
        },
  });
  const v = useWatch({ control });
  const save = useMutation({
    mutationFn: (values: TypeValues) => {
      const body = {
        name: values.name.trim(),
        paid: values.paid,
        accrual: values.accrual,
        carry_over_max: values.unlimited ? 0 : Number(values.carry_over_max || 0),
        allow_half_day: values.allow_half_day,
        calendar_days: values.calendar_days,
        prorate: values.prorate,
        color: values.color,
      };
      if (isNew) return api("/v1/leave/types", { body: { ...body, days_per_year: values.unlimited ? null : Number(values.days_per_year) } });
      const days = values.unlimited ? { unlimited: true } : { days_per_year: Number(values.days_per_year) };
      return api(`/v1/leave/types/${kind.id}`, { method: "PATCH", body: { ...body, ...days, active: values.active }, version: kind.version });
    },
    onSuccess: () => {
      toast.success(t("common.saved"));
      void queryClient.invalidateQueries({ queryKey: ["leave"] });
      onClose();
    },
    onError: (e) => {
      if (!applyFieldErrors(setError, TYPE_FIELDS, e)) toast.error(errorMessage(e));
    },
  });
  const flag = (key: "unlimited" | "paid" | "allow_half_day" | "calendar_days" | "prorate" | "active", label: string) => (
    <Toggle label={label} checked={!!v[key]} onChange={(on) => setValue(key, on, { shouldDirty: true })} />
  );
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={isNew ? t("leave.addType") : t("leave.editType")}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" type="submit" form="type-form" loading={save.isPending}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <form id="type-form" onSubmit={handleSubmit((values) => save.mutate(values))} className="flex flex-col gap-4" noValidate>
          <div className="grid gap-4 sm:grid-cols-[1fr_auto]">
            <Field label={t("leave.name")} error={formState.errors.name?.message}>
              <Input maxLength={80} {...register("name", { required: t("common.required") })} />
            </Field>
            <Field label={t("leave.color")} error={formState.errors.color?.message}>
              <Input type="color" className="h-10 w-16 p-1" {...register("color")} />
            </Field>
          </div>
          {flag("unlimited", t("leave.unlimited"))}
          {!v.unlimited && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t("leave.daysPerYear")} error={formState.errors.days_per_year?.message}>
                <Input type="number" inputMode="decimal" min={0} max={366} step={0.5} {...register("days_per_year", { required: t("common.required") })} />
              </Field>
              <Field label={t("leave.carryOver")} error={formState.errors.carry_over_max?.message}>
                <Input type="number" inputMode="decimal" min={0} max={366} step={0.5} {...register("carry_over_max")} />
              </Field>
              <Field label={t("leave.accrual")} className="sm:col-span-2">
                <Select {...register("accrual")}>
                  <option value="yearly">{t("leave.accrualYearly")}</option>
                  <option value="monthly">{t("leave.accrualMonthly")}</option>
                </Select>
              </Field>
            </div>
          )}
          <div className="flex flex-col divide-y divide-border rounded-xl border border-border px-3.5 py-1">
            {flag("paid", t("leave.paid"))}
            {flag("allow_half_day", t("leave.halfDays"))}
            {flag("calendar_days", t("leave.calendarDays"))}
            {!v.unlimited && flag("prorate", t("leave.prorate"))}
            {!isNew && flag("active", t("leave.inUse"))}
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function TypesCard() {
  const { t } = useTranslation();
  const types = useLeaveTypes(true);
  const [editing, setEditing] = useState<LeaveType | "new" | null>(null);
  return (
    <Card>
      <CardHeader
        title={t("leave.types")}
        action={
          <Button size="sm" onClick={() => setEditing("new")}>
            <Plus aria-hidden="true" />
            {t("leave.addType")}
          </Button>
        }
      />
      <ul className="divide-y divide-border px-5 pb-3">
        {(types.data ?? []).map((k) => (
          <li key={k.id} className="flex items-center gap-3 py-3">
            <TypeDot color={k.color} />
            <div className="min-w-0 flex-1">
              <p className={cn("font-medium", !k.active && "text-muted")}>{k.name}</p>
              <p className="text-[13px] text-muted">
                {[
                  k.days_per_year === null ? t("leave.noLimit") : t("leave.perYear", { n: formatNumber(k.days_per_year) }),
                  k.accrual === "monthly" && k.days_per_year !== null ? t("leave.monthly") : null,
                  k.paid ? t("leave.paid") : t("leave.unpaid"),
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            </div>
            {!k.active && <Badge>{t("leave.off")}</Badge>}
            <Button size="sm" variant="ghost" onClick={() => setEditing(k)} aria-label={`${t("common.edit")}: ${k.name}`}>
              <Pencil aria-hidden="true" />
              {t("common.edit")}
            </Button>
          </li>
        ))}
      </ul>
      {editing && <TypeDialog kind={editing} onClose={() => setEditing(null)} />}
    </Card>
  );
}

// ---- Work week ------------------------------------------------------------------------

// 2024-01-01 was a Monday, so day n of that week has ISO weekday n.
const weekdayName = (n: number) => formatDay(`2024-01-0${n}`, { weekday: "long", day: undefined, month: undefined, year: undefined });

function WeekForm({ policy }: { policy: LeavePolicy }) {
  const { t } = useTranslation();
  const { week_start } = useWorkspace();
  const queryClient = useQueryClient();
  const [off, setOff] = useState(new Set(policy.weekly_off));
  const [teamCalendar, setTeamCalendar] = useState(policy.team_calendar);
  const save = useMutation({
    mutationFn: () => api("/v1/leave/policy", { method: "PUT", body: { weekly_off: [...off].sort(), team_calendar: teamCalendar } }),
    onSuccess: () => {
      toast.success(t("common.saved"));
      void queryClient.invalidateQueries({ queryKey: ["leave"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const order = Array.from({ length: 7 }, (_, i) => ((week_start - 1 + i) % 7) + 1);
  const toggle = (n: number) => {
    const next = new Set(off);
    if (next.has(n)) next.delete(n);
    else if (next.size < 6) next.add(n);
    setOff(next);
  };
  return (
    <div className="flex flex-col gap-4 px-5 pb-5 pt-2">
      <p className="text-sm text-muted">{t("leave.weekHelp")}</p>
      <div className="flex flex-wrap gap-2" role="group" aria-label={t("leave.week")}>
        {order.map((n) => (
          <button
            key={n}
            type="button"
            aria-pressed={off.has(n)}
            onClick={() => toggle(n)}
            className={cn(
              "min-h-10 rounded-lg border px-3 text-sm font-medium transition-colors",
              off.has(n) ? "border-accent bg-accent text-on-accent" : "border-border bg-surface hover:border-border-strong",
            )}
          >
            {weekdayName(n)}
          </button>
        ))}
      </div>
      <Toggle label={t("leave.teamCalendar")} checked={teamCalendar} onChange={setTeamCalendar} />
      <div>
        <Button variant="primary" loading={save.isPending} onClick={() => save.mutate()}>
          {t("common.save")}
        </Button>
      </div>
    </div>
  );
}

function WeekCard() {
  const { t } = useTranslation();
  const policy = useLeavePolicy();
  return (
    <Card>
      <CardHeader title={t("leave.week")} />
      {policy.data && <WeekForm key={policy.dataUpdatedAt} policy={policy.data} />}
    </Card>
  );
}

// ---- Holidays -------------------------------------------------------------------------

interface HolidayValues {
  day: string;
  name: string;
  branch_id: string;
}

function HolidaysCard() {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const queryClient = useQueryClient();
  const thisYear = Number(todayIn(timezone).slice(0, 4));
  const [year, setYear] = useState(thisYear);
  const holidays = useHolidays(year);
  const branches = useBranches();
  const [removing, setRemoving] = useState<Holiday | null>(null);
  const { register, handleSubmit, reset, setError, formState } = useForm<HolidayValues>({ defaultValues: { day: "", name: "", branch_id: "" } });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["leave", "holidays"] });
  const add = useMutation({
    mutationFn: (v: HolidayValues) => api("/v1/leave/holidays", { body: { day: v.day, name: v.name.trim(), branch_id: v.branch_id || undefined } }),
    onSuccess: () => {
      reset();
      void refresh();
    },
    onError: (e) => {
      if (!applyFieldErrors(setError, ["day", "name", "branch_id"], e)) toast.error(errorMessage(e));
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/v1/leave/holidays/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      setRemoving(null);
      void refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const branchName = new Map((branches.data ?? []).map((b) => [b.id, b.name]));
  const multiBranch = (branches.data?.length ?? 0) > 1;
  return (
    <Card>
      <CardHeader
        title={t("leave.holidays")}
        action={
          <Field label={t("leave.year")} hideLabel className="w-28">
            <Select value={year} onChange={(e) => setYear(Number(e.target.value))}>
              {[thisYear - 1, thisYear, thisYear + 1].map((y) => (
                <option key={y} value={y}>
                  {formatYear(y)}
                </option>
              ))}
            </Select>
          </Field>
        }
      />
      <div className="flex flex-col gap-4 px-5 pb-5 pt-2">
        <p className="text-sm text-muted">{t("leave.holidayHelp")}</p>
        {holidays.data?.length === 0 && <p className="text-sm text-muted">{t("leave.noHolidays", { year: formatYear(year) })}</p>}
        <ul className="divide-y divide-border">
          {(holidays.data ?? []).map((h) => (
            <li key={h.id} className="flex items-center gap-3 py-2.5">
              <span className="w-28 shrink-0 text-sm tabular-nums text-muted">{formatDay(h.day, { weekday: "short", year: undefined })}</span>
              <span className="min-w-0 flex-1 truncate text-sm font-medium">{h.name}</span>
              {h.branch_id && <Badge>{branchName.get(h.branch_id) ?? t("leave.branch")}</Badge>}
              <Button size="sm" variant="ghost" onClick={() => setRemoving(h)} aria-label={`${t("common.remove")}: ${h.name}`}>
                <Trash2 aria-hidden="true" />
              </Button>
            </li>
          ))}
        </ul>
        <form onSubmit={handleSubmit((v) => add.mutate(v))} className="flex flex-wrap items-end gap-3 border-t border-border pt-4" noValidate>
          <Field label={t("leave.day")} error={formState.errors.day?.message} className="w-44">
            <Input type="date" {...register("day", { required: t("common.required") })} />
          </Field>
          <Field label={t("leave.name")} error={formState.errors.name?.message} className="min-w-48 flex-1">
            <Input maxLength={120} {...register("name", { required: t("common.required") })} />
          </Field>
          {multiBranch && (
            <Field label={t("leave.branch")} className="w-48">
              <Select {...register("branch_id")}>
                <option value="">{t("leave.allBranches")}</option>
                {(branches.data ?? []).map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </Select>
            </Field>
          )}
          <Button type="submit" loading={add.isPending}>
            <Plus aria-hidden="true" />
            {t("leave.addHoliday")}
          </Button>
        </form>
      </div>
      <ConfirmDialog
        open={!!removing}
        title={t("leave.removeHoliday", { name: removing?.name ?? "" })}
        confirmLabel={t("common.remove")}
        busy={remove.isPending}
        onConfirm={() => removing && remove.mutate(removing.id)}
        onClose={() => setRemoving(null)}
      />
    </Card>
  );
}

export function LeaveSettings() {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <TypesCard />
      <div className="flex flex-col gap-4">
        <WeekCard />
        <HolidaysCard />
      </div>
    </div>
  );
}
