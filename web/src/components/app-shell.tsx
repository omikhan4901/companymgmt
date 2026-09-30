"use client";

import { Building2, Check, ChevronsUpDown, LogOut, Search, UserRound } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { DropdownMenu as M } from "radix-ui";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { useSession } from "@/auth/session";
import { cn } from "@/lib/cn";

import { CommandPalette, useCommandPalette } from "./command-palette";
import { LogoMark } from "./logo";
import { isActive, useNavItems } from "./nav-items";
import { AppearanceMenu, LanguageButton } from "./prefs";
import { Avatar } from "./ui/avatar";
import { MenuContent, MenuItem, MenuLabel, MenuSeparator } from "./ui/menu";

function WorkspaceSwitcher() {
  const { t } = useTranslation();
  const { me, workspace, switchWorkspace } = useSession();
  const router = useRouter();
  const workspaces = me?.workspaces ?? [];
  const label = (
    <span className="flex min-w-0 flex-col text-left leading-tight">
      <span className="truncate text-sm font-semibold">{workspace?.name}</span>
      <span className="truncate text-xs text-muted">{workspace?.role}</span>
    </span>
  );
  if (workspaces.length < 2) return <div className="flex min-w-0 items-center gap-2.5">{label}</div>;
  return (
    <M.Root>
      <M.Trigger className="flex min-w-0 items-center gap-2 rounded-lg px-2 py-1 hover:bg-surface-2" aria-label={t("nav.switchWorkspace")}>
        {label}
        <ChevronsUpDown className="size-4 shrink-0 text-muted" aria-hidden="true" />
      </M.Trigger>
      <MenuContent align="start">
        <MenuLabel>{t("nav.switchWorkspace")}</MenuLabel>
        {workspaces.map((w) => (
          <MenuItem
            key={w.id}
            onSelect={async () => {
              if (w.id === workspace?.id) return;
              await switchWorkspace(w.id);
              router.push("/app");
            }}
          >
            <Building2 aria-hidden="true" />
            <span className="flex-1 truncate">{w.name}</span>
            {w.id === workspace?.id && <Check aria-hidden="true" />}
          </MenuItem>
        ))}
      </MenuContent>
    </M.Root>
  );
}

function UserMenu() {
  const { t } = useTranslation();
  const { me, signOut } = useSession();
  const router = useRouter();
  return (
    <M.Root>
      <M.Trigger className="rounded-full" aria-label={t("nav.account")}>
        <Avatar name={me?.name ?? "?"} className="size-9" />
      </M.Trigger>
      <MenuContent>
        <div className="px-2.5 py-2">
          <p className="truncate text-sm font-semibold">{me?.name}</p>
          <p className="truncate text-xs text-muted">{me?.email ?? me?.username}</p>
        </div>
        <MenuSeparator />
        <MenuItem asChild>
          <Link href="/app/account">
            <UserRound aria-hidden="true" />
            {t("nav.account")}
          </Link>
        </MenuItem>
        <MenuItem
          onSelect={async () => {
            await signOut();
            router.replace("/login");
          }}
          className="text-danger [&_svg]:text-danger"
        >
          <LogOut aria-hidden="true" />
          {t("nav.signOut")}
        </MenuItem>
      </MenuContent>
    </M.Root>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const pathname = usePathname();
  const items = useNavItems();
  const palette = useCommandPalette();

  return (
    <div className="min-h-dvh">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2">
        {t("app.skip")}
      </a>

      {/* App rail (desktop) */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[84px] flex-col items-center gap-1.5 border-r border-border bg-rail py-4 lg:flex">
        <Link href="/app" aria-label="CompanyMgmt" className="mb-3">
          <LogoMark size={40} />
        </Link>
        <nav aria-label={t("nav.main")} className="flex flex-col items-center gap-1.5">
          {items.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex h-[54px] w-[64px] flex-col items-center justify-center gap-1 rounded-xl text-[11px] font-medium transition-colors",
                  active ? "bg-accent-soft text-accent-soft-text" : "text-muted hover:bg-surface-2 hover:text-text",
                )}
              >
                <item.icon className="size-5" aria-hidden="true" />
                <span className="max-w-full truncate px-1">{item.short}</span>
              </Link>
            );
          })}
        </nav>
        <div className="flex-1" />
        <AppearanceMenu side="right" />
      </aside>

      <div className="lg:pl-[84px]">
        <header className="sticky top-0 z-20 border-b border-border bg-bg/85 backdrop-blur-md">
          <div className="mx-auto flex h-16 max-w-[1400px] items-center gap-3 px-4 md:px-7">
            <Link href="/app" aria-label="CompanyMgmt" className="lg:hidden">
              <LogoMark size={32} />
            </Link>
            <WorkspaceSwitcher />
            <div className="flex-1" />
            <button
              type="button"
              onClick={() => palette.setOpen(true)}
              className="hidden h-10 w-72 items-center gap-2.5 rounded-[10px] border border-border bg-surface px-3 text-sm text-muted hover:border-border-strong md:flex"
            >
              <Search className="size-4" aria-hidden="true" />
              <span className="flex-1 text-left">{t("palette.placeholder")}</span>
              <kbd className="rounded border border-border px-1.5 font-sans text-[11px]">⌘K</kbd>
            </button>
            <button
              type="button"
              onClick={() => palette.setOpen(true)}
              className="grid size-10 place-items-center rounded-[10px] text-muted hover:bg-surface-2 md:hidden"
              aria-label={t("palette.title")}
            >
              <Search className="size-5" aria-hidden="true" />
            </button>
            <LanguageButton signedIn className="hidden sm:inline-flex" />
            <AppearanceMenu className="lg:hidden" />
            <UserMenu />
          </div>
        </header>

        <main id="main" className="mx-auto max-w-[1400px] px-4 pb-28 pt-6 md:px-7 md:pt-8 lg:pb-12">
          {children}
        </main>
      </div>

      {/* Tab bar (phones and tablets) */}
      <nav aria-label={t("nav.main")} className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface/95 backdrop-blur lg:hidden">
        <div className="mx-auto flex max-w-lg justify-around px-1 pb-[env(safe-area-inset-bottom)]">
          {items.slice(0, 5).map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn("flex min-h-16 min-w-14 flex-1 flex-col items-center justify-center gap-1 text-[11px]", active ? "font-semibold text-accent-soft-text" : "text-muted")}
              >
                <item.icon className="size-5" aria-hidden="true" />
                {item.short}
              </Link>
            );
          })}
        </div>
      </nav>

      <CommandPalette open={palette.open} onOpenChange={palette.setOpen} />
    </div>
  );
}
