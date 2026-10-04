"use client";

import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, Download, FileText, Pencil, Plus, Upload } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api, download } from "@/api/client";
import type { Doc, DocDetail } from "@/api/types";
import { useSession } from "@/auth/session";
import { CATEGORIES, formatSize, uploadVersion, useAcks, useDocument, useLibrary, useRefreshDocs, useToAcknowledge } from "@/components/documents/data";
import { DocumentDialog, fileError } from "@/components/documents/document-dialog";
import { PageHeader } from "@/components/page";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, EmptyState } from "@/components/ui/card";
import { Switch } from "@/components/ui/choice";
import { DocumentSummary } from "@/components/ai/write-help";
import { Dialog, SheetContent } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { intlLocale } from "@/i18n";
import { cn } from "@/lib/cn";
import { errorMessage } from "@/lib/errors";
import { formatAgo, formatNumber } from "@/lib/format";

function useDocParam(): [string | null, (id: string | null) => void] {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const set = useCallback(
    (id: string | null) => {
      const next = new URLSearchParams(params);
      if (id) next.set("doc", id);
      else next.delete("doc");
      const query = next.toString();
      router.push(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [params, router, pathname],
  );
  return [params.get("doc"), set];
}

function AckStatus({ doc }: { doc: Doc }) {
  const { t } = useTranslation();
  if (doc.reach !== null && doc.reach !== undefined) {
    return <span className="text-xs text-muted">{t("docs.ackCount", { done: formatNumber(doc.ack_count ?? 0), total: formatNumber(doc.reach) })}</span>;
  }
  if (doc.acknowledged === false) return <Badge tone="warn">{t("docs.toAcknowledge")}</Badge>;
  if (doc.acknowledged) return <Badge tone="success">{t("docs.acknowledged")}</Badge>;
  return null;
}

function Row({ doc, onOpen }: { doc: Doc; onOpen: (id: string) => void }) {
  const { t } = useTranslation();
  return (
    <li>
      <button type="button" onClick={() => onOpen(doc.id)} className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left hover:bg-surface-2">
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent-soft-text">
          <FileText className="size-5" aria-hidden="true" />
        </span>
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className={cn("truncate text-sm font-semibold", doc.archived && "text-muted")}>{doc.title}</span>
          <span className="truncate text-xs text-muted">
            {doc.current ? `${doc.current.filename} · ${formatSize(doc.current.size, intlLocale())} · ${formatAgo(doc.updated_at)}` : t("docs.noFile")}
          </span>
        </span>
        <AckStatus doc={doc} />
      </button>
    </li>
  );
}

function AcksPanel({ id }: { id: string }) {
  const { t } = useTranslation();
  const acks = useAcks(id);
  if (!acks.data) return null;
  return (
    <section aria-labelledby="acks-title" className="flex flex-col gap-2">
      <h3 id="acks-title" className="text-sm font-semibold">
        {t("docs.ackCount", { done: formatNumber(acks.data.acknowledged), total: formatNumber(acks.data.total) })}
      </h3>
      <ul className="divide-y divide-border rounded-xl border border-border px-3">
        {acks.data.people.map((p) => (
          <li key={p.employee_id} className="flex items-center gap-3 py-2">
            <Avatar name={p.name} className="size-7 text-[10px]" />
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="truncate text-sm">{p.name}</span>
              {p.department && <span className="truncate text-xs text-muted">{p.department}</span>}
            </span>
            {p.acked_at ? <span className="text-xs text-muted">{formatAgo(p.acked_at)}</span> : <Badge tone="warn">{t("news.notYet")}</Badge>}
          </li>
        ))}
      </ul>
    </section>
  );
}

function DocumentBody({ doc }: { doc: DocDetail }) {
  const { t } = useTranslation();
  const refresh = useRefreshDocs();
  const [editing, setEditing] = useState(false);
  const acknowledge = useMutation({
    mutationFn: () => api(`/v1/documents/${doc.id}/acknowledge`, { method: "POST" }),
    onSuccess: () => {
      toast.success(t("docs.thanks"));
      void refresh();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const upload = useMutation({
    mutationFn: (file: File) => uploadVersion(doc.id, file),
    onSuccess: () => {
      toast.success(t("docs.newVersion"));
      void refresh();
    },
    onError: (e) => toast.error(fileError(e, t)),
  });
  const save = (versionId: string, name: string) => download(`/v1/documents/${doc.id}/versions/${versionId}/file`, {}, name).catch((e: unknown) => toast.error(errorMessage(e)));
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-2">
        <Badge>{t(`docs.categories.${doc.category}`)}</Badge>
        <span className="text-xs text-muted">
          {doc.visibility === "everyone" ? t("docs.visibility.everyone") : doc.visibility_names.map((v) => v.name).join(", ")}
        </span>
        {doc.archived && <Badge tone="warn">{t("tasks.archived")}</Badge>}
      </div>
      {doc.description && <p className="whitespace-pre-wrap text-sm leading-relaxed">{doc.description}</p>}
      {doc.current && (
        <Button variant="primary" className="self-start" onClick={() => void save(doc.current!.id, doc.current!.filename)}>
          <Download aria-hidden="true" />
          {t("docs.download", { name: doc.current.filename })}
        </Button>
      )}
      {doc.current && <DocumentSummary key={doc.current.id} documentId={doc.id} />}
      {doc.acknowledged === false && (
        <Card className="flex flex-col gap-3 border-warn-soft bg-warn-soft/40 p-4">
          <p className="text-sm">{t("docs.ackPrompt")}</p>
          <Button variant="primary" className="self-start" loading={acknowledge.isPending} onClick={() => acknowledge.mutate()}>
            <CheckCircle2 aria-hidden="true" />
            {t("docs.ackButton")}
          </Button>
        </Card>
      )}
      {doc.acknowledged && (
        <p className="flex items-center gap-2 text-sm text-success-text">
          <CheckCircle2 className="size-4" aria-hidden="true" />
          {t("docs.youAcknowledged")}
        </p>
      )}
      {doc.can_manage && (
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => setEditing(true)}>
            <Pencil aria-hidden="true" />
            {t("docs.edit")}
          </Button>
          <label className={cn(buttonVariants({ variant: "secondary" }), "cursor-pointer has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-accent", upload.isPending && "pointer-events-none opacity-60")}>
            <Upload aria-hidden="true" />
            {t("docs.uploadVersion")}
            <input
              type="file"
              className="sr-only"
              accept=".pdf,.docx,.xlsx,.pptx,.odt,.png,.jpg,.jpeg,.txt,.md,.csv"
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (file) upload.mutate(file);
              }}
            />
          </label>
        </div>
      )}
      {doc.can_manage && doc.requires_ack && doc.current && <AcksPanel id={doc.id} />}
      {doc.versions.length > 0 && (
        <section aria-labelledby="versions-title" className="flex flex-col gap-2">
          <h3 id="versions-title" className="text-sm font-semibold">
            {t("docs.versions")}
          </h3>
          <ul className="divide-y divide-border rounded-xl border border-border">
            {doc.versions.map((v) => (
              <li key={v.id} className="flex items-center gap-3 px-3 py-2.5">
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-sm font-medium">
                    {t("docs.versionN", { n: formatNumber(v.number) })} · {v.filename}
                  </span>
                  <span className="truncate text-xs text-muted">
                    {formatSize(v.size, intlLocale())} · {formatAgo(v.created_at)}
                    {v.uploaded_by_name && ` · ${v.uploaded_by_name}`}
                  </span>
                </span>
                <Button size="iconSm" variant="ghost" aria-label={t("docs.download", { name: `${v.filename} (${v.number})` })} onClick={() => void save(v.id, v.filename)}>
                  <Download aria-hidden="true" />
                </Button>
              </li>
            ))}
          </ul>
        </section>
      )}
      {editing && <DocumentDialog doc={doc} onClose={() => setEditing(false)} />}
    </div>
  );
}

function DocumentSheet({ id, onClose }: { id: string | null; onClose: () => void }) {
  const { t } = useTranslation();
  const doc = useDocument(id);
  return (
    <Dialog open={!!id} onOpenChange={(o) => !o && onClose()}>
      <SheetContent title={doc.data?.title ?? t("docs.document")} closeLabel={t("common.close")}>
        {doc.isPending ? (
          <div className="grid place-items-center py-16">
            <Spinner />
          </div>
        ) : doc.data ? (
          <DocumentBody doc={doc.data} />
        ) : (
          <p className="text-sm text-muted">{t("docs.notFound")}</p>
        )}
      </SheetContent>
    </Dialog>
  );
}

export default function DocumentsPage() {
  const { t } = useTranslation();
  const { can, hasModule } = useSession();
  const allowed = hasModule("documents") && can("documents.read");
  const manager = can("documents.manage");
  const [archived, setArchived] = useState(false);
  const library = useLibrary(archived, allowed);
  const pending = useToAcknowledge(allowed);
  const [docId, setDoc] = useDocParam();
  const [adding, setAdding] = useState(false);
  if (!allowed) return <EmptyState icon={<FileText />} title={t("common.notAllowed")} />;
  const docs = library.data ?? [];
  return (
    <>
      <PageHeader
        title={t("docs.title")}
        sub={t("docs.sub")}
        actions={
          manager ? (
            <Button variant="primary" onClick={() => setAdding(true)}>
              <Plus aria-hidden="true" />
              {t("docs.new")}
            </Button>
          ) : undefined
        }
      />
      <div className="mx-auto flex max-w-3xl flex-col gap-5">
        {(pending.data ?? []).length > 0 && (
          <Card className="border-warn-soft p-3">
            <h2 className="px-3 pb-1 pt-2 text-sm font-semibold">{t("docs.waitingForYou", { count: pending.data!.length, formatted: formatNumber(pending.data!.length) })}</h2>
            <ul>
              {pending.data!.map((d) => (
                <Row key={d.id} doc={d} onOpen={setDoc} />
              ))}
            </ul>
          </Card>
        )}
        {manager && (
          <label className="flex w-fit items-center gap-3 text-sm">
            <Switch checked={archived} onCheckedChange={setArchived} />
            {t("docs.showArchived")}
          </label>
        )}
        {library.isPending ? (
          <div className="grid place-items-center py-16">
            <Spinner />
          </div>
        ) : docs.length === 0 ? (
          <EmptyState icon={<FileText />} title={t("docs.empty")}>
            {manager ? t("docs.emptyManager") : t("docs.emptyReader")}
          </EmptyState>
        ) : (
          CATEGORIES.map((c) => {
            const group = docs.filter((d) => d.category === c);
            if (!group.length) return null;
            return (
              <Card key={c} className="p-3">
                <h2 className="px-3 pb-1 pt-2 text-xs font-semibold uppercase tracking-wide text-muted">{t(`docs.categoriesPlural.${c}`)}</h2>
                <ul>
                  {group.map((d) => (
                    <Row key={d.id} doc={d} onOpen={setDoc} />
                  ))}
                </ul>
              </Card>
            );
          })
        )}
      </div>
      <DocumentSheet id={docId} onClose={() => setDoc(null)} />
      {adding && <DocumentDialog onClose={() => setAdding(false)} onSaved={setDoc} />}
    </>
  );
}
