import Link from "next/link";

import { Logo } from "@/components/logo";

export default function NotFound() {
  return (
    <main className="grid min-h-dvh place-items-center px-4 text-center">
      <div className="flex flex-col items-center gap-5">
        <Logo />
        <p className="font-display text-7xl font-bold text-accent" aria-hidden="true">
          404
        </p>
        <h1 className="text-2xl font-semibold">We couldn&apos;t find that page.</h1>
        <p className="text-muted">It may have moved, or the link may be mistyped.</p>
        <div className="flex gap-2">
          <Link href="/" className="inline-flex h-10 items-center rounded-[10px] border border-border bg-surface px-4 text-sm font-medium hover:bg-surface-2">
            Home page
          </Link>
          <Link href="/app" className="inline-flex h-10 items-center rounded-[10px] bg-accent px-4 text-sm font-medium text-on-accent hover:bg-accent-hover">
            Go to your workspace
          </Link>
        </div>
      </div>
    </main>
  );
}
