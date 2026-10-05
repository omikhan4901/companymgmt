"use client";

import { LifeBuoy, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/page";
import { searchArticles } from "@/components/help/articles";
import { SupportDialog } from "@/components/help/support";
import { Button } from "@/components/ui/button";
import { Card, EmptyState } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { currentLang } from "@/i18n";

export default function HelpPage() {
  const { t } = useTranslation();
  const lang = currentLang() === "bn" ? "bn" : "en";
  const [query, setQuery] = useState("");
  const [contact, setContact] = useState(false);
  const found = searchArticles(query, lang);
  return (
    <>
      <PageHeader
        title={t("help.title")}
        actions={
          <Button onClick={() => setContact(true)}>
            <LifeBuoy aria-hidden="true" />
            {t("support.title")}
          </Button>
        }
      />
      <div className="relative mb-5 max-w-xl">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden="true" />
        <Input className="pl-9" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t("help.search")} aria-label={t("help.search")} />
      </div>
      {found.length ? (
        <div className="grid gap-4 md:grid-cols-2">
          {found.map((a) => (
            <Card key={a.id} className="flex flex-col gap-3 p-5">
              <h2 className="text-base font-semibold">{a[lang].title}</h2>
              <ol className="flex list-decimal flex-col gap-1.5 pl-5 text-sm text-muted">
                {a[lang].steps.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ol>
              {a.href && (
                <Link href={a.href} className="mt-auto self-start text-sm font-semibold text-accent-soft-text hover:underline">
                  {t("help.open")}
                </Link>
              )}
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState icon={<Search />} title={t("help.nothing")} action={<Button onClick={() => setContact(true)}>{t("support.title")}</Button>} />
      )}
      <SupportDialog open={contact} onOpenChange={setContact} />
    </>
  );
}
