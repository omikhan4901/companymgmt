"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Globe } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api } from "@/api/client";
import type { Workspace } from "@/api/types";
import { useSession } from "@/auth/session";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { addressFor, WORKSPACE_DOMAIN } from "@/lib/address";
import { errorMessage } from "@/lib/errors";

/** The workspace's own address, which is also the code staff sign in with. */
export function AddressCard() {
  const { t } = useTranslation();
  const { workspace, reload } = useSession();
  const queryClient = useQueryClient();
  const current = useQuery({ queryKey: ["workspace"], queryFn: () => api<Workspace>("/v1/workspace") });
  const [slug, setSlug] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => api("/v1/workspace/address", { method: "PUT", body: { slug: (slug ?? "").trim().toLowerCase() } }),
    onSuccess: async () => {
      toast.success(t("address.changed"));
      setSlug(null);
      await queryClient.invalidateQueries({ queryKey: ["workspace"] });
      await reload();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (!current.data) return null;
  const owner = workspace?.role_key === "owner";
  return (
    <Card className="mt-5 flex max-w-2xl flex-col gap-3 p-5">
      <p className="flex items-center gap-2 font-semibold">
        <Globe className="size-4" aria-hidden="true" />
        {t("address.title")}
      </p>
      <p className="text-sm">
        <a href={addressFor(current.data.slug)} className="font-medium underline-offset-4 hover:underline">
          {addressFor(current.data.slug).replace("https://", "")}
        </a>
      </p>
      <p className="text-sm text-muted">{t("address.help", { code: current.data.slug })}</p>
      {owner && (
        <div className="flex flex-wrap items-end gap-2">
          <Field label={t("address.new")} help={t("address.rules", { domain: WORKSPACE_DOMAIN })} className="w-72">
            <Input value={slug ?? current.data.slug} maxLength={40} autoCapitalize="none" onChange={(e) => setSlug(e.target.value)} />
          </Field>
          <Button disabled={!slug || slug === current.data.slug} loading={save.isPending} onClick={() => save.mutate()}>
            {t("address.save")}
          </Button>
        </div>
      )}
    </Card>
  );
}
