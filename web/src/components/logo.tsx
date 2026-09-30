import Link from "next/link";

import { cn } from "@/lib/cn";

/** The mark takes the current accent colour, so it follows the chosen theme. */
export function LogoMark({ size = 30, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" className={cn("shrink-0 text-accent", className)} aria-hidden="true">
      <rect width="32" height="32" rx="9" fill="currentColor" />
      <rect x="8" y="8" width="7" height="7" rx="2" fill="var(--on-accent)" />
      <rect x="17" y="17" width="7" height="7" rx="2" fill="var(--on-accent)" />
      <rect x="8" y="17" width="7" height="7" rx="2" fill="var(--on-accent)" fillOpacity=".55" />
      <circle cx="20.5" cy="11.5" r="3.5" fill="var(--on-accent)" fillOpacity=".55" />
    </svg>
  );
}

export function Logo({ href = "/", className }: { href?: string; className?: string }) {
  return (
    <Link href={href} className={cn("inline-flex items-center gap-2.5", className)} aria-label="CompanyMgmt home">
      <LogoMark />
      <span className="font-display text-lg font-bold tracking-tight">CompanyMgmt</span>
    </Link>
  );
}
