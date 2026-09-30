import Link from "next/link";

import { Logo } from "./logo";

export function SiteFooter() {
  return (
    <footer className="border-t border-border bg-surface">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 text-sm text-muted md:flex-row md:items-center md:justify-between md:px-6">
        <div className="flex flex-col gap-2">
          <Logo />
          <p>© {new Date().getFullYear()} CompanyMgmt. Made in Dhaka.</p>
        </div>
        <nav className="flex flex-wrap gap-5" aria-label="Footer">
          <Link href="/pricing" className="hover:text-text">
            Pricing
          </Link>
          <Link href="/privacy" className="hover:text-text">
            Privacy
          </Link>
          <Link href="/terms" className="hover:text-text">
            Terms
          </Link>
          <a href="mailto:hello@companymgmt.app" className="hover:text-text">
            Contact
          </a>
        </nav>
      </div>
    </footer>
  );
}
