"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, Download, FileSpreadsheet } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { api, download } from "@/api/client";
import type { ImportResult } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Table, Td, Th } from "@/components/ui/table";
import { errorMessage } from "@/lib/errors";
import { formatNumber } from "@/lib/format";

const FIELDS = ["full_name", "preferred_name", "employee_code", "email", "phone", "job_title", "employment_type", "joined_on", "date_of_birth", "department", "branch"];

function send(file: File, commit: boolean) {
  return api<ImportResult>("/v1/people/import", { query: { commit }, rawBody: new Blob([file], { type: "text/csv" }) });
}

/** Choose a CSV, see what it would do (and what's wrong with it), then import it. */
export function ImportDialog({ onClose }: { onClose: () => void }) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const label = (field: string) => (FIELDS.includes(field) ? t(`importer.fields.${field}`) : field);

  const check = useMutation({
    mutationFn: (f: File) => send(f, false),
    onSuccess: setResult,
    onError: (e) => {
      setResult(null);
      toast.error(errorMessage(e));
    },
  });
  const save = useMutation({
    mutationFn: (f: File) => send(f, true),
    onSuccess: (done) => {
      toast.success(t("importer.done", { created: formatNumber(done.create), updated: formatNumber(done.update) }));
      void queryClient.invalidateQueries({ queryKey: ["people"] });
      void queryClient.invalidateQueries({ queryKey: ["departments"] });
      void queryClient.invalidateQueries({ queryKey: ["leave"] });
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const pick = (f: File | null) => {
    setFile(f);
    setResult(null);
    if (f) check.mutate(f);
  };
  const problems = result?.rows.filter((r) => r.action === "error") ?? [];
  const changes = result?.rows.filter((r) => r.action === "create" || r.action === "update") ?? [];
  const ignored = result?.columns.filter((c) => c.field === null).map((c) => c.header) ?? [];
  const todo = (result?.create ?? 0) + (result?.update ?? 0);

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={t("importer.title")}
        description={t("importer.sub")}
        closeLabel={t("common.close")}
        className="sm:w-[min(760px,calc(100vw-32px))]"
        footer={
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="primary" disabled={!file || !result || result.errors > 0 || todo === 0} loading={save.isPending} onClick={() => file && save.mutate(file)}>
              {t("importer.import", { count: todo, formatted: formatNumber(todo) })}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-5">
          <ol className="flex flex-col gap-1.5 text-sm text-muted">
            <li>{t("importer.step1")}</li>
            <li>{t("importer.step2")}</li>
            <li>{t("importer.step3")}</li>
          </ol>
          <div className="flex flex-wrap items-end gap-3">
            <Button onClick={() => void download("/v1/people/import/template", { lang: i18n.language === "bn" ? "bn" : "en" }, "people-import.csv")}>
              <Download aria-hidden="true" />
              {t("importer.template")}
            </Button>
            <Field label={t("importer.file")} className="min-w-0 flex-1">
              <Input type="file" accept=".csv,text/csv" onChange={(e) => pick(e.target.files?.[0] ?? null)} />
            </Field>
          </div>

          {check.isPending && <p className="text-sm text-muted">{t("importer.checking")}</p>}
          {result && (
            <section aria-label={t("importer.summary")} className="flex flex-col gap-4">
              <div className="flex flex-wrap gap-2" role="status">
                <Badge tone="accent">{t("importer.creates", { count: result.create, formatted: formatNumber(result.create) })}</Badge>
                <Badge tone="neutral">{t("importer.updates", { count: result.update, formatted: formatNumber(result.update) })}</Badge>
                {result.unchanged > 0 && <Badge tone="neutral">{t("importer.unchanged", { count: result.unchanged, formatted: formatNumber(result.unchanged) })}</Badge>}
                {result.errors > 0 && <Badge tone="danger">{t("importer.problems", { count: result.errors, formatted: formatNumber(result.errors) })}</Badge>}
              </div>
              {result.errors > 0 ? (
                <p className="flex items-start gap-2 text-sm text-danger-text">
                  <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                  {t("importer.fixFirst")}
                </p>
              ) : (
                todo > 0 && (
                  <p className="flex items-start gap-2 text-sm text-success-text">
                    <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                    {t("importer.ready")}
                  </p>
                )
              )}
              {result.new_departments.length > 0 && (
                <p className="text-sm">
                  <span className="font-medium">{t("importer.newDepartments")}</span> {result.new_departments.join(", ")}
                </p>
              )}
              {ignored.length > 0 && (
                <p className="text-sm text-muted">
                  {t("importer.ignored")} {ignored.join(", ")}
                </p>
              )}
              {problems.length > 0 && (
                <Table label={t("importer.problemsTable")}>
                  <thead>
                    <tr>
                      <Th>{t("importer.line")}</Th>
                      <Th>{t("importer.person")}</Th>
                      <Th>{t("importer.whatsWrong")}</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {problems.map((r) => (
                      <tr key={r.line}>
                        <Td className="tabular-nums">{formatNumber(r.line)}</Td>
                        <Td>{r.name || "—"}</Td>
                        <Td>
                          <ul className="flex flex-col gap-1">
                            {r.errors.map((e, i) => (
                              <li key={i}>
                                <span className="font-medium">{e.column}:</span> {e.message}
                              </li>
                            ))}
                          </ul>
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )}
              {problems.length === 0 && changes.length > 0 && (
                <Table label={t("importer.changesTable")}>
                  <thead>
                    <tr>
                      <Th>{t("importer.line")}</Th>
                      <Th>{t("importer.person")}</Th>
                      <Th>{t("importer.what")}</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {changes.slice(0, 100).map((r) => (
                      <tr key={r.line}>
                        <Td className="tabular-nums">{formatNumber(r.line)}</Td>
                        <Td>
                          <span className="inline-flex items-center gap-2">
                            <FileSpreadsheet className="size-4 text-muted" aria-hidden="true" />
                            {r.name}
                          </span>
                        </Td>
                        <Td className="text-muted">{r.action === "create" ? t("importer.new") : t("importer.changes", { fields: r.changes.map(label).join(", ") })}</Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )}
            </section>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
