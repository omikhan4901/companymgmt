"use client";

import Link from "next/link";

import { ThemeProvider } from "@/lib/theme";

import { Logo } from "./logo";
import { AppearanceMenu } from "./prefs";

const NAV = [
  { href: "/#features", label: "Features" },
  { href: "/#location", label: "Location check" },
  { href: "/pricing", label: "Pricing" },
  { href: "/#security", label: "Security" },
];

export function SiteHeader() {
  return (
    <ThemeProvider>
      <header className="sticky top-0 z-40 border-b border-border bg-bg/85 backdrop-blur-md">
        <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 md:px-6" aria-label="Main">
          <Logo />
          <div className="hidden items-center gap-1 md:flex">
            {NAV.map((l) => (
              <Link key={l.href} href={l.href} className="rounded-lg px-3 py-2 text-sm font-medium text-muted hover:bg-surface-2 hover:text-text">
                {l.label}
              </Link>
            ))}
          </div>
          <div className="flex items-center gap-1.5">
            <AppearanceMenu />
            <Link href="/login" className="hidden rounded-lg px-3 py-2 text-sm font-medium hover:bg-surface-2 sm:inline-block">
              Sign in
            </Link>
            <Link href="/signup" className="rounded-[10px] bg-accent px-4 py-2 text-sm font-semibold text-on-accent hover:bg-accent-hover">
              Start free
            </Link>
          </div>
        </nav>
      </header>
    </ThemeProvider>
  );
}
