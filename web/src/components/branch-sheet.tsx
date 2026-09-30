"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Crosshair, ExternalLink, MapPin } from "lucide-react";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { Branch } from "@/api/types";
import { useWorkspace } from "@/auth/session";
import { intlLocale } from "@/i18n";
import { applyFieldErrors, errorMessage } from "@/lib/errors";
import { currentPosition, formatDistance, LocationError } from "@/lib/geolocation";
import { timezoneOptions } from "@/lib/places";

import { Alert } from "./ui/alert";
import { Button } from "./ui/button";
import { Switch } from "./ui/choice";
import { Dialog, SheetContent } from "./ui/dialog";
import { Field } from "./ui/field";
import { Input, Select, Textarea } from "./ui/input";

interface Values {
  name: string;
  timezone: string;
  address: string;
  latitude: string;
  longitude: string;
  geofence_m: string;
  is_active: boolean;
}

const FIELDS = ["name", "timezone", "address", "latitude", "longitude", "geofence_m", "is_active"] as const;

/** Add or edit a branch, including where it is and how far "at work" reaches. */
export function BranchSheet({ branch, onClose }: { branch: Branch | "new"; onClose: () => void }) {
  const { t } = useTranslation();
  const workspace = useWorkspace();
  const queryClient = useQueryClient();
  const isNew = branch === "new";
  const [locating, setLocating] = useState(false);
  const [note, setNote] = useState<{ tone: "info" | "warn" | "error"; text: string } | null>(null);
  const { register, handleSubmit, setValue, control, setError, formState } = useForm<Values>({
    defaultValues: isNew
      ? { name: "", timezone: workspace.timezone, address: "", latitude: "", longitude: "", geofence_m: "150", is_active: true }
      : {
          name: branch.name,
          timezone: branch.timezone,
          address: branch.address ?? "",
          latitude: branch.latitude?.toString() ?? "",
          longitude: branch.longitude?.toString() ?? "",
          geofence_m: String(branch.geofence_m),
          is_active: branch.is_active,
        },
  });
  const [lat, lng, radiusText, active] = useWatch({ control, name: ["latitude", "longitude", "geofence_m", "is_active"] });
  const radius = Number(radiusText) || 150;
  const placed = lat.trim() !== "" && lng.trim() !== "";

  const placeHere = async () => {
    setLocating(true);
    setNote(null);
    try {
      const here = await currentPosition({ timeoutMs: 20_000 });
      setValue("latitude", here.latitude.toFixed(6), { shouldDirty: true });
      setValue("longitude", here.longitude.toFixed(6), { shouldDirty: true });
      const accuracy = formatDistance(here.accuracy_m, intlLocale());
      setNote(here.accuracy_m > 100 ? { tone: "warn", text: t("branch.lowAccuracy", { accuracy }) } : { tone: "info", text: t("branch.placedHere", { accuracy }) });
    } catch (e) {
      setNote({ tone: "error", text: e instanceof LocationError ? t(`location.${e.problem}`) : errorMessage(e) });
    } finally {
      setLocating(false);
    }
  };

  const save = useMutation({
    mutationFn: (v: Values) => {
      const location = placed ? { latitude: Number(v.latitude), longitude: Number(v.longitude) } : {};
      const body: Record<string, unknown> = {
        name: v.name.trim(),
        timezone: v.timezone,
        address: v.address.trim() || undefined,
        geofence_m: Number(v.geofence_m),
        ...location,
      };
      if (isNew) return api("/v1/branches", { body });
      if (!placed && branch.latitude !== null) body.clear_location = true;
      body.is_active = v.is_active;
      return api(`/v1/branches/${branch.id}`, { method: "PATCH", body, version: branch.version });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["branches"] });
      await queryClient.invalidateQueries({ queryKey: ["attendance", "settings"] });
      toast.success(t("common.saved"));
      onClose();
    },
    onError: (e) => {
      if (!applyFieldErrors(setError, FIELDS, e)) toast.error(errorMessage(e));
    },
  });
  const errors = formState.errors;
  const coordinate = (min: number, max: number) => ({
    validate: (v: string) => {
      if (v.trim() === "") return placed || lat.trim() === lng.trim() || t("branch.bothCoordinates");
      const n = Number(v);
      return (Number.isFinite(n) && n >= min && n <= max) || t("branch.badCoordinate");
    },
  });

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <SheetContent
        title={isNew ? t("settings.addBranch") : t("branch.editTitle", { name: branch.name })}
        closeLabel={t("common.close")}
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" type="submit" form="branch-form" loading={save.isPending}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        <form id="branch-form" onSubmit={handleSubmit((v) => save.mutate(v))} className="flex flex-col gap-5" noValidate>
          <Field label={t("settings.branchName")} error={errors.name?.message}>
            <Input {...register("name", { validate: (v) => v.trim().length > 0 || t("common.required") })} />
          </Field>
          <Field label={t("settings.timezone")} error={errors.timezone?.message}>
            <Select {...register("timezone")}>
              {timezoneOptions().map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("settings.address")} optional={t("common.optional")}>
            <Textarea rows={2} maxLength={500} {...register("address")} />
          </Field>

          <fieldset className="flex flex-col gap-4 rounded-2xl border border-border p-4">
            <legend className="flex items-center gap-2 px-1 text-sm font-semibold">
              <MapPin className="size-4 text-accent-soft-text" aria-hidden="true" />
              {t("location.settingsTitle")}
            </legend>
            <p className="-mt-1 text-[13px] text-muted">{t("branch.locationHelp")}</p>
            <Button type="button" onClick={() => void placeHere()} loading={locating} className="self-start">
              {!locating && <Crosshair aria-hidden="true" />}
              {t("location.useMyLocation")}
            </Button>
            {note && <Alert tone={note.tone}>{note.text}</Alert>}
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t("location.latitude")} error={errors.latitude?.message}>
                <Input inputMode="decimal" placeholder="23.738300" {...register("latitude", coordinate(-90, 90))} />
              </Field>
              <Field label={t("location.longitude")} error={errors.longitude?.message}>
                <Input inputMode="decimal" placeholder="90.395800" {...register("longitude", coordinate(-180, 180))} />
              </Field>
            </div>
            <Field label={`${t("location.radius")}: ${formatDistance(radius, intlLocale())}`} help={t("location.radiusHelp")} error={errors.geofence_m?.message}>
              <input type="range" min={25} max={1000} step={25} className="w-full accent-[var(--accent)]" {...register("geofence_m")} />
            </Field>
            {placed && (
              <div className="flex flex-wrap items-center gap-3">
                <a
                  href={`https://www.openstreetmap.org/?mlat=${encodeURIComponent(lat)}&mlon=${encodeURIComponent(lng)}#map=17/${encodeURIComponent(lat)}/${encodeURIComponent(lng)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-sm font-medium text-accent-soft-text hover:underline"
                >
                  {t("branch.checkOnMap")}
                  <ExternalLink className="size-3.5" aria-hidden="true" />
                  <span className="sr-only">({t("common.opensNewTab")})</span>
                </a>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="text-danger"
                  onClick={() => {
                    setValue("latitude", "", { shouldDirty: true });
                    setValue("longitude", "", { shouldDirty: true });
                    setNote(null);
                  }}
                >
                  {t("location.clearLocation")}
                </Button>
              </div>
            )}
          </fieldset>

          {!isNew && (
            <label className="flex items-center justify-between gap-3 rounded-2xl border border-border p-4">
              <span className="flex flex-col">
                <span className="text-sm font-medium">{active ? t("settings.open") : t("settings.closed")}</span>
                <span className="text-[13px] text-muted">{t("branch.openHelp")}</span>
              </span>
              <Switch checked={active} onCheckedChange={(v) => setValue("is_active", v, { shouldDirty: true })} aria-label={t("common.status")} />
            </label>
          )}
        </form>
      </SheetContent>
    </Dialog>
  );
}
