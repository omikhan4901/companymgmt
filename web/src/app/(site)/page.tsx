import {
  BarChart3,
  Banknote,
  BookOpenCheck,
  BookUser,
  Boxes,
  Check,
  Code2,
  Inbox,
  Languages,
  ListChecks,
  MapPin,
  Megaphone,
  Receipt,
  ShieldCheck,
  ShoppingBasket,
  Sparkles,
  TreePalm,
  Workflow,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { PlanGrid } from "@/components/plan-grid";

export const metadata: Metadata = {
  title: { absolute: "CompanyMgmt: run your people, shop and books in one place" },
  description:
    "Location-checked clock-ins, leave, payroll with Bangla payslips, a till with dues, stock and self-posting books, tasks, policies, an AI assistant and an API. Free for up to 5 people.",
};

const modules: { icon: ReactNode; title: string; text: string }[] = [
  { icon: <MapPin />, title: "Attendance at work", text: "One-tap clock-in from any phone, checked against each branch's area on the map. Night shifts, time zones and fair time fixes." },
  { icon: <TreePalm />, title: "Leave", text: "Balances that add up, requests in two taps, a team calendar, and holidays per branch." },
  { icon: <Banknote />, title: "Payroll", text: "Monthly pay runs with allowances, advances and deductions, and payslips in English or বাংলা." },
  { icon: <ShoppingBasket />, title: "Point of sale", text: "A fast till that keeps selling offline, receipts, returns and voids, cash drawers, and shared tills unlocked with a cashier PIN." },
  { icon: <BookUser />, title: "Customers and dues", text: "Sell on account, take payments, send a WhatsApp reminder, and print a statement for every customer." },
  { icon: <Receipt />, title: "Expenses", text: "Record spending with a photo of the receipt, from the drawer or petty cash, by category." },
  { icon: <Boxes />, title: "Stock and purchases", text: "Purchases, suppliers, transfers between branches and stock counts, with average cost and low-stock alerts." },
  { icon: <BookOpenCheck />, title: "Books that keep themselves", text: "Every sale, purchase, expense and pay run posts to double-entry books: profit and loss, balance sheet, cash book, tax-return templates." },
  { icon: <ListChecks />, title: "Tasks and projects", text: "Boards per project, checklists and comments, and a My work list everyone can follow." },
  { icon: <Megaphone />, title: "Announcements and policies", text: "Post to everyone or a team and see who has read it; publish policies and record who acknowledged them." },
  { icon: <Inbox />, title: "Approvals and onboarding", text: "One inbox for leave and time fixes; a new joiner's first days started by themselves." },
  { icon: <BarChart3 />, title: "Reports", text: "Attendance rate, late arrivals, leave taken and overdue work, by period and department, by email if you like." },
  { icon: <Sparkles />, title: "An assistant that knows your business", text: "Ask in plain words and get answers with sources, drafts, summaries and a weekly brief. It only sees what you may see." },
  { icon: <Workflow />, title: "Automations", text: "\"Every Monday, remind managers about overdue tasks\": write it in plain words or build it step by step." },
  { icon: <Code2 />, title: "API and integrations", text: "API keys, signed webhooks, company sign-in with Google, Microsoft or Okta, and automatic provisioning." },
  { icon: <Languages />, title: "English and বাংলা", text: "Every screen, email, receipt and payslip in both languages. Names in any script, everywhere." },
];

const showcase: { title: string; text: string; points: string[]; image: string; alt: string; phone?: boolean }[] = [
  {
    title: "Clock-ins that happen at work",
    text: "Place each branch on the map once. When someone clocks in, their phone shares its location for that moment only.",
    points: ["Required, record only, or off: your choice", "A clear message when someone is too far", "Never tracked between clock-ins"],
    image: "/screens/phone-too-far-bangla.png",
    alt: "A phone in Bangla telling a staff member they are 2 km from the branch",
    phone: true,
  },
  {
    title: "Plan the work and watch it get done",
    text: "Projects with boards, checklists and comments. Everyone sees their own work, most urgent first.",
    points: ["Managers run their own department's projects", "People are told when work is given to them", "Due dates and overdue work stand out"],
    image: "/screens/agency-board.png",
    alt: "A campaign board with tasks to do, in progress and done",
  },
  {
    title: "Know how the month went",
    text: "Attendance rate, late arrivals, leave taken and overdue tasks for any period, for the whole company or one department.",
    points: ["Your own start time and grace period", "Managers see their own teams only", "Weekly or monthly by email"],
    image: "/screens/reports.png",
    alt: "Reports for a 30-person agency's week",
  },
  {
    title: "A till that keeps going",
    text: "Sell from any phone or tablet. If the internet drops, sales wait on the device and go through when it's back. The books, stock and dues update themselves.",
    points: ["Taxes and receipts set by you or your accountant", "Shared tills open with each cashier's PIN", "Close the drawer and see any difference"],
    image: "/screens/pos.png",
    alt: "The till: items on the left, the sale and payment on the right",
  },
  {
    title: "Policies everyone has actually read",
    text: "Share the handbook and policies, ask people to acknowledge the ones that matter, and see who hasn't yet.",
    points: ["Every version kept", "Choose who sees each document", "New joiners get them in their checklist"],
    image: "/screens/policy-acknowledged.png",
    alt: "The code of conduct, acknowledged by 30 of 30 people",
  },
];

const steps = [
  { title: "Create your workspace", text: "Pick your language and business type. We switch on only what you need." },
  { title: "Add your people", text: "Import a spreadsheet, invite by email, or share a join link or QR code. Staff don't need an email." },
  { title: "Run the day from one place", text: "Clock-ins, leave, pay, sales, stock, the books, work and news, on any phone or computer." },
];

const security = [
  "Each business's data is kept apart inside the database itself, not only by the app.",
  "Passkeys, two-step sign-in, company sign-in, and an email when your account is opened on a new device.",
  "A tamper-evident audit log with a built-in integrity check, exportable any time.",
  "National ID numbers and secrets encrypted; passwords hashed with Argon2 and checked against known breaches.",
  "Locations saved only at clock-in and clock-out, rounded to about 11 m.",
  "The assistant can't see more than you, and nothing it suggests happens until you confirm.",
  "Export everything, or delete your workspace, whenever you want.",
  "Report a security issue to security@companymgmt.app: we answer within 3 working days.",
];

const next = ["Online payment in taka and dollars", "Your own domain for your workspace", "Approval chains with several steps"];

function Screenshot({ src, alt, phone }: { src: string; alt: string; phone?: boolean }) {
  if (phone) {
    return (
      <div className="mx-auto w-full max-w-[260px] rounded-[34px] border border-slate-200 bg-white p-2.5 shadow-[0_24px_60px_-24px_rgba(0,42,58,.35)]">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={src} alt={alt} width={1082} height={2202} loading="lazy" className="h-auto w-full rounded-[26px]" />
      </div>
    );
  }
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_24px_60px_-24px_rgba(0,42,58,.35)]">
      <div className="flex gap-1.5 border-b border-slate-200 bg-slate-50 px-4 py-2.5" aria-hidden="true">
        <span className="size-2.5 rounded-full bg-slate-300" />
        <span className="size-2.5 rounded-full bg-slate-300" />
        <span className="size-2.5 rounded-full bg-slate-300" />
      </div>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={alt} width={1440} height={900} loading="lazy" className="h-auto w-full" />
    </div>
  );
}

export default function Landing() {
  return (
    <>
      <section className="relative overflow-hidden bg-gradient-to-b from-brand-50 via-white to-white">
        <div className="site-grid absolute inset-0 [mask-image:radial-gradient(ellipse_at_top,black_30%,transparent_70%)]" aria-hidden="true" />
        <div className="relative mx-auto max-w-[1200px] px-5 pb-10 pt-16 text-center md:px-8 md:pt-24">
          <span className="inline-flex items-center gap-2 rounded-full border border-brand-200 bg-white px-3 py-1 text-xs font-medium text-brand-dark shadow-sm">Free for up to 5 people</span>
          <h1 className="mx-auto mt-5 max-w-3xl font-site-display text-4xl font-extrabold leading-[1.08] tracking-tight text-ink sm:text-5xl lg:text-6xl">
            Run your people, shop and books from <span className="text-brand">one place</span>
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg text-slate-600">
            Attendance checked at the branch, payroll with Bangla payslips, a till that works offline, stock and books that keep themselves, and an assistant that answers from your own data. From a tea stall to a company with branches.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link href="/signup" className="rounded-[10px] bg-brand px-6 py-3 font-semibold text-white shadow-[0_6px_16px_-6px_rgba(0,123,123,.5)] hover:bg-brand-dark">
              Create your workspace
            </Link>
            <Link href="/pricing" className="rounded-[10px] border border-slate-300 bg-white px-6 py-3 font-semibold text-ink hover:border-brand">
              See pricing
            </Link>
          </div>
          <p className="mt-4 text-sm text-slate-500">No card needed. Set up in two minutes.</p>
          <div className="mx-auto mt-14 max-w-5xl text-left">
            <Screenshot src="/screens/home.png" alt="The CompanyMgmt home screen: who's at work, hours this week and requests waiting" />
          </div>
        </div>
      </section>

      <section id="features" className="mx-auto max-w-[1200px] px-5 py-20 md:px-8">
        <p className="text-center text-sm font-semibold uppercase tracking-wider text-brand-dark">Everything in one place</p>
        <h2 className="mt-2 text-center font-site-display text-3xl font-bold text-ink md:text-4xl">What you get today</h2>
        <p className="mx-auto mt-3 max-w-2xl text-center text-slate-600">Switch on only the modules you need. Everything works on a phone, in English and বাংলা.</p>
        <ul className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {modules.map((m) => (
            <li key={m.title} className="rounded-2xl border border-slate-200 bg-white p-5 transition-shadow hover:shadow-[0_12px_32px_-16px_rgba(0,42,58,.25)]">
              <span className="grid size-10 place-items-center rounded-xl bg-brand-50 text-brand [&_svg]:size-5" aria-hidden="true">
                {m.icon}
              </span>
              <h3 className="mt-3 font-semibold text-ink">{m.title}</h3>
              <p className="mt-1 text-slate-600">{m.text}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="bg-slate-50">
        <div className="mx-auto flex max-w-[1200px] flex-col gap-20 px-5 py-20 md:px-8">
          {showcase.map((s, i) => (
            <div key={s.title} className="grid items-center gap-10 lg:grid-cols-2">
              <div className={i % 2 ? "lg:order-2" : undefined}>
                <h2 className="font-site-display text-3xl font-bold text-ink">{s.title}</h2>
                <p className="mt-3 text-lg text-slate-600">{s.text}</p>
                <ul className="mt-5 flex flex-col gap-2.5">
                  {s.points.map((p) => (
                    <li key={p} className="flex items-start gap-2.5 text-slate-700">
                      <Check className="mt-0.5 size-5 shrink-0 text-brand" aria-hidden="true" />
                      {p}
                    </li>
                  ))}
                </ul>
              </div>
              <Screenshot src={s.image} alt={s.alt} phone={s.phone} />
            </div>
          ))}
        </div>
      </section>

      <section id="how" className="mx-auto max-w-[1200px] px-5 py-20 md:px-8">
        <h2 className="text-center font-site-display text-3xl font-bold text-ink md:text-4xl">Up and running this afternoon</h2>
        <ol className="mt-12 grid gap-4 md:grid-cols-3">
          {steps.map((s, i) => (
            <li key={s.title} className="rounded-2xl border border-slate-200 bg-white p-6">
              <span className="grid size-9 place-items-center rounded-full bg-brand font-site-display font-bold text-white" aria-hidden="true">
                {i + 1}
              </span>
              <h3 className="mt-4 font-semibold text-ink">{s.title}</h3>
              <p className="mt-1 text-slate-600">{s.text}</p>
            </li>
          ))}
        </ol>
        <div className="mt-10 grid gap-6 rounded-2xl border border-slate-200 bg-white p-6 md:grid-cols-2 md:items-center md:p-8">
          <div>
            <h3 className="font-site-display text-2xl font-bold text-ink">Simple for a shop. Ready for a company.</h3>
            <p className="mt-2 text-slate-600">Big buttons and plain words for a team of three. Branches, departments, managers who see only their own people, custom roles, an API and company sign-in when you grow. Nothing to move, nothing to re-learn.</p>
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-600">Coming next</p>
            <ul className="mt-3 flex flex-wrap gap-2">
              {next.map((n) => (
                <li key={n} className="rounded-full border border-dashed border-slate-300 px-3 py-1 text-sm text-slate-700">
                  {n}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section id="security" className="bg-navy text-white">
        <div className="mx-auto max-w-[1200px] px-5 py-20 md:px-8">
          <div className="flex items-center gap-3">
            <ShieldCheck className="size-8 text-brand-200" aria-hidden="true" />
            <h2 className="font-site-display text-3xl font-bold md:text-4xl">Built to keep your data safe</h2>
          </div>
          <ul className="mt-10 grid gap-3 md:grid-cols-2">
            {security.map((s) => (
              <li key={s} className="flex items-start gap-3 rounded-2xl border border-white/10 bg-white/5 p-4">
                <Check className="mt-0.5 size-5 shrink-0 text-brand-200" aria-hidden="true" />
                <span className="text-slate-200">{s}</span>
              </li>
            ))}
          </ul>
          <Link href="/security" className="mt-8 inline-block font-semibold text-brand-200 hover:underline">
            How we protect your data
          </Link>
        </div>
      </section>

      <section className="mx-auto max-w-[1200px] px-5 py-20 md:px-8">
        <h2 className="text-center font-site-display text-3xl font-bold text-ink md:text-4xl">Simple pricing</h2>
        <p className="mx-auto mt-3 max-w-xl text-center text-slate-600">One price for your whole workspace, not per user. Every paid plan starts with a 14-day Growth trial.</p>
        <div className="mt-12">
          <PlanGrid />
        </div>
      </section>

      <section className="mx-auto max-w-[1200px] px-5 pb-20 md:px-8">
        <div className="relative overflow-hidden rounded-3xl bg-brand-dark px-8 py-12 text-white md:px-12">
          <div className="site-grid absolute inset-0 opacity-30 [mask-image:linear-gradient(to_left,black,transparent)]" aria-hidden="true" />
          <div className="relative flex flex-col items-start gap-6 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="font-site-display text-3xl font-bold">Try it with your team this week.</h2>
              <p className="mt-2 text-brand-50">Free for up to 5 people, for good. No card needed.</p>
            </div>
            <Link href="/signup" className="rounded-[10px] bg-white px-6 py-3 font-semibold text-brand-dark hover:bg-brand-50">
              Create your workspace
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
