"use client";

import { Check, Languages, Monitor, Moon, Palette, Sun } from "lucide-react";
import { DropdownMenu as M } from "radix-ui";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import { currentLang, setLanguage, type Lang } from "@/i18n";
import { cn } from "@/lib/cn";
import { ACCENT_SWATCH, ACCENTS, MODES, useTheme, type Accent, type Mode } from "@/lib/theme";

import { Button } from "./ui/button";
import { MenuContent, MenuLabel, MenuSeparator } from "./ui/menu";

/** Switches between English and Bangla; saved on the account when signed in. */
export function LanguageButton({ signedIn = false, className }: { signedIn?: boolean; className?: string }) {
  const { t } = useTranslation();
  const toggle = () => {
    const next: Lang = currentLang() === "bn" ? "en" : "bn";
    setLanguage(next);
    if (signedIn) void api("/v1/auth/me", { method: "PATCH", body: { locale: next } }).catch(() => undefined);
  };
  return (
    <Button variant="ghost" size="sm" onClick={toggle} className={className} lang={currentLang() === "bn" ? "en" : "bn"}>
      <Languages aria-hidden="true" />
      {t("nav.language")}
    </Button>
  );
}

const MODE_ICON: Record<Mode, typeof Sun> = { light: Sun, dark: Moon, system: Monitor };

/** Colour mode and accent, remembered on this device. */
export function AppearanceMenu({ className, side = "bottom" }: { className?: string; side?: "bottom" | "right" | "top" }) {
  const { t } = useTranslation();
  const { mode, accent, resolved, setMode, setAccent } = useTheme();
  const Current = resolved === "dark" ? Moon : Sun;
  return (
    <M.Root>
      <M.Trigger asChild>
        <Button variant="ghost" size="icon" aria-label={t("appearance.title")} className={className}>
          <Current aria-hidden="true" />
        </Button>
      </M.Trigger>
      <MenuContent side={side} align="end" className="w-60">
        <MenuLabel>{t("appearance.mode")}</MenuLabel>
        <M.RadioGroup value={mode} onValueChange={(v) => setMode(v as Mode)}>
          {MODES.map((m) => {
            const Icon = MODE_ICON[m];
            return (
              <M.RadioItem
                key={m}
                value={m}
                className="flex cursor-pointer select-none items-center gap-2 rounded-lg px-2.5 py-2 outline-none data-[highlighted]:bg-surface-2"
              >
                <Icon className="size-4 text-muted" aria-hidden="true" />
                <span className="flex-1">{t(`appearance.modes.${m}`)}</span>
                <M.ItemIndicator>
                  <Check className="size-4 text-accent-soft-text" aria-hidden="true" />
                </M.ItemIndicator>
              </M.RadioItem>
            );
          })}
        </M.RadioGroup>
        <MenuSeparator />
        <MenuLabel className="flex items-center gap-1.5">
          <Palette className="size-3.5" aria-hidden="true" />
          {t("appearance.accent")}
        </MenuLabel>
        <M.RadioGroup value={accent} onValueChange={(v) => setAccent(v as Accent)} className="grid grid-cols-4 gap-1 px-1.5 pb-1.5">
          {ACCENTS.map((a) => (
            <M.RadioItem
              key={a}
              value={a}
              aria-label={t(`appearance.accents.${a}`)}
              className="group flex cursor-pointer flex-col items-center gap-1 rounded-lg py-1.5 outline-none data-[highlighted]:bg-surface-2"
            >
              <span
                className={cn("grid size-7 place-items-center rounded-full ring-offset-2 ring-offset-surface group-data-[state=checked]:ring-2 group-data-[state=checked]:ring-text")}
                style={{ background: ACCENT_SWATCH[a][resolved === "dark" ? 1 : 0] }}
                aria-hidden="true"
              />
              <span className="text-[11px] text-muted">{t(`appearance.accents.${a}`)}</span>
            </M.RadioItem>
          ))}
        </M.RadioGroup>
        <p className="px-2.5 pb-1.5 text-[11px] text-muted">{t("appearance.help")}</p>
      </MenuContent>
    </M.Root>
  );
}
