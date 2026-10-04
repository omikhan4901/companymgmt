"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Link2, MessageCircle, Plus, Trash2 } from "lucide-react";
import QRCode from "qrcode";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import { useRoles } from "@/api/hooks";
import { useWorkspace } from "@/auth/session";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, EmptyState } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Select } from "@/components/ui/input";
import { errorMessage } from "@/lib/errors";
import { formatDay, formatNumber } from "@/lib/format";

interface JoinLink {
  id: string;
  hint: string;
  label: string | null;
  role_name: string;
  expires_at: string;
  max_uses: number;
  uses: number;
  revoked: boolean;
  token: string | null;
}

function Share({ url, onClose }: { url: string; onClose: () => void }) {
  const { t } = useTranslation();
  const workspace = useWorkspace();
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (canvas.current) void QRCode.toCanvas(canvas.current, url, { margin: 1, width: 240, errorCorrectionLevel: "M" });
  }, [url]);
  const text = t("joinLinks.shareText", { workspace: workspace.name, url });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={t("joinLinks.ready")} description={t("joinLinks.onlyOnce")} closeLabel={t("common.close")}>
        <div className="flex flex-col items-center gap-4">
          <canvas ref={canvas} role="img" aria-label={t("joinLinks.qrAlt")} className="rounded-lg bg-white p-2" />
          <code className="w-full break-all rounded-lg bg-surface-2 p-3 text-xs">{url}</code>
          <div className="flex flex-wrap justify-center gap-2">
            <Button onClick={() => void navigator.clipboard.writeText(url).then(() => toast.success(t("joinLinks.copied")))}>
              <Copy aria-hidden="true" />
              {t("joinLinks.copy")}
            </Button>
            <a
              href={`https://wa.me/?text=${encodeURIComponent(text)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-10 items-center gap-2 rounded-[10px] border border-border px-4 text-sm font-medium hover:bg-surface-2"
            >
              <MessageCircle className="size-4" aria-hidden="true" />
              {t("joinLinks.whatsapp")}
            </a>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function JoinLinks() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const roles = useRoles();
  const links = useQuery({ queryKey: ["join-links"], queryFn: () => api<JoinLink[]>("/v1/join-links") });
  const [roleId, setRoleId] = useState("");
  const [label, setLabel] = useState("");
  const [days, setDays] = useState("7");
  const [uses, setUses] = useState("20");
  const [made, setMade] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: () => api<JoinLink>("/v1/join-links", { method: "POST", body: { role_id: roleId, label: label || null, days: Number(days), max_uses: Number(uses) } }),
    onSuccess: (link) => {
      setMade(`${window.location.origin}/join?token=${encodeURIComponent(link.token ?? "")}`);
      setLabel("");
      void queryClient.invalidateQueries({ queryKey: ["join-links"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const revoke = useMutation({
    mutationFn: (id: string) => api(`/v1/join-links/${id}`, { method: "DELETE" }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["join-links"] }),
    onError: (e) => toast.error(errorMessage(e)),
  });
  const choosable = (roles.data ?? []).filter((r) => r.key !== "owner");
  return (
    <div className="flex flex-col gap-4">
      <p className="max-w-2xl text-sm text-muted">{t("joinLinks.intro")}</p>
      <Card className="grid gap-3 p-4 sm:grid-cols-4 sm:items-end">
        <Field label={t("joinLinks.role")}>
          <Select value={roleId} onChange={(e) => setRoleId(e.target.value)}>
            <option value="">–</option>
            {choosable.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("joinLinks.label")} optional={t("common.optional")}>
          <Input value={label} maxLength={120} onChange={(e) => setLabel(e.target.value)} />
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label={t("joinLinks.days")}>
            <Input type="number" min={1} max={30} value={days} onChange={(e) => setDays(e.target.value)} />
          </Field>
          <Field label={t("joinLinks.uses")}>
            <Input type="number" min={1} max={500} value={uses} onChange={(e) => setUses(e.target.value)} />
          </Field>
        </div>
        <Button variant="primary" disabled={!roleId} loading={create.isPending} onClick={() => create.mutate()}>
          <Plus aria-hidden="true" />
          {t("joinLinks.make")}
        </Button>
      </Card>
      {!links.data?.length ? (
        <EmptyState icon={<Link2 />} title={t("joinLinks.none")} />
      ) : (
        <ul className="flex flex-col gap-2">
          {links.data.map((l) => {
            const expired = new Date(l.expires_at) < new Date();
            return (
              <li key={l.id}>
                <Card className="flex items-center gap-3 px-4 py-3">
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="font-medium">{l.label || `${l.hint}…`}</span>
                    <span className="text-xs text-muted">
                      {l.role_name} · {t("joinLinks.used", { uses: formatNumber(l.uses), max: formatNumber(l.max_uses) })} · {t("joinLinks.until", { date: formatDay(l.expires_at.slice(0, 10)) })}
                    </span>
                  </span>
                  {(l.revoked || expired || l.uses >= l.max_uses) && <Badge>{t(l.revoked ? "joinLinks.revoked" : expired ? "joinLinks.expired" : "joinLinks.usedUp")}</Badge>}
                  {!l.revoked && (
                    <Button variant="ghost" size="iconSm" aria-label={t("joinLinks.revoke")} onClick={() => revoke.mutate(l.id)}>
                      <Trash2 aria-hidden="true" />
                    </Button>
                  )}
                </Card>
              </li>
            );
          })}
        </ul>
      )}
      {made && <Share url={made} onClose={() => setMade(null)} />}
    </div>
  );
}
