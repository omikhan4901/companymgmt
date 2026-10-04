"use client";

import { BookUser, Banknote, Receipt, ShoppingBasket, Store, BarChart3, CalendarClock, FileText, Home, Inbox, ListChecks, Megaphone, Settings, Sparkles, TreePalm, Users, UsersRound, Workflow, type LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useSession } from "@/auth/session";
import { aiOpen, useAIStatus } from "@/components/ai/ai";

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
  const ai = useAIStatus();
  const items: (NavItem & { show: boolean })[] = [
    { href: "/app", label: t("nav.home"), short: t("nav.homeShort"), icon: Home, show: true },
    { href: "/app/ask", label: t("nav.ask"), short: t("nav.ask"), icon: Sparkles, show: aiOpen(ai.data, can).any },
    { href: "/app/pos", label: t("nav.pos"), short: t("nav.pos"), icon: ShoppingBasket, show: hasModule("sales") && can("sales.sell") },
    { href: "/app/customers", label: t("nav.customers"), short: t("nav.customersShort"), icon: BookUser, show: hasModule("customers") && can("customers.view") },
    { href: "/app/expenses", label: t("nav.expenses"), short: t("nav.expenses"), icon: Receipt, show: hasModule("expenses") && can("expenses.record") },
    { href: "/app/tasks", label: t("nav.tasks"), short: t("nav.tasks"), icon: ListChecks, show: hasModule("tasks") && can("tasks.self") },
    { href: "/app/announcements", label: t("nav.announcements"), short: t("nav.announcementsShort"), icon: Megaphone, show: hasModule("announcements") && can("announcements.read") },
    { href: "/app/documents", label: t("nav.documents"), short: t("nav.documentsShort"), icon: FileText, show: hasModule("documents") && can("documents.read") },
    { href: "/app/approvals", label: t("nav.approvals"), short: t("nav.approvalsShort"), icon: Inbox, show: can("leave.approve") || can("attendance.approve") },
    { href: "/app/attendance", label: t("nav.attendance"), short: t("nav.attendanceShort"), icon: CalendarClock, show: hasModule("attendance") && can("attendance.self") },
    { href: "/app/leave", label: t("nav.leave"), short: t("nav.leave"), icon: TreePalm, show: hasModule("leave") && can("leave.self") },
    { href: "/app/payroll", label: t("nav.payroll"), short: t("nav.payroll"), icon: Banknote, show: hasModule("payroll") && can("payroll.self") },
    { href: "/app/sales", label: t("nav.sales"), short: t("nav.sales"), icon: Store, show: hasModule("sales") && (can("sales.view") || can("sales.manage")) },
    { href: "/app/reports", label: t("nav.reports"), short: t("nav.reports"), icon: BarChart3, show: can("reports.view") },
    { href: "/app/people", label: t("nav.people"), short: t("nav.people"), icon: UsersRound, show: can("people.view") },
    { href: "/app/team", label: t("nav.team"), short: t("nav.team"), icon: Users, show: can("members.view") },
    { href: "/app/automations", label: t("nav.automations"), short: t("nav.automations"), icon: Workflow, show: can("automations.manage") },
    {
      href: "/app/settings",
      label: t("nav.settings"),
      short: t("nav.settings"),
      icon: Settings,
      show: can("workspace.manage") || can("branches.manage") || can("audit.view") || can("ai.manage"),
    },
  ];
  return items.filter((i) => i.show);
}

export function isActive(pathname: string, href: string): boolean {
  return href === "/app" ? pathname === "/app" || pathname === "/app/" : pathname === href || pathname.startsWith(`${href}/`);
}
