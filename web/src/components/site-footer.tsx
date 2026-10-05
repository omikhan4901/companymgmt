import Link from "next/link";

import { Logo } from "./logo";

const LINKS = [
  { href: "/pricing", label: "Pricing" },
  { href: "/developers", label: "Developers" },
  { href: "/security", label: "Security" },
  { href: "/privacy", label: "Privacy" },
  { href: "/terms", label: "Terms" },
  { href: "/dpa", label: "DPA" },
  { href: "/subprocessors", label: "Sub-processors" },
];

export function SiteFooter() {
  return (
    <footer className="bg-navy text-slate-300">
      <div className="mx-auto flex max-w-[1200px] flex-col gap-8 px-5 py-12 md:flex-row md:items-start md:justify-between md:px-8">
        <div className="flex max-w-sm flex-col gap-3">
          <Logo className="text-white [&_span]:font-site-display" />
          <p className="text-sm">People, attendance, leave, payroll and work in one place, in English and বাংলা.</p>
          <p className="text-sm text-slate-400">© {new Date().getFullYear()} CompanyMgmt. Made in Dhaka.</p>
        </div>
        <nav className="flex flex-wrap gap-x-6 gap-y-3 text-sm" aria-label="Footer">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} className="hover:text-white">
              {l.label}
            </Link>
          ))}
          <a href="mailto:hello@companymgmt.app" className="hover:text-white">
            Contact
          </a>
        </nav>
      </div>
    </footer>
  );
}
