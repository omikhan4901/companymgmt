import { Dropdown, type MenuProps } from "antd";
import { Building2, CalendarClock, ChevronDown, Home, Languages, LogOut, Settings, UserRound, Users, UsersRound } from "lucide-react";
import { motion } from "motion/react";
import type { LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet, useNavigate } from "react-router";

import { useSession } from "@/auth/session";
import Logo from "@/components/Logo";
import { currentLang, setLanguage } from "@/i18n";
import { initials } from "@/lib/format";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  show: boolean;
}

export function useNavItems(): NavItem[] {
  const { t } = useTranslation();
  const { can, hasModule } = useSession();
  return [
    { to: "/", label: t("nav.home"), icon: Home, show: true },
    { to: "/attendance", label: t("nav.attendance"), icon: CalendarClock, show: hasModule("attendance") && can("attendance.self") },
    { to: "/people", label: t("nav.people"), icon: UsersRound, show: can("people.view") },
    { to: "/team", label: t("nav.team"), icon: Users, show: can("members.view") },
    {
      to: "/settings",
      label: t("nav.settings"),
      icon: Settings,
      show: can("workspace.manage") || can("branches.manage") || can("audit.view"),
    },
  ].filter((i) => i.show);
}

function LanguageButton() {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      onClick={() => setLanguage(currentLang() === "bn" ? "en" : "bn")}
      className="inline-flex h-9 items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
    >
      <Languages size={16} aria-hidden="true" />
      {t("nav.language")}
    </button>
  );
}

function WorkspaceSwitcher() {
  const { t } = useTranslation();
  const { me, workspace, switchWorkspace } = useSession();
  const navigate = useNavigate();
  const others = (me?.workspaces ?? []).filter((w) => w.id !== workspace?.id);
  const label = (
    <span className="flex min-w-0 items-center gap-2">
      <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand" aria-hidden="true">
        <Building2 size={16} />
      </span>
      <span className="truncate text-sm font-semibold text-ink">{workspace?.name}</span>
    </span>
  );
  if (!others.length) return <div className="min-w-0">{label}</div>;
  const items: MenuProps["items"] = [
    { key: "title", type: "group", label: t("nav.switchWorkspace") },
    ...others.map((w) => ({
      key: w.id,
      label: w.name,
      onClick: async () => {
        await switchWorkspace(w.id);
        navigate("/");
      },
    })),
  ];
  return (
    <Dropdown menu={{ items }} trigger={["click"]}>
      <button type="button" className="flex min-w-0 items-center gap-1 rounded-lg px-1 py-1 hover:bg-slate-100" aria-label={t("nav.switchWorkspace")}>
        {label}
        <ChevronDown size={14} className="shrink-0 text-slate-400" aria-hidden="true" />
      </button>
    </Dropdown>
  );
}

function UserMenu() {
  const { t } = useTranslation();
  const { me, signOut } = useSession();
  const navigate = useNavigate();
  const items: MenuProps["items"] = [
    { key: "account", icon: <UserRound size={15} />, label: <Link to="/account">{t("nav.account")}</Link> },
    { type: "divider" },
    {
      key: "out",
      icon: <LogOut size={15} />,
      danger: true,
      label: t("nav.signOut"),
      onClick: async () => {
        await signOut();
        navigate("/login");
      },
    },
  ];
  return (
    <Dropdown menu={{ items }} trigger={["click"]} placement="bottomRight">
      <button type="button" className="grid size-9 place-items-center rounded-full bg-navy text-xs font-semibold text-white" aria-label={t("nav.account")}>
        {initials(me?.name ?? "?")}
      </button>
    </Dropdown>
  );
}

export default function AppShell() {
  const { t } = useTranslation();
  const items = useNavItems();
  const mobile = items.slice(0, 5);

  return (
    <div className="min-h-screen">
      <a href="#main" className="skip-link">
        {t("app.skip")}
      </a>
      {/* Sidebar (desktop) */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-slate-200 bg-white px-3 py-4 lg:flex">
        <div className="px-2 pb-4">
          <Logo />
        </div>
        <nav aria-label="Main" className="flex flex-col gap-1">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive ? "text-brand" : "text-slate-600 hover:bg-slate-50 hover:text-ink"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {isActive ? (
                    <motion.span layoutId="nav-pill" className="absolute inset-0 -z-10 rounded-lg bg-brand-50" transition={{ type: "spring", stiffness: 400, damping: 32 }} />
                  ) : null}
                  <item.icon size={18} aria-hidden="true" />
                  {item.label}
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="lg:pl-60">
        {/* Top bar */}
        <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/85 backdrop-blur-md">
          <div className="flex h-16 items-center justify-between gap-3 px-4 md:px-6">
            <WorkspaceSwitcher />
            <div className="flex items-center gap-1">
              <LanguageButton />
              <UserMenu />
            </div>
          </div>
        </header>

        <main id="main" className="px-4 pb-28 pt-6 md:px-6 md:pt-8 lg:pb-12">
          <div className="mx-auto max-w-6xl">
            <Outlet />
          </div>
        </main>
      </div>

      {/* Bottom tabs (phones and tablets) */}
      <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-30 border-t border-slate-200 bg-white/95 backdrop-blur lg:hidden">
        <div className="mx-auto flex max-w-lg justify-around px-1 pb-[env(safe-area-inset-bottom)]">
          {mobile.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `flex min-h-14 min-w-14 flex-1 flex-col items-center justify-center gap-0.5 text-[11px] font-medium ${
                  isActive ? "text-brand" : "text-slate-500"
                }`
              }
            >
              <item.icon size={20} aria-hidden="true" />
              {item.label}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
