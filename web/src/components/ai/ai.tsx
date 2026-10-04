"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Check, X } from "lucide-react";
import { useState } from "react";
import Link from "next/link";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { AIAction, AIMessage, AIStatus } from "@/api/types";
import { useSession } from "@/auth/session";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { errorMessage } from "@/lib/errors";
import { formatDay, formatNumber } from "@/lib/format";
import { toast } from "sonner";

export const aiKeys = {
  status: ["ai", "status"] as const,
  conversations: ["ai", "conversations"] as const,
  conversation: (id: string) => ["ai", "conversations", id] as const,
};

/** What the assistant can do here: set up on the server, switched on, this person's allowance. */
export function useAIStatus() {
  const { signedIn, workspace } = useSession();
  return useQuery({
    queryKey: aiKeys.status,
    queryFn: () => api<AIStatus>("/v1/ai/status"),
    enabled: signedIn && !!workspace,
    staleTime: 60_000,
  });
}

/** An answer: the model's words, then numbered links to where each fact came from. */
export function AnswerBody({ message }: { message: AIMessage }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-3">
      <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.text}</p>
      {(message.actions ?? []).map((a) => (
        <ActionCard key={a.id} action={a} />
      ))}
      {message.sources.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-muted">{t("ai.sources")}</span>
          <ul className="flex flex-wrap gap-1.5">
            {message.sources.map((s) => (
              <li key={s.n}>
                {s.link ? (
                  <Link
                    href={s.link}
                    className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-1 text-xs hover:border-border-strong"
                  >
                    <span className="font-semibold tabular-nums">[{formatNumber(s.n)}]</span>
                    <span className="max-w-60 truncate">{s.label}</span>
                  </Link>
                ) : (
                  <span className="inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-xs">
                    <span className="font-semibold tabular-nums">[{formatNumber(s.n)}]</span>
                    <span className="max-w-60 truncate">{s.label}</span>
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/** "12 of 500 questions this month", or nothing when the plan has no limit. */
export function UsageLine({ status }: { status: AIStatus }) {
  const { t } = useTranslation();
  if (status.allowance === null) return <span>{t("ai.usageUnlimited", { used: formatNumber(status.used) })}</span>;
  return (
    <span>
      {t("ai.usage", { used: formatNumber(status.used), allowance: formatNumber(status.allowance) })}{" "}
      {t("ai.resets", { date: formatDay(status.resets_on, { year: undefined }) })}
    </span>
  );
}

export function AINotice() {
  const { t } = useTranslation();
  return (
    <p className="flex items-start gap-2 text-xs text-muted">
      <BookOpen className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
      {t("ai.notice")}
    </p>
  );
}

/** Which assistant features this person can open right now. */
export function aiOpen(status: AIStatus | undefined, can: (permission: string) => boolean) {
  const on = !!status && status.available && status.enabled && status.can_use;
  const ask = on && status.features.includes("ask");
  const brief = on && status.features.includes("brief") && can("reports.view");
  return { ask, brief, any: ask || brief };
}

const TONES: Record<string, "accent" | "success" | "warn" | "danger" | undefined> = {
  pending: "accent",
  done: "success",
  failed: "danger",
  expired: "warn",
};

/** Something the assistant offered to do. Nothing happens until the person confirms. */
export function ActionCard({ action: initial }: { action: AIAction }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [action, setAction] = useState(initial);
  const decide = useMutation({
    mutationFn: (what: "confirm" | "cancel") => api<AIAction>(`/v1/ai/actions/${action.id}/${what}`, { method: "POST" }),
    onSuccess: (a) => {
      setAction(a);
      if (a.status === "done") toast.success(t("ai.actionDone"));
      void queryClient.invalidateQueries();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const value = (f: AIAction["fields"][number]) => {
    if (f.kind === "date") return formatDay(f.value);
    if (f.kind === "flag") return t("common.yes");
    if (f.field === "decision" || f.field === "priority" || f.field === "status") return t(`ai.values.${f.value}`, { defaultValue: f.value });
    return f.value;
  };
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface-2/60 p-3.5" role="group" aria-label={action.label}>
      <div className="flex items-start gap-2">
        <span className="min-w-0 flex-1 text-sm font-medium">{t(`ai.capabilities.${action.capability}`, { defaultValue: action.label })}</span>
        <Badge tone={TONES[action.status]}>{t(`ai.actionStatus.${action.status}`)}</Badge>
      </div>
      {action.fields.length > 0 && (
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
          {action.fields.map((f) => (
            <div key={f.field} className="contents">
              <dt className="text-muted">{t(`ai.fields.${f.field}`, { defaultValue: f.field })}</dt>
              <dd className="min-w-0 whitespace-pre-wrap break-words">{value(f)}</dd>
            </div>
          ))}
        </dl>
      )}
      {action.status === "failed" && action.error && <p className="text-sm text-danger-text">{action.error}</p>}
      {action.status === "pending" && (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="primary" loading={decide.isPending && decide.variables === "confirm"} disabled={decide.isPending} onClick={() => decide.mutate("confirm")}>
            <Check aria-hidden="true" />
            {t("ai.confirm")}
          </Button>
          <Button size="sm" disabled={decide.isPending} onClick={() => decide.mutate("cancel")}>
            <X aria-hidden="true" />
            {t("common.cancel")}
          </Button>
        </div>
      )}
      {action.status === "done" && action.link && (
        <Link href={action.link} className="text-sm font-semibold text-accent-soft-text underline-offset-4 hover:underline">
          {t("ai.openResult")}
        </Link>
      )}
    </div>
  );
}
