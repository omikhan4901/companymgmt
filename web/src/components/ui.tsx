/** Small building blocks in the ResumeX style: page headers, cards, icon tiles, pills. */
import type { LucideIcon } from "lucide-react";
import { ArrowRight } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";

export function PageHeader({ title, sub, actions }: { title: string; sub?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="font-display text-2xl font-bold text-ink md:text-3xl">{title}</h1>
        {sub ? <p className="mt-1 text-slate-500">{sub}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-2xl border border-slate-200 bg-white p-4 md:p-5 ${className}`}>{children}</section>;
}

export function IconTile({ icon: Icon, tone = "brand" }: { icon: LucideIcon; tone?: "brand" | "amber" | "slate" }) {
  const tones = {
    brand: "bg-brand-50 text-brand",
    amber: "bg-amber-100 text-amber-800",
    slate: "bg-slate-100 text-slate-600",
  };
  return (
    <span className={`grid size-10 shrink-0 place-items-center rounded-xl ${tones[tone]}`} aria-hidden="true">
      <Icon size={18} />
    </span>
  );
}

export function ActionRow({ to, icon, title, text, onClick }: { to?: string; icon: LucideIcon; title: string; text?: string; onClick?: () => void }) {
  const body = (
    <>
      <IconTile icon={icon} />
      <span className="min-w-0 flex-1 text-left">
        <span className="block font-semibold text-ink">{title}</span>
        {text ? <span className="block text-sm text-slate-500">{text}</span> : null}
      </span>
      <ArrowRight size={16} className="shrink-0 text-slate-400 transition group-hover:translate-x-0.5 group-hover:text-brand" aria-hidden="true" />
    </>
  );
  const cls = "group flex w-full items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 transition hover:border-brand";
  if (to) {
    return (
      <Link to={to} className={cls}>
        {body}
      </Link>
    );
  }
  return (
    <button type="button" onClick={onClick} className={cls}>
      {body}
    </button>
  );
}

export function Banner({ tone = "brand", icon, children, action }: { tone?: "brand" | "amber"; icon: LucideIcon; children: ReactNode; action?: ReactNode }) {
  const tones = { brand: "border-brand-200 bg-brand-50 text-ink", amber: "border-amber-200 bg-amber-50 text-amber-950" };
  return (
    <div className={`mb-4 flex flex-wrap items-center gap-3 rounded-2xl border px-4 py-3 ${tones[tone]}`} role="status">
      <IconTile icon={icon} tone={tone === "amber" ? "amber" : "brand"} />
      <div className="min-w-0 flex-1 text-sm">{children}</div>
      {action}
    </div>
  );
}

export function Pill({ children, tone = "slate" }: { children: ReactNode; tone?: "slate" | "brand" | "amber" | "red" | "green" }) {
  const tones = {
    slate: "bg-slate-100 text-slate-700",
    brand: "bg-brand-50 text-brand-dark",
    amber: "bg-amber-100 text-amber-900",
    red: "bg-red-50 text-red-700",
    green: "bg-emerald-50 text-emerald-800",
  };
  return <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${tones[tone]}`}>{children}</span>;
}

export function EmptyState({ icon: Icon, title, action }: { icon: LucideIcon; title: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-slate-200 bg-white/60 px-6 py-12 text-center">
      <span className="grid size-12 place-items-center rounded-full bg-slate-100 text-slate-500" aria-hidden="true">
        <Icon size={22} />
      </span>
      <p className="max-w-sm text-slate-600">{title}</p>
      {action}
    </div>
  );
}
