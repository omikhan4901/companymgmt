"use client";

import { CalendarClock, Home, Settings, Users, UsersRound, type LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useSession } from "@/auth/session";

export interface NavItem {
  href: string;
  label: string;
  short: string;
  icon: LucideIcon;
}

/** The modules this person can open, in rail order. */
export function useNavItems(): NavItem[] {
  const { t } = useTranslation();
  const { can, hasModule } = useSession();
  const items: (NavItem & { show: boolean })[] = [
    { href: "/app", label: t("nav.home"), short: t("nav.homeShort"), icon: Home, show: true },
    { href: "/app/attendance", label: t("nav.attendance"), short: t("nav.attendanceShort"), icon: CalendarClock, show: hasModule("attendance") && can("attendance.self") },
    { href: "/app/people", label: t("nav.people"), short: t("nav.people"), icon: UsersRound, show: can("people.view") },
    { href: "/app/team", label: t("nav.team"), short: t("nav.team"), icon: Users, show: can("members.view") },
    {
      href: "/app/settings",
      label: t("nav.settings"),
      short: t("nav.settings"),
      icon: Settings,
      show: can("workspace.manage") || can("branches.manage") || can("audit.view"),
    },
  ];
  return items.filter((i) => i.show);
}

export function isActive(pathname: string, href: string): boolean {
  return href === "/app" ? pathname === "/app" || pathname === "/app/" : pathname === href || pathname.startsWith(`${href}/`);
}
