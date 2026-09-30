"use client";

import { Command } from "cmdk";
import { Languages, LogOut, Moon, Search, Sun, UserRound } from "lucide-react";
import { Dialog as D } from "radix-ui";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { useSession } from "@/auth/session";
import { currentLang, setLanguage } from "@/i18n";
import { useTheme } from "@/lib/theme";

import { useNavItems } from "./nav-items";

function Item({ onSelect, icon, children }: { onSelect: () => void; icon: ReactNode; children: ReactNode }) {
  return (
    <Command.Item
      onSelect={onSelect}
      className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-sm data-[selected=true]:bg-accent-soft data-[selected=true]:text-accent-soft-text [&_svg]:size-4 [&_svg]:text-muted"
    >
      {icon}
      {children}
    </Command.Item>
  );
}

/** ⌘K / Ctrl+K: jump to any page or run a common action. */
export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const { t } = useTranslation();
  const router = useRouter();
  const nav = useNavItems();
  const { signOut } = useSession();
  const { resolved, setMode } = useTheme();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        onOpenChange(!open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  const run = (fn: () => void) => () => {
    onOpenChange(false);
    fn();
  };

  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      <D.Portal>
        <D.Overlay className="fixed inset-0 z-40 bg-overlay backdrop-blur-[2px]" />
        <D.Content className="fixed left-1/2 top-[12vh] z-50 w-[min(560px,calc(100vw-24px))] -translate-x-1/2 overflow-hidden rounded-2xl border border-border bg-surface text-text shadow-2xl">
          <D.Title className="sr-only">{t("palette.title")}</D.Title>
          <D.Description className="sr-only">{t("palette.hint")}</D.Description>
          <Command label={t("palette.title")} loop>
            <div className="flex items-center gap-3 border-b border-border px-4">
              <Search className="size-4 text-muted" aria-hidden="true" />
              <Command.Input placeholder={t("palette.placeholder")} className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-muted" />
            </div>
            <Command.List className="max-h-[50vh] overflow-y-auto p-2">
              <Command.Empty className="px-3 py-6 text-center text-sm text-muted">{t("palette.empty")}</Command.Empty>
              <Command.Group heading={t("palette.go")} className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:text-muted">
                {nav.map((n) => (
                  <Item key={n.href} onSelect={run(() => router.push(n.href))} icon={<n.icon aria-hidden="true" />}>
                    {n.label}
                  </Item>
                ))}
                <Item onSelect={run(() => router.push("/app/account"))} icon={<UserRound aria-hidden="true" />}>
                  {t("nav.account")}
                </Item>
              </Command.Group>
              <Command.Group heading={t("palette.actions")} className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:text-muted">
                <Item onSelect={run(() => setMode(resolved === "dark" ? "light" : "dark"))} icon={resolved === "dark" ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}>
                  {resolved === "dark" ? t("palette.lightMode") : t("palette.darkMode")}
                </Item>
                <Item onSelect={run(() => setLanguage(currentLang() === "bn" ? "en" : "bn"))} icon={<Languages aria-hidden="true" />}>
                  {t("nav.language")}
                </Item>
                <Item
                  onSelect={run(async () => {
                    await signOut();
                    router.replace("/login");
                  })}
                  icon={<LogOut aria-hidden="true" />}
                >
                  {t("nav.signOut")}
                </Item>
              </Command.Group>
            </Command.List>
          </Command>
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}

export function useCommandPalette() {
  const [open, setOpen] = useState(false);
  return { open, setOpen };
}
