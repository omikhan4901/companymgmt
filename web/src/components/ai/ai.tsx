"use client";

import { useQuery } from "@tanstack/react-query";
import { BookOpen } from "lucide-react";
import Link from "next/link";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { AIMessage, AIStatus } from "@/api/types";
import { useSession } from "@/auth/session";
import { formatDay, formatNumber } from "@/lib/format";

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
