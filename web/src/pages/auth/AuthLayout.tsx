import { Languages } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import Logo from "@/components/Logo";
import { currentLang, setLanguage } from "@/i18n";

export default function AuthLayout({ title, sub, children, footer }: { title: string; sub?: string; children: ReactNode; footer?: ReactNode }) {
  const { t } = useTranslation();
  return (
    <div className="relative min-h-screen overflow-hidden bg-gradient-to-b from-brand-50 via-white to-white">
      <div className="bg-grid absolute inset-0 [mask-image:radial-gradient(ellipse_at_top,black_30%,transparent_70%)]" aria-hidden="true" />
      <div className="relative mx-auto flex min-h-screen max-w-md flex-col px-4 py-6">
        <header className="flex items-center justify-between">
          <Logo to="/login" />
          <button
            type="button"
            onClick={() => setLanguage(currentLang() === "bn" ? "en" : "bn")}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium text-slate-600 hover:bg-white"
          >
            <Languages size={16} aria-hidden="true" />
            {t("nav.language")}
          </button>
        </header>
        <main className="flex flex-1 flex-col justify-center py-8">
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm md:p-8">
            <h1 className="font-display text-2xl font-bold text-ink">{title}</h1>
            {sub ? <p className="mt-1 text-slate-500">{sub}</p> : null}
            <div className="mt-6">{children}</div>
          </div>
          {footer ? <div className="mt-6 text-center text-sm text-slate-600">{footer}</div> : null}
        </main>
      </div>
    </div>
  );
}
