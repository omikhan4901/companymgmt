import { useMutation, useQueryClient } from "@tanstack/react-query";
import { App, Button, Skeleton } from "antd";
import { AlertTriangle, LogIn, LogOut, Timer } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { api, ApiError } from "@/api/client";
import { useAttendanceStatus } from "@/api/hooks";
import { useWorkspace } from "@/auth/session";
import { errorMessage } from "@/lib/errors";
import { formatDuration, formatTime } from "@/lib/format";

import CorrectionModal from "./CorrectionModal";
import { Card, IconTile } from "./ui";

/** The one big action for most people: clock in or out. */
export default function ClockCard() {
  const { t } = useTranslation();
  const workspace = useWorkspace();
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const status = useAttendanceStatus();
  const [fixing, setFixing] = useState(false);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(id);
  }, []);

  const clock = useMutation({
    mutationFn: (direction: "in" | "out") =>
      api(`/v1/attendance/clock-${direction}`, { body: direction === "in" ? { client_time: new Date().toISOString() } : {} }),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["attendance"] }),
    onError: (e) => {
      if (e instanceof ApiError && e.code === "forgot_clock_out") setFixing(true);
      else if (!(e instanceof ApiError && e.code === "already_clocked_in")) void message.error(errorMessage(e));
    },
  });

  if (status.isPending) {
    return (
      <Card>
        <Skeleton active paragraph={{ rows: 2 }} />
      </Card>
    );
  }
  if (status.isError) {
    const noProfile = status.error instanceof ApiError && status.error.code === "no_profile";
    return <Card>{noProfile ? t("home.noProfile") : errorMessage(status.error)}</Card>;
  }

  const data = status.data;
  const open = data.open_record;
  const runningMinutes = open ? Math.max(0, Math.floor((now - new Date(open.clock_in_at).getTime()) / 60_000)) : 0;

  return (
    <Card className="flex flex-col gap-4 sm:flex-row sm:items-center">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <IconTile icon={data.forgot_clock_out ? AlertTriangle : Timer} tone={data.forgot_clock_out ? "amber" : "brand"} />
        <div className="min-w-0">
          <p className="font-semibold text-ink">
            {data.forgot_clock_out && open
              ? t("home.forgot", { time: formatTime(open.clock_in_at, workspace.timezone) })
              : open
                ? t("home.clockedInSince", { time: formatTime(open.clock_in_at, workspace.timezone) })
                : t("home.notClockedIn")}
          </p>
          <p className="text-sm text-slate-500 tabular">
            {t("home.workedToday", { duration: formatDuration(data.today_minutes + (open && !data.forgot_clock_out ? runningMinutes : 0), t) })}
          </p>
        </div>
      </div>
      {data.forgot_clock_out ? (
        <Button size="large" onClick={() => setFixing(true)}>
          {t("home.fixIt")}
        </Button>
      ) : (
        <Button
          type="primary"
          size="large"
          className="min-h-14 sm:min-w-44"
          icon={open ? <LogOut size={18} /> : <LogIn size={18} />}
          loading={clock.isPending}
          onClick={() => clock.mutate(open ? "out" : "in")}
        >
          {open ? t("home.clockOut") : t("home.clockIn")}
        </Button>
      )}
      {fixing && open ? <CorrectionModal record={open} onClose={() => setFixing(false)} /> : null}
    </Card>
  );
}
