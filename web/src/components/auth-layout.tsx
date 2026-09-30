"use client";

import { CalendarCheck2, MapPin, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { Logo, LogoMark } from "./logo";
import { AppearanceMenu, LanguageButton } from "./prefs";

/** Sign-in pages: a form on the right, the product in a sentence on the left (desktop). */
export function AuthLayout({ title, sub, children, footer }: { title: string; sub?: string; children: ReactNode; footer?: ReactNode }) {
  const { t } = useTranslation();
  const points = [
    { icon: MapPin, text: t("authPanel.location") },
    { icon: CalendarCheck2, text: t("authPanel.leave") },
    { icon: ShieldCheck, text: t("authPanel.secure") },
  ];
  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-accent p-10 text-on-accent lg:flex">
        <div className="flex items-center gap-2.5">
          <LogoMark className="text-on-accent [&_rect:first-child]:fill-[color-mix(in_oklab,var(--on-accent)_18%,transparent)]" size={34} />
          <span className="font-display text-lg font-bold">CompanyMgmt</span>
        </div>
        <div className="flex max-w-md flex-col gap-8">
          <p className="font-display text-4xl font-semibold leading-tight tracking-tight">{t("authPanel.headline")}</p>
          <ul className="flex flex-col gap-4">
            {points.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-start gap-3 text-[15px]">
                <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-[color-mix(in_oklab,var(--on-accent)_16%,transparent)]">
                  <Icon className="size-[18px]" aria-hidden="true" />
                </span>
                <span className="pt-1.5">{text}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="text-sm opacity-80">{t("authPanel.footer")}</p>
      </aside>

      <div className="flex min-h-dvh flex-col px-4 py-5 sm:px-8">
        <header className="flex items-center justify-between gap-2">
          <Logo href="/" className="lg:invisible" />
          <div className="flex items-center gap-1">
            <LanguageButton />
            <AppearanceMenu />
          </div>
        </header>
        <main id="main" className="mx-auto flex w-full max-w-[420px] flex-1 flex-col justify-center py-10">
          <h1 className="text-[28px] font-semibold leading-tight">{title}</h1>
          {sub && <p className="mt-1.5 text-muted">{sub}</p>}
          <div className="mt-7">{children}</div>
          {footer && <div className="mt-8 text-sm text-muted">{footer}</div>}
        </main>
      </div>
    </div>
  );
}
