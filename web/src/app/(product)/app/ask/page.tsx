"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquarePlus, Newspaper, SendHorizonal, Sparkles, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { AIAnswer, AIBrief, AIConversation, AIMessage } from "@/api/types";
import { useSession } from "@/auth/session";
import { aiKeys, AINotice, aiOpen, AnswerBody, UsageLine, useAIStatus } from "@/components/ai/ai";
import { PageHeader } from "@/components/page";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardHeader, EmptyState } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { PageLoading, Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/cn";
import { errorMessage } from "@/lib/errors";
import { formatDay } from "@/lib/format";

function Bubble({ message }: { message: AIMessage }) {
  const { t } = useTranslation();
  if (message.role === "user") {
    return (
      <li className="flex justify-end">
        <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-accent-soft px-3.5 py-2.5 text-sm text-accent-soft-text">
          <span className="sr-only">{t("ai.you")}: </span>
          {message.text}
        </p>
      </li>
    );
  }
  return (
    <li className="flex gap-3">
      <span className="grid size-8 shrink-0 place-items-center rounded-full bg-accent text-on-accent" aria-hidden="true">
        <Sparkles className="size-4" />
      </span>
      <div className="min-w-0 flex-1 pt-1">
        <span className="sr-only">{t("ai.assistant")}: </span>
        <AnswerBody message={message} />
      </div>
    </li>
  );
}

function Brief() {
  const { t } = useTranslation();
  const [brief, setBrief] = useState<AIBrief | null>(null);
  const queryClient = useQueryClient();
  const write = useMutation({
    mutationFn: () => api<AIBrief>("/v1/ai/brief", { method: "POST" }),
    onSuccess: (b) => {
      setBrief(b);
      void queryClient.invalidateQueries({ queryKey: aiKeys.status });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Card className="pb-5">
      <CardHeader title={t("ai.briefTitle")} sub={brief ? t("ai.briefWeek", { date: formatDay(brief.week_of, { year: undefined }) }) : t("ai.briefSub")} />
      <div className="mt-3 px-5">
        {brief ? (
          <AnswerBody message={brief.message} />
        ) : (
          <Button onClick={() => write.mutate()} loading={write.isPending}>
            <Newspaper aria-hidden="true" />
            {t("ai.briefWrite")}
          </Button>
        )}
      </div>
    </Card>
  );
}

function History({ current, onOpen }: { current: string | null; onOpen: (id: string | null) => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const list = useQuery({ queryKey: aiKeys.conversations, queryFn: () => api<AIConversation[]>("/v1/ai/conversations") });
  const forget = useMutation({
    mutationFn: (id: string) => api(`/v1/ai/conversations/${id}`, { method: "DELETE" }),
    onSuccess: (_, id) => {
      if (id === current) onOpen(null);
      void queryClient.invalidateQueries({ queryKey: aiKeys.conversations });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const items = list.data ?? [];
  return (
    <Card className="pb-5">
      <CardHeader title={t("ai.history")} />
      {items.length === 0 ? (
        <p className="mt-2 px-5 text-sm text-muted">{t("ai.historyEmpty")}</p>
      ) : (
        <ul className="mt-2 flex flex-col px-3">
          {items.map((c) => (
            <li key={c.id} className="group flex items-center gap-1">
              <button
                type="button"
                onClick={() => onOpen(c.id)}
                aria-current={c.id === current ? "true" : undefined}
                className={cn("min-w-0 flex-1 truncate rounded-lg px-2 py-1.5 text-left text-sm hover:bg-surface-2", c.id === current && "bg-surface-2 font-medium")}
              >
                {c.title}
              </button>
              <Button variant="ghost" size="iconSm" aria-label={t("ai.forget", { title: c.title })} onClick={() => forget.mutate(c.id)}>
                <Trash2 aria-hidden="true" />
              </Button>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 px-5 text-xs text-muted">{t("ai.historyPrivate")}</p>
    </Card>
  );
}

function Chat({ id, onStarted }: { id: string | null; onStarted: (id: string) => void }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const detail = useQuery({
    queryKey: aiKeys.conversation(id ?? ""),
    queryFn: () => api<AIConversation>(`/v1/ai/conversations/${id}`),
    enabled: !!id,
  });
  const ask = useMutation({
    mutationFn: (q: string) => api<AIAnswer>("/v1/ai/ask", { method: "POST", body: { question: q, conversation_id: id } }),
    onMutate: (q) => setPending(q),
    onSuccess: (a) => {
      queryClient.setQueryData<AIConversation>(aiKeys.conversation(a.conversation_id), (old) => ({
        id: a.conversation_id,
        title: old?.title ?? a.question.text,
        messages: [...(old?.messages ?? []), a.question, a.answer],
      }));
      setQuestion("");
      if (a.conversation_id !== id) onStarted(a.conversation_id);
      void queryClient.invalidateQueries({ queryKey: aiKeys.conversations });
      void queryClient.invalidateQueries({ queryKey: aiKeys.status });
    },
    onError: (e) => toast.error(errorMessage(e)),
    onSettled: () => setPending(null),
  });
  const messages = id ? (detail.data?.messages ?? []) : [];
  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest" });
  }, [messages.length, pending]);
  const send = (e?: FormEvent) => {
    e?.preventDefault();
    const q = question.trim();
    if (q && !ask.isPending) ask.mutate(q);
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) send(e);
  };
  const suggestions = [t("ai.suggest.leave"), t("ai.suggest.approvals"), t("ai.suggest.tasks"), t("ai.suggest.policy")];
  return (
    <Card className="flex min-h-[28rem] flex-col">
      <div className="flex-1 p-4 sm:p-5" aria-live="polite">
        {id && detail.isPending ? (
          <div className="grid h-full place-items-center">
            <Spinner />
          </div>
        ) : messages.length === 0 && !pending ? (
          <div className="flex flex-col gap-4">
            <p className="text-sm text-muted">{t("ai.empty")}</p>
            <ul className="flex flex-wrap gap-2">
              {suggestions.map((s) => (
                <li key={s}>
                  <Button size="sm" onClick={() => ask.mutate(s)} disabled={ask.isPending}>
                    {s}
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <ol className="flex flex-col gap-5">
            {messages.map((m) => (
              <Bubble key={m.id} message={m} />
            ))}
            {pending && (
              <>
                <Bubble message={{ id: "pending", role: "user", text: pending, sources: [] }} />
                <li className="flex items-center gap-3 text-sm text-muted">
                  <Spinner />
                  {t("ai.thinking")}
                </li>
              </>
            )}
          </ol>
        )}
        <div ref={end} />
      </div>
      <form onSubmit={send} className="flex items-end gap-2 border-t border-border p-3">
        <label htmlFor="ai-question" className="sr-only">
          {t("ai.question")}
        </label>
        <Textarea
          id="ai-question"
          rows={2}
          maxLength={2000}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={onKey}
          placeholder={t("ai.placeholder")}
          className="min-h-11 flex-1 resize-none"
        />
        <Button type="submit" variant="primary" size="icon" aria-label={t("ai.send")} loading={ask.isPending} disabled={!question.trim()}>
          {!ask.isPending && <SendHorizonal aria-hidden="true" />}
        </Button>
      </form>
    </Card>
  );
}

export default function AskPage() {
  const { t } = useTranslation();
  const { can } = useSession();
  const status = useAIStatus();
  const [id, setId] = useState<string | null>(null);
  if (status.isPending) return <PageLoading label={t("app.loading")} />;
  const open = aiOpen(status.data, can);
  if (!status.data?.available) {
    return <EmptyState icon={<Sparkles />} title={t("ai.notSetUp")}>{t("ai.notSetUpBody")}</EmptyState>;
  }
  if (!open.any) {
    return (
      <EmptyState
        icon={<Sparkles />}
        title={t("ai.off")}
        action={
          status.data.can_manage ? (
            <Link href="/app/settings?tab=ai" className={buttonVariants({ variant: "primary" })}>
              {t("ai.openSettings")}
            </Link>
          ) : undefined
        }
      >
        {status.data.can_manage ? t("ai.offManage") : t("ai.offAsk")}
      </EmptyState>
    );
  }
  return (
    <>
      <PageHeader
        title={t("ai.title")}
        sub={t("ai.sub")}
        actions={
          open.ask && id ? (
            <Button onClick={() => setId(null)}>
              <MessageSquarePlus aria-hidden="true" />
              {t("ai.new")}
            </Button>
          ) : undefined
        }
      />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="flex min-w-0 flex-col gap-3">
          {open.ask ? <Chat key={id ?? "new"} id={id} onStarted={setId} /> : <p className="text-sm text-muted">{t("ai.askOff")}</p>}
          <div className="flex flex-col gap-1.5 text-xs text-muted">
            <UsageLine status={status.data} />
            <AINotice />
          </div>
        </div>
        <div className="flex min-w-0 flex-col gap-5">
          {open.brief && <Brief />}
          {open.ask && <History current={id} onOpen={setId} />}
        </div>
      </div>
    </>
  );
}
