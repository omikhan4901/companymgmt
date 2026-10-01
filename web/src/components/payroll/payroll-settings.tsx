"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import { usePayrollSettings } from "@/api/hooks";
import type { PayrollSettings } from "@/api/types";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Switch } from "@/components/ui/choice";
import { Field } from "@/components/ui/field";
import { Input, Select } from "@/components/ui/input";
import { normalizeDigits } from "@/lib/format";
import { fromMinor, toMinor } from "@/lib/money";

import { payrollError } from "./shared";

interface Slab {
  width: string;
  rate: string;
}

function Form({ settings }: { settings: PayrollSettings }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [f, setF] = useState({
    day_basis: settings.day_basis,
    hours_per_day: String(settings.hours_per_day),
    overtime_multiplier: String(settings.overtime_multiplier),
    overtime_divisor: String(settings.overtime_divisor),
    bonus_percent: String(settings.bonus_percent),
    bonus_min_months: String(settings.bonus_min_months),
    round_net: settings.round_net,
    tax_enabled: settings.tax_enabled,
    tax_free: fromMinor(settings.tax_table.tax_free),
    exempt_fraction: settings.tax_table.exempt_fraction ?? "0",
    exempt_cap: fromMinor(settings.tax_table.exempt_cap),
    minimum: fromMinor(settings.tax_table.minimum),
  });
  const [slabs, setSlabs] = useState<Slab[]>(
    (settings.tax_table.slabs ?? []).map((s) => ({ width: s.width === null || s.width === undefined ? "" : fromMinor(s.width), rate: String(s.rate) })),
  );
  const set = (key: keyof typeof f, value: string | boolean) => setF((x) => ({ ...x, [key]: value }));
  const num = (v: string) => Number(normalizeDigits(v));
  const save = useMutation({
    mutationFn: () =>
      api("/v1/payroll/settings", {
        method: "PUT",
        body: {
          day_basis: f.day_basis,
          hours_per_day: num(f.hours_per_day),
          overtime_multiplier: num(f.overtime_multiplier),
          overtime_divisor: num(f.overtime_divisor),
          bonus_percent: num(f.bonus_percent),
          bonus_min_months: num(f.bonus_min_months),
          round_net: f.round_net,
          tax_enabled: f.tax_enabled,
          tax_table: {
            name: settings.tax_table.name ?? "",
            tax_free: toMinor(f.tax_free) ?? 0,
            exempt_fraction: f.exempt_fraction.trim() || "0",
            exempt_cap: f.exempt_cap.trim() ? toMinor(f.exempt_cap) : null,
            minimum: toMinor(f.minimum) ?? 0,
            slabs: slabs.map((s, i) => ({ width: i === slabs.length - 1 && !s.width.trim() ? null : toMinor(s.width), rate: num(s.rate) })),
          },
        },
      }),
    onSuccess: () => {
      toast.success(t("common.saved"));
      void queryClient.invalidateQueries({ queryKey: ["payroll", "settings"] });
    },
    onError: (e) => toast.error(payrollError(e)),
  });
  const text = (key: keyof typeof f, label: string, mode: "decimal" | "numeric" = "decimal", help?: string) => (
    <Field label={label} help={help}>
      <Input inputMode={mode} value={String(f[key])} onChange={(e) => set(key, e.target.value)} />
    </Field>
  );
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card>
        <CardHeader title={t("payroll.settings")} />
        <div className="grid gap-4 px-5 pb-5 pt-2 sm:grid-cols-2">
          <Field label={t("payroll.dayBasis")} className="sm:col-span-2">
            <Select value={f.day_basis} onChange={(e) => set("day_basis", e.target.value)}>
              <option value="calendar">{t("payroll.dayBasisCalendar")}</option>
              <option value="thirty">{t("payroll.dayBasisThirty")}</option>
            </Select>
          </Field>
          {text("hours_per_day", t("payroll.hoursPerDay"), "numeric")}
          {text("overtime_multiplier", t("payroll.otMultiplier"))}
          {text("overtime_divisor", t("payroll.otDivisor"), "numeric")}
          {text("bonus_percent", t("payroll.bonusPercent"), "numeric")}
          {text("bonus_min_months", t("payroll.bonusMonths"), "numeric")}
          <label className="flex items-center justify-between gap-4 text-sm sm:col-span-2">
            {t("payroll.roundNet")}
            <Switch checked={f.round_net} onCheckedChange={(on) => set("round_net", on)} />
          </label>
        </div>
      </Card>
      <Card>
        <CardHeader title={t("payroll.tax")} />
        <div className="flex flex-col gap-4 px-5 pb-5 pt-2">
          <Alert tone="warn">
            {settings.tax_table.name ? <span className="block font-medium">{settings.tax_table.name}</span> : null}
            {t("payroll.taxWarning")}
          </Alert>
          <label className="flex items-center justify-between gap-4 text-sm">
            {t("payroll.taxOn")}
            <Switch checked={f.tax_enabled} onCheckedChange={(on) => set("tax_enabled", on)} />
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            {text("tax_free", t("payroll.taxFree"))}
            {text("exempt_fraction", t("payroll.exemptFraction"), "decimal", "1/3")}
            {text("exempt_cap", t("payroll.exemptCap"))}
            {text("minimum", t("payroll.minimumTax"))}
          </div>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 text-sm font-medium">{t("payroll.slabs")}</legend>
            {slabs.map((s, i) => {
              const last = i === slabs.length - 1;
              return (
                <div key={i} className="flex items-end gap-2">
                  <Field label={last && !s.width ? t("payroll.slabRest") : t("payroll.slabWidth")} className="flex-1">
                    <Input inputMode="decimal" value={s.width} onChange={(e) => setSlabs(slabs.map((x, j) => (j === i ? { ...x, width: e.target.value } : x)))} />
                  </Field>
                  <Field label={t("payroll.slabRate")} className="w-24">
                    <Input inputMode="decimal" value={s.rate} onChange={(e) => setSlabs(slabs.map((x, j) => (j === i ? { ...x, rate: e.target.value } : x)))} />
                  </Field>
                  <Button variant="ghost" size="sm" aria-label={`${t("payroll.removeSlab")} ${i + 1}`} onClick={() => setSlabs(slabs.filter((_, j) => j !== i))}>
                    <Trash2 aria-hidden="true" />
                  </Button>
                </div>
              );
            })}
            <div>
              <Button size="sm" onClick={() => setSlabs([...slabs, { width: "", rate: "" }])}>
                <Plus aria-hidden="true" />
                {t("payroll.addSlab")}
              </Button>
            </div>
          </fieldset>
        </div>
      </Card>
      <div className="xl:col-span-2">
        <Button variant="primary" loading={save.isPending} onClick={() => save.mutate()}>
          {t("common.save")}
        </Button>
      </div>
    </div>
  );
}

export function PayrollSettingsTab() {
  const settings = usePayrollSettings();
  return settings.data ? <Form key={settings.dataUpdatedAt} settings={settings.data} /> : null;
}
