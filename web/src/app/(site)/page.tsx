import {
  CalendarCheck2,
  Check,
  ClipboardCheck,
  Languages,
  MapPin,
  ScrollText,
  ShieldCheck,
  Smartphone,
  UserRound,
  UsersRound,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { PlanGrid } from "@/components/plan-grid";

export const metadata: Metadata = {
  title: { absolute: "CompanyMgmt: attendance and people for every business" },
  description: "Location-checked clock-ins, fair time fixes, timesheets and your team in one place. Free for up to 5 people. In English and Bangla.",
};

const features: { icon: ReactNode; title: string; text: string; wide?: boolean }[] = [
  { icon: <MapPin />, title: "Clock in at work, not at home", text: "Each branch has an area on the map. Clock-ins outside it are refused or flagged: your choice.", wide: true },
  { icon: <Smartphone />, title: "Any phone, one big button", text: "Night shifts and branches in different time zones handled." },
  { icon: <UserRound />, title: "Staff without email", text: "Give each person a username; they sign in with your workspace code." },
  { icon: <ClipboardCheck />, title: "Fix mistakes fairly", text: "Forgot to clock out? People ask for a fix, a manager approves it, and the change is recorded." },
  { icon: <CalendarCheck2 />, title: "Monthly timesheets", text: "Hours per person per day, ready to check and download as a spreadsheet." },
  { icon: <UsersRound />, title: "Your people in one place", text: "Profiles, departments and branches. Managers see only their own team.", wide: true },
  { icon: <Languages />, title: "English and বাংলা", text: "Every screen in both languages, light or dark, in the colour you like.", wide: true },
  { icon: <ScrollText />, title: "A record nobody can quietly change", text: "Important changes go into an audit log that can't be edited, with a built-in integrity check.", wide: true },
];

const security = [
  "Each business's data is kept apart inside the database itself, not just by the app.",
  "Two-step verification with an authenticator app, and a list of every signed-in device.",
  "An audit log that can't be edited, with a built-in integrity check.",
  "National ID numbers are encrypted. Passwords are hashed with Argon2.",
  "Locations are saved only when someone clocks in or out, rounded to about 11 m. Never tracked in between.",
  "Every page ships with a strict content security policy.",
];

const next = ["Leave", "Payroll with payslips", "Tasks and projects", "Announcements", "Documents and policies", "An assistant that answers from your own data"];

function Preview() {
  return (
    <div className="relative mx-auto w-full max-w-md" aria-hidden="true">
      <div className="flex flex-col gap-4 rounded-[26px] border border-border bg-surface p-4 shadow-2xl shadow-black/5">
        <div className="flex flex-col gap-4 rounded-[18px] bg-accent p-5 text-on-accent">
          <div className="flex items-center justify-between text-sm font-semibold">
            <span className="flex items-center gap-2">
              <span className="size-2 rounded-full bg-on-accent" />
              Clocked in since 8:02
            </span>
            <span className="flex items-center gap-1 font-medium opacity-90">
              <MapPin className="size-3.5" />
              Main branch
            </span>
          </div>
          <div className="flex items-end justify-between">
            <span className="font-display text-5xl font-bold tracking-tight tabular-nums">6:14</span>
            <span className="rounded-[10px] bg-surface px-4 py-2.5 text-sm font-semibold text-text">Clock out</span>
          </div>
          <span className="inline-flex w-fit items-center gap-1 rounded-md bg-surface px-2 py-0.5 text-xs font-semibold text-success-text">
            <MapPin className="size-3" />
            In: at branch
          </span>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-[16px] border border-border p-4">
            <p className="text-xs text-muted">At work now</p>
            <p className="font-display text-3xl font-semibold tabular-nums">5</p>
          </div>
          <div className="rounded-[16px] border border-border p-4">
            <p className="text-xs text-muted">Hours this week</p>
            <p className="font-display text-3xl font-semibold tabular-nums">186:20</p>
          </div>
        </div>
        <div className="flex items-center gap-3 rounded-[16px] border border-border px-3 py-2.5">
          <span className="rounded-md bg-warn-soft px-2 py-0.5 text-xs font-semibold text-warn-text">Fix</span>
          <span className="flex min-w-0 flex-1 flex-col text-sm">
            <span className="font-semibold">Nadia Rahman</span>
            <span className="truncate text-muted">Forgot to clock out Monday, 5:30 pm</span>
          </span>
          <span className="grid size-8 place-items-center rounded-lg bg-text text-surface">
            <Check className="size-4" />
          </span>
        </div>
      </div>
    </div>
  );
}

export default function Landing() {
  return (
    <>
      <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 md:px-6 md:py-24 lg:grid-cols-[1.1fr_1fr]">
        <div className="flex flex-col items-start gap-6">
          <span className="rounded-md bg-accent-soft px-2.5 py-1 text-xs font-semibold text-accent-soft-text">Free for up to 5 people</span>
          <h1 className="text-4xl font-semibold leading-[1.08] tracking-tight sm:text-5xl lg:text-[56px]">Run your team from one place, from a tea stall to a company with branches.</h1>
          <p className="max-w-xl text-lg text-muted">Know who&apos;s at work and where they clocked in, fix mistakes fairly, and close the month with a timesheet you trust.</p>
          <div className="flex flex-wrap gap-3">
            <Link href="/signup" className="rounded-[12px] bg-accent px-6 py-3 font-semibold text-on-accent hover:bg-accent-hover">
              Create your workspace
            </Link>
            <Link href="/pricing" className="rounded-[12px] border border-border bg-surface px-6 py-3 font-semibold hover:bg-surface-2">
              See pricing
            </Link>
          </div>
          <p className="text-sm text-muted">No card needed. Set up in two minutes.</p>
        </div>
        <Preview />
      </section>

      <section id="features" className="border-y border-border bg-surface">
        <div className="mx-auto max-w-6xl px-4 py-16 md:px-6">
          <h2 className="text-3xl font-semibold">What you get today</h2>
          <ul className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {features.map((f) => (
              <li key={f.title} className={`flex flex-col gap-3 rounded-[var(--radius-card)] border border-border bg-bg p-5 ${f.wide ? "lg:col-span-2" : ""}`}>
                <span className="grid size-10 place-items-center rounded-xl bg-accent-soft text-accent-soft-text [&_svg]:size-5" aria-hidden="true">
                  {f.icon}
                </span>
                <h3 className="text-base font-semibold">{f.title}</h3>
                <p className="text-sm text-muted">{f.text}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section id="location" className="mx-auto grid max-w-6xl gap-10 px-4 py-16 md:px-6 lg:grid-cols-2 lg:items-center">
        <div className="flex flex-col gap-4">
          <h2 className="text-3xl font-semibold">Clock-ins that happen at work</h2>
          <p className="text-muted">Place each branch on the map once and choose how far &ldquo;at work&rdquo; reaches. When someone clocks in, their phone shares its location for that moment only.</p>
          <ol className="flex flex-col gap-3">
            {[
              ["Required", "Clock-in works only inside a branch area. Clock-out is never blocked, only flagged."],
              ["Record only", "Every clock-in is saved with its distance, and ones away from a branch are flagged for managers."],
              ["Off", "No location at all, for teams that work on the road."],
            ].map(([title, text]) => (
              <li key={title} className="flex gap-3 rounded-[16px] border border-border bg-surface p-4">
                <MapPin className="mt-0.5 size-5 shrink-0 text-accent-soft-text" aria-hidden="true" />
                <span className="flex flex-col">
                  <span className="font-semibold">{title}</span>
                  <span className="text-sm text-muted">{text}</span>
                </span>
              </li>
            ))}
          </ol>
        </div>
        <div className="rounded-[var(--radius-card)] border border-border bg-surface p-6">
          <p className="text-sm font-semibold text-muted">What staff see when they&apos;re too far</p>
          <div className="mt-4 flex items-start gap-3 rounded-xl bg-danger-soft px-4 py-3 text-sm text-danger-text">
            <MapPin className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            You&apos;re about 1.2 km from Gulshan kiosk. Clock in when you get there.
          </div>
          <p className="mt-6 text-sm font-semibold text-muted">What managers see</p>
          <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold">
            <span className="rounded-md bg-success-soft px-2 py-1 text-success-text">In: at branch</span>
            <span className="rounded-md bg-warn-soft px-2 py-1 text-warn-text">Out: 6.9 km away</span>
          </div>
          <p className="mt-6 text-xs text-muted">A determined person can fake a phone&apos;s location. The check stops casual clock-ins from home, and the saved distance and accuracy help managers spot anything odd.</p>
        </div>
      </section>

      <section className="border-y border-border bg-surface">
        <div className="mx-auto grid max-w-6xl gap-8 px-4 py-16 md:grid-cols-2 md:items-center md:px-6">
          <div className="flex flex-col gap-3">
            <h2 className="text-3xl font-semibold">Simple for a shop. Ready for a company.</h2>
            <p className="text-muted">Tell us what kind of business you run and we switch on only what you need. As you grow, add branches, departments, managers and custom roles. Nothing to move, nothing to re-learn.</p>
          </div>
          <div className="rounded-[var(--radius-card)] border border-border bg-bg p-6">
            <p className="text-sm font-semibold text-muted">Coming next, one module at a time</p>
            <ul className="mt-4 flex flex-wrap gap-2">
              {next.map((m) => (
                <li key={m} className="rounded-full border border-dashed border-border-strong px-3 py-1 text-sm">
                  {m}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section id="security" className="mx-auto max-w-6xl px-4 py-16 md:px-6">
        <div className="flex items-center gap-3">
          <ShieldCheck className="size-7 text-accent-soft-text" aria-hidden="true" />
          <h2 className="text-3xl font-semibold">Built to keep your data safe</h2>
        </div>
        <ul className="mt-8 grid gap-3 md:grid-cols-2">
          {security.map((s) => (
            <li key={s} className="flex items-start gap-3 rounded-[16px] border border-border bg-surface p-4">
              <Check className="mt-0.5 size-5 shrink-0 text-success-text" aria-hidden="true" />
              <span>{s}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="border-t border-border bg-surface">
        <div className="mx-auto max-w-6xl px-4 py-16 md:px-6">
          <h2 className="text-center text-3xl font-semibold">Simple pricing</h2>
          <p className="mx-auto mt-2 max-w-xl text-center text-muted">One price for your whole workspace, not per user. Every paid plan starts with a 14-day Growth trial.</p>
          <div className="mt-10">
            <PlanGrid />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-16 md:px-6">
        <div className="flex flex-col items-start gap-5 rounded-[26px] bg-accent p-8 text-on-accent md:flex-row md:items-center md:justify-between md:p-10">
          <div className="flex flex-col gap-2">
            <h2 className="text-3xl font-semibold">Try it with your team this week.</h2>
            <p className="opacity-90">Free for up to 5 people, forever. No card needed.</p>
          </div>
          <Link href="/signup" className="rounded-[12px] bg-surface px-6 py-3 font-semibold text-text hover:bg-surface-2">
            Create your workspace
          </Link>
        </div>
      </section>
    </>
  );
}
