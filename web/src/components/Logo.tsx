import { Link } from "react-router";

export function LogoMark({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="9" fill="#007B7B" />
      <path d="M9 10h14v3H12.5v2.5H21v3h-8.5V22H9z" fill="#fff" />
      <circle cx="25" cy="8" r="2.4" fill="#5eead4" />
    </svg>
  );
}

export default function Logo({ to = "/" }: { to?: string }) {
  return (
    <Link to={to} className="inline-flex items-center gap-2" aria-label="CompanyMgmt home">
      <LogoMark />
      <span className="font-display text-lg font-bold tracking-tight text-ink">
        Company<span className="text-brand">Mgmt</span>
      </span>
    </Link>
  );
}
