import { useQuery } from "@tanstack/react-query";
import { App, Button } from "antd";
import { CheckCircle2, Circle, ClipboardCheck, Clock3, Mail, Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { api } from "@/api/client";
import { useCorrections, useDepartments, usePresent } from "@/api/hooks";
import type { Page, Employee } from "@/api/types";
import { useSession, useWorkspace } from "@/auth/session";
import ClockCard from "@/components/ClockCard";
import { ActionRow, Banner, Card, PageHeader } from "@/components/ui";
import { errorMessage } from "@/lib/errors";
import { formatDay, formatTime } from "@/lib/format";

function Checklist() {
  const { t } = useTranslation();
  const { me, can } = useSession();
  const people = useQuery({
    queryKey: ["people", { limit: 2 }],
    queryFn: () => api<Page<Employee>>("/v1/people", { query: { limit: 2 } }),
    enabled: can("people.view"),
  });
  const departments = useDepartments(can("departments.manage"));
  const records = useQuery({
    queryKey: ["attendance", "records", { limit: 1 }],
    queryFn: () => api<Page<unknown>>("/v1/attendance/records", { query: { limit: 1 } }),
  });
  if (!can("members.invite")) return null;
  const steps = [
    { done: !!me?.email_verified, label: t("home.stepVerify"), to: "/account" },
    { done: (people.data?.items.length ?? 0) > 1, label: t("home.stepPeople"), to: "/team" },
    { done: (departments.data?.length ?? 0) > 0, label: t("home.stepDepartments"), to: "/people?tab=departments" },
    { done: (records.data?.items.length ?? 0) > 0, label: t("home.stepClock"), to: "/" },
  ];
  if (steps.every((s) => s.done)) return null;
  return (
    <Card>
      <h2 className="mb-3 font-display text-lg font-bold text-ink">{t("home.checklist")}</h2>
      <ol className="flex flex-col gap-1">
        {steps.map((s) => (
          <li key={s.label}>
            <Link to={s.to} className="flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-slate-50">
              {s.done ? <CheckCircle2 size={20} className="text-brand" aria-hidden="true" /> : <Circle size={20} className="text-slate-300" aria-hidden="true" />}
              <span className={s.done ? "text-slate-400 line-through" : "text-ink"}>{s.label}</span>
              <span className="sr-only">{s.done ? "✓" : ""}</span>
            </Link>
          </li>
        ))}
      </ol>
    </Card>
  );
}

function WhoIsIn() {
  const { t } = useTranslation();
  const { timezone } = useWorkspace();
  const present = usePresent();
  return (
    <Card>
      <h2 className="mb-3 font-display text-lg font-bold text-ink">{t("home.whoIsIn")}</h2>
      {present.data && present.data.length === 0 ? <p className="text-slate-500">{t("home.nobodyIn")}</p> : null}
      <ul className="divide-y divide-slate-100">
        {(present.data ?? []).map((p) => (
          <li key={p.employee_id} className="flex items-center justify-between gap-3 py-2">
            <span className="truncate text-ink">{p.employee_name}</span>
            <span className="shrink-0 text-sm text-slate-500 tabular">{formatTime(p.clock_in_at, timezone)}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export default function Home() {
  const { t } = useTranslation();
  const { me, can, hasModule } = useSession();
  const workspace = useWorkspace();
  const { message } = App.useApp();
  const attendance = hasModule("attendance");
  const pending = useCorrections("pending", false, attendance && can("attendance.approve"));
  const plan = workspace.plan;

  const resend = async () => {
    try {
      await api("/v1/auth/email/resend", { method: "POST" });
      void message.success(t("home.verifySent"));
    } catch (e) {
      void message.error(errorMessage(e));
    }
  };

  return (
    <>
      <PageHeader title={t("home.greeting", { name: (me?.name ?? "").split(" ")[0] })} sub={t("home.sub", { workspace: workspace.name })} />

      {me?.email && !me.email_verified ? (
        <Banner icon={Mail} tone="amber" action={<Button onClick={() => void resend()}>{t("home.resendVerify")}</Button>}>
          {t("home.stepVerify")}
        </Banner>
      ) : null}

      {plan.status === "trialing" && plan.trial_ends_at && can("workspace.manage") ? (
        <Banner icon={Sparkles} action={<Link to="/settings?tab=plan"><Button>{t("home.seePlans")}</Button></Link>}>
          {t("home.trialEnds", { date: formatDay(plan.trial_ends_at.slice(0, 10)) })}
        </Banner>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <div className="flex flex-col gap-4">
          {attendance && can("attendance.self") ? <ClockCard /> : null}
          {pending.data && pending.data.length > 0 ? (
            <ActionRow to="/attendance?tab=corrections" icon={ClipboardCheck} title={t("home.pending", { count: pending.data.length })} text={t("home.review")} />
          ) : null}
          <Checklist />
        </div>
        <div className="flex flex-col gap-4">
          {attendance && can("attendance.view") ? <WhoIsIn /> : null}
          {attendance && can("attendance.self") ? (
            <ActionRow to="/attendance" icon={Clock3} title={t("attendance.title")} text={t("attendance.sub")} />
          ) : null}
        </div>
      </div>
    </>
  );
}
