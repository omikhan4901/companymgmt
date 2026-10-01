"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { Popover as P } from "radix-ui";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { Inbox, Notification } from "@/api/types";
import { useWorkspace } from "@/auth/session";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/cn";
import { formatAgo, formatDay, formatNumber } from "@/lib/format";

const unreadKey = ["notifications", "unread"] as const;
const inboxKey = ["notifications", "inbox"] as const;

function dates(data: Record<string, unknown>): string {
  const start = typeof data.start_date === "string" ? data.start_date : null;
  const end = typeof data.end_date === "string" ? data.end_date : null;
  if (!start) return "";
  if (!end || end === start) return formatDay(start, { weekday: "short", year: undefined });
  return `${formatDay(start, { year: undefined })} – ${formatDay(end, { year: undefined })}`;
}

function month(data: Record<string, unknown>): string {
  return typeof data.period === "string" ? formatDay(`${data.period}-01`, { day: undefined, month: "long" }) : "";
}

/** The sentence for one notification, worded from its event and data. */
export function useDescribe() {
  const { t } = useTranslation();
  const workspace = useWorkspace();
  return (n: Notification): string => {
    const data = n.data as Record<string, unknown>;
    const values = {
      actor: n.actor_name ?? t("notifications.someone"),
      name: typeof data.employee_name === "string" ? data.employee_name : t("notifications.someone"),
      type: typeof data.type === "string" ? data.type : "",
      dates: dates(data),
      period: month(data),
      title: typeof data.title === "string" ? data.title : "",
      project: typeof data.project_name === "string" ? data.project_name : "",
    };
    let key = n.kind.replace(".", "_");
    if (n.kind === "leave.cancelled") {
      key = data.membership_id === workspace.membership_id ? "leave_cancelled_yours" : "leave_withdrawn";
    }
    return t(`notifications.kinds.${key}`, { ...values, defaultValue: t("notifications.kinds.other") });
  };
}

function Item({ n, onOpen }: { n: Notification; onOpen: (n: Notification) => void }) {
  const { t } = useTranslation();
  const describe = useDescribe();
  const unread = !n.read_at;
  return (
    <li>
      <button
        type="button"
        onClick={() => onOpen(n)}
        className={cn("flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left hover:bg-surface-2", unread && "bg-accent-soft/40")}
      >
        <span aria-hidden="true" className={cn("mt-1.5 size-2 shrink-0 rounded-full", unread ? "bg-accent" : "bg-transparent")} />
        <span className="min-w-0 flex-1">
          <span className={cn("block text-sm", unread ? "font-semibold" : "text-text")}>{describe(n)}</span>
          <span className="block text-xs text-muted">{formatAgo(n.created_at)}</span>
        </span>
        {unread && <span className="sr-only">{t("notifications.unread")}</span>}
      </button>
    </li>
  );
}

export function NotificationBell() {
  const { t } = useTranslation();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const unread = useQuery({
    queryKey: unreadKey,
    queryFn: () => api<{ unread: number }>("/v1/notifications/unread"),
    refetchInterval: 60_000,
  });
  const inbox = useInfiniteQuery({
    queryKey: inboxKey,
    queryFn: ({ pageParam }) => api<Inbox>("/v1/notifications", { query: pageParam ? { cursor: pageParam } : {} }),
    initialPageParam: "",
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled: open,
  });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["notifications"] });
  };
  const markAll = useMutation({
    mutationFn: () => api("/v1/notifications/read-all", { method: "POST" }),
    onSuccess: refresh,
  });
  const openOne = async (n: Notification) => {
    setOpen(false);
    if (!n.read_at) {
      await api(`/v1/notifications/${n.id}/read`, { method: "POST" }).catch(() => undefined);
      refresh();
    }
    if (n.link) router.push(n.link);
  };
  const count = unread.data?.unread ?? 0;
  const items = inbox.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <P.Root
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (o) refresh();
      }}
    >
      <P.Trigger
        className="relative grid size-10 place-items-center rounded-[10px] text-muted hover:bg-surface-2 hover:text-text"
        aria-label={count ? t("notifications.openUnread", { count, formatted: formatNumber(count) }) : t("notifications.title")}
      >
        <Bell className="size-5" aria-hidden="true" />
        {count > 0 && (
          <span aria-hidden="true" className="absolute right-1 top-1 grid min-w-[18px] place-items-center rounded-full bg-accent px-1 text-[10px] font-bold leading-[18px] text-on-accent">
            {count > 99 ? "99+" : formatNumber(count)}
          </span>
        )}
      </P.Trigger>
      <P.Portal>
        <P.Content
          align="end"
          sideOffset={8}
          collisionPadding={12}
          className="z-50 flex max-h-[min(560px,80dvh)] w-[min(400px,calc(100vw-24px))] flex-col rounded-xl border border-border bg-surface text-text shadow-xl"
        >
          <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold">{t("notifications.title")}</h2>
            {count > 0 && (
              <Button size="sm" variant="ghost" loading={markAll.isPending} onClick={() => markAll.mutate()}>
                <CheckCheck aria-hidden="true" />
                {t("notifications.markAll")}
              </Button>
            )}
          </div>
          <div className="overflow-y-auto p-1.5">
            {inbox.isPending ? (
              <div className="grid place-items-center py-10">
                <Spinner />
              </div>
            ) : items.length === 0 ? (
              <div className="px-4 py-10 text-center">
                <p className="text-sm font-semibold">{t("notifications.empty")}</p>
                <p className="mt-1 text-sm text-muted">{t("notifications.emptyBody")}</p>
              </div>
            ) : (
              <ul aria-label={t("notifications.title")}>
                {items.map((n) => (
                  <Item key={n.id} n={n} onOpen={(x) => void openOne(x)} />
                ))}
              </ul>
            )}
            {inbox.hasNextPage && (
              <div className="p-2">
                <Button size="sm" variant="secondary" className="w-full" loading={inbox.isFetchingNextPage} onClick={() => void inbox.fetchNextPage()}>
                  {t("notifications.more")}
                </Button>
              </div>
            )}
          </div>
        </P.Content>
      </P.Portal>
    </P.Root>
  );
}
