"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Megaphone, MoreHorizontal, Pencil, Pin, PinOff, Plus, Trash2 } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { DropdownMenu as M } from "radix-ui";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { Announcement } from "@/api/types";
import { useSession } from "@/auth/session";
import { newsKeys, useFeed, useReceipts, useRefreshNews } from "@/components/announcements/data";
import { PostDialog } from "@/components/announcements/post-dialog";
import { PageHeader } from "@/components/page";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, EmptyState } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { MenuContent, MenuItem } from "@/components/ui/menu";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/cn";
import { errorMessage } from "@/lib/errors";
import { formatAgo, formatNumber } from "@/lib/format";

function ReceiptsDialog({ post, onClose }: { post: Announcement; onClose: () => void }) {
  const { t } = useTranslation();
  const receipts = useReceipts(post.id);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={t("news.receiptsTitle")}
        description={post.title}
        closeLabel={t("common.close")}
      >
        {receipts.isPending ? (
          <div className="grid place-items-center py-10">
            <Spinner />
          </div>
        ) : receipts.data ? (
          <div className="flex flex-col gap-3">
            <p className="text-sm font-medium">{t("news.readBy", { read: formatNumber(receipts.data.read), total: formatNumber(receipts.data.total) })}</p>
            <ul className="divide-y divide-border">
              {receipts.data.people.map((p) => (
                <li key={p.employee_id} className="flex items-center gap-3 py-2">
                  <Avatar name={p.name} className="size-8 text-[11px]" />
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate text-sm font-medium">{p.name}</span>
                    {p.department && <span className="truncate text-xs text-muted">{p.department}</span>}
                  </span>
                  {p.read_at ? <span className="text-xs text-muted">{formatAgo(p.read_at)}</span> : <Badge tone="warn">{t("news.notYet")}</Badge>}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function PostCard({ post, highlight, onEdit }: { post: Announcement; highlight: boolean; onEdit: () => void }) {
  const { t } = useTranslation();
  const refresh = useRefreshNews();
  const ref = useRef<HTMLElement>(null);
  const [receipts, setReceipts] = useState(false);
  const [deleting, setDeleting] = useState(false);
  useEffect(() => {
    if (highlight) ref.current?.scrollIntoView({ block: "center" });
  }, [highlight]);
  const change = useMutation({
    mutationFn: (fn: () => Promise<unknown>) => fn(),
    onSuccess: () => void refresh(),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const audience =
    post.audience === "everyone" ? t("news.audiences.everyone") : post.audience_names.map((a) => a.name).join(", ");
  return (
    <Card className={cn("p-5", highlight && "ring-2 ring-accent")}>
      <article ref={ref} aria-labelledby={`post-${post.id}`} className="flex flex-col gap-3">
        <header className="flex items-start gap-3">
          <Avatar name={post.author_name ?? "?"} className="size-9" />
          <div className="flex min-w-0 flex-1 flex-col gap-0.5">
            <h2 id={`post-${post.id}`} className="flex flex-wrap items-center gap-2 text-base font-semibold">
              {post.title}
              {post.pinned && (
                <Badge tone="accent">
                  <Pin className="size-3" aria-hidden="true" />
                  {t("news.pinned")}
                </Badge>
              )}
              {!post.read && <Badge tone="accent">{t("news.new")}</Badge>}
            </h2>
            <p className="text-xs text-muted">
              {post.author_name ?? t("notifications.someone")} · {formatAgo(post.published_at)}
              {post.edited_at && ` · ${t("news.edited")}`} · {t("news.to", { audience })}
            </p>
          </div>
          {post.can_edit && (
            <M.Root>
              <M.Trigger className="grid size-8 place-items-center rounded-lg text-muted hover:bg-surface-2 hover:text-text" aria-label={t("news.actions", { title: post.title })}>
                <MoreHorizontal className="size-4" aria-hidden="true" />
              </M.Trigger>
              <MenuContent>
                <MenuItem onSelect={onEdit}>
                  <Pencil aria-hidden="true" />
                  {t("news.editPost")}
                </MenuItem>
                <MenuItem onSelect={() => change.mutate(() => api(`/v1/announcements/${post.id}`, { method: "PATCH", body: { pinned: !post.pinned }, version: post.version }))}>
                  {post.pinned ? <PinOff aria-hidden="true" /> : <Pin aria-hidden="true" />}
                  {post.pinned ? t("news.unpin") : t("news.pin")}
                </MenuItem>
                <MenuItem onSelect={() => setDeleting(true)} className="text-danger [&_svg]:text-danger">
                  <Trash2 aria-hidden="true" />
                  {t("news.delete")}
                </MenuItem>
              </MenuContent>
            </M.Root>
          )}
        </header>
        <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">{post.body}</p>
        {post.reach !== null && post.reach !== undefined && (
          <div>
            <Button size="sm" variant="ghost" className="px-2 text-muted" onClick={() => setReceipts(true)}>
              {t("news.readBy", { read: formatNumber(post.read_count ?? 0), total: formatNumber(post.reach) })}
            </Button>
          </div>
        )}
      </article>
      {receipts && <ReceiptsDialog post={post} onClose={() => setReceipts(false)} />}
      <ConfirmDialog
        open={deleting}
        onClose={() => setDeleting(false)}
        title={t("news.deleteTitle", { title: post.title })}
        confirmLabel={t("news.delete")}
        busy={change.isPending}
        onConfirm={() => change.mutate(() => api(`/v1/announcements/${post.id}`, { method: "DELETE" }), { onSuccess: () => setDeleting(false) })}
      >
        <p className="text-sm text-muted">{t("news.deleteBody")}</p>
      </ConfirmDialog>
    </Card>
  );
}

export default function AnnouncementsPage() {
  const { t } = useTranslation();
  const { can, hasModule } = useSession();
  const params = useSearchParams();
  const queryClient = useQueryClient();
  const allowed = hasModule("announcements") && can("announcements.read");
  const feed = useFeed(allowed);
  const [writing, setWriting] = useState(false);
  const [editing, setEditing] = useState<Announcement | null>(null);
  const focus = params.get("post");

  // Posts shown here count as read.
  useEffect(() => {
    const unread = (feed.data ?? []).filter((p) => !p.read);
    if (!unread.length) return;
    void Promise.all(unread.map((p) => api(`/v1/announcements/${p.id}/read`, { method: "POST" }).catch(() => undefined))).then(() =>
      queryClient.invalidateQueries({ queryKey: newsKeys.unread }),
    );
  }, [feed.data, queryClient]);

  if (!allowed) return <EmptyState icon={<Megaphone />} title={t("common.notAllowed")} />;
  return (
    <>
      <PageHeader
        title={t("news.title")}
        sub={t("news.sub")}
        actions={
          can("announcements.post") ? (
            <Button variant="primary" onClick={() => setWriting(true)}>
              <Plus aria-hidden="true" />
              {t("news.newPost")}
            </Button>
          ) : undefined
        }
      />
      {feed.isPending ? (
        <div className="grid place-items-center py-16">
          <Spinner />
        </div>
      ) : feed.data?.length ? (
        <div className="mx-auto flex max-w-3xl flex-col gap-4">
          {feed.data.map((post) => (
            <PostCard key={post.id} post={post} highlight={post.id === focus} onEdit={() => setEditing(post)} />
          ))}
        </div>
      ) : (
        <EmptyState icon={<Megaphone />} title={t("news.empty")}>
          {can("announcements.post") ? t("news.emptyPoster") : t("news.emptyReader")}
        </EmptyState>
      )}
      {writing && <PostDialog onClose={() => setWriting(false)} />}
      {editing && <PostDialog post={editing} onClose={() => setEditing(null)} />}
    </>
  );
}
