import Link from "next/link";

import { Logo } from "./logo";

const NAV = [
  { href: "/#features", label: "Features" },
  { href: "/#how", label: "How it works" },
  { href: "/pricing", label: "Pricing" },
  { href: "/developers", label: "Developers" },
  { href: "/security", label: "Security" },
];

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/90 backdrop-blur-md">
      <nav className="mx-auto flex h-16 max-w-[1200px] items-center justify-between gap-4 px-5 md:px-8" aria-label="Main">
        <Logo className="[&_span]:font-site-display" />
        <div className="hidden items-center gap-1 md:flex">
          {NAV.map((l) => (
            <Link key={l.href} href={l.href} className="rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-brand-50 hover:text-ink">
              {l.label}
            </Link>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          <Link href="/login" className="hidden rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-brand-50 sm:inline-block">
            Sign in
          </Link>
          <Link href="/signup" className="rounded-[10px] bg-brand px-4 py-2 text-sm font-semibold text-white shadow-[0_6px_16px_-6px_rgba(0,123,123,.5)] hover:bg-brand-dark">
            Start free
          </Link>
        </div>
      </nav>
    </header>
  );
}
