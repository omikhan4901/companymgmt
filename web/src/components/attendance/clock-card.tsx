"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, LogIn, LogOut, MapPin } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api, ApiError } from "@/api/client";
import { useAttendanceStatus, useBranches } from "@/api/hooks";
import type { AttendanceRecord } from "@/api/types";
import { useWorkspace } from "@/auth/session";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { intlLocale } from "@/i18n";
import { cn } from "@/lib/cn";
import { errorMessage } from "@/lib/errors";
import { formatDuration, formatNumber, formatTime } from "@/lib/format";
import { currentPosition, formatDistance, LocationError, type Position } from "@/lib/geolocation";

import { CorrectionDialog } from "./correction-dialog";
import { GeoBadge } from "./geo-badge";

type Problem = { tone: "error" | "warn"; text: string };

function clockText(total: number): string {
  const h = Math.floor(total / 60);
  const m = total % 60;
  return `${formatNumber(h)}:${String(m).padStart(2, "0").replace(/\d/g, (d) => formatNumber(Number(d)))}`;
}

/** The one big action for most people: clock in or out, at a branch. */
export function ClockCard({ className }: { className?: string }) {
  const { t } = useTranslation();
  const workspace = useWorkspace();
  const queryClient = useQueryClient();
  const status = useAttendanceStatus();
  const branches = useBranches();
  const [fixing, setFixing] = useState(false);
  const [locating, setLocating] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 20_000);
    return () => clearInterval(id);
  }, []);

  const mode = status.data?.location_mode ?? "off";

  const locationText = (e: LocationError) => t(`location.${e.problem}`);

  const clock = useMutation({
    mutationFn: async (direction: "in" | "out") => {
      setProblem(null);
      let location: Position | undefined;
      if (mode !== "off") {
        setLocating(true);
        try {
          location = await currentPosition();
        } catch (e) {
          // Clock-in with location required can't go ahead; anything else goes on and is flagged.
          if (!(e instanceof LocationError)) throw e;
          if (direction === "in" && mode === "require") throw e;
          setProblem({ tone: "warn", text: locationText(e) });
        } finally {
          setLocating(false);
        }
      }
      const body = direction === "in" ? { client_time: new Date().toISOString(), location } : { location };
      return api<AttendanceRecord>(`/v1/attendance/clock-${direction}`, { body });
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["attendance"] }),
    onSuccess: (record, direction) => {
      const geo = direction === "in" ? record.in_geo : record.out_geo;
      if (geo === "outside") {
        const distance = direction === "in" ? record.in_distance_m : record.out_distance_m;
        toast.warning(t("location.outsideShort", { distance: formatDistance(distance ?? 0, intlLocale()) }));
      }
    },
    onError: (e) => {
      if (e instanceof LocationError) return setProblem({ tone: "error", text: locationText(e) });
      if (e instanceof ApiError) {
        if (e.code === "forgot_clock_out") return setFixing(true);
        if (e.code === "already_clocked_in") return;
        if (e.code === "outside_area") {
          return setProblem({
            tone: "error",
            text: t("location.outside", { distance: formatDistance(Number(e.body.distance_m ?? 0), intlLocale()), branch: String(e.body.branch_name ?? "") }),
          });
        }
        if (e.code === "location_imprecise") {
          return setProblem({ tone: "error", text: t("location.imprecise", { accuracy: formatDistance(Number(e.body.accuracy_m ?? 0), intlLocale()) }) });
        }
        if (e.code === "location_required") return setProblem({ tone: "error", text: t("location.required") });
      }
      toast.error(errorMessage(e));
    },
  });

  if (status.isPending) {
    return (
      <section className={cn("grid min-h-56 place-items-center rounded-[var(--radius-card)] bg-accent text-on-accent", className)} role="status">
        <Spinner />
      </section>
    );
  }
  if (status.isError) {
    const noProfile = status.error instanceof ApiError && status.error.code === "no_profile";
    return <Alert tone="warn" className={className}>{noProfile ? t("home.noProfile") : errorMessage(status.error)}</Alert>;
  }

  const data = status.data;
  const open = data.open_record;
  const running = open && !data.forgot_clock_out ? Math.max(0, Math.floor((now - new Date(open.clock_in_at).getTime()) / 60_000)) : 0;
  const branchName = open ? branches.data?.find((b) => b.id === open.branch_id)?.name : undefined;
  const busy = clock.isPending;

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <section className="flex flex-col gap-5 rounded-[var(--radius-card)] bg-accent p-5 text-on-accent md:p-6" aria-live="polite">
        <div className="flex items-center justify-between gap-3 text-sm font-semibold">
          <span className="flex items-center gap-2">
            {data.forgot_clock_out ? <AlertTriangle className="size-4" aria-hidden="true" /> : <span className={cn("size-2 rounded-full", open ? "bg-on-accent" : "bg-on-accent/40")} aria-hidden="true" />}
            {data.forgot_clock_out && open
              ? t("home.forgot", { time: formatTime(open.clock_in_at, workspace.timezone) })
              : open
                ? t("home.clockedInSince", { time: formatTime(open.clock_in_at, workspace.timezone) })
                : t("home.notClockedIn")}
          </span>
          {branchName && (
            <span className="flex items-center gap-1 font-medium opacity-90">
              <MapPin className="size-3.5" aria-hidden="true" />
              {branchName}
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="flex flex-col gap-1">
            <span className="font-display text-6xl font-bold leading-none tracking-tight tabular-nums">{clockText(data.today_minutes + running)}</span>
            <span className="text-sm opacity-90">{t("home.workedToday", { duration: formatDuration(data.today_minutes + running, t) })}</span>
          </div>
          {data.forgot_clock_out ? (
            <Button size="lg" className="min-w-40 border-0 bg-surface text-text hover:bg-surface-2" onClick={() => setFixing(true)}>
              {t("home.fixIt")}
            </Button>
          ) : (
            <Button
              size="lg"
              className="h-14 min-w-44 border-0 bg-surface text-base text-text hover:bg-surface-2"
              loading={busy}
              onClick={() => clock.mutate(open ? "out" : "in")}
            >
              {!busy && (open ? <LogOut aria-hidden="true" /> : <LogIn aria-hidden="true" />)}
              {locating ? t("location.asking") : open ? t("home.clockOut") : t("home.clockIn")}
            </Button>
          )}
        </div>
        {open?.in_geo && (
          <div>
            <span className="inline-flex rounded-md bg-surface/95 p-0.5">
              <GeoBadge geo={open.in_geo} distance={open.in_distance_m} />
            </span>
          </div>
        )}
      </section>
      {problem && <Alert tone={problem.tone}>{problem.text}</Alert>}
      {fixing && open && <CorrectionDialog record={open} onClose={() => setFixing(false)} />}
    </div>
  );
}
