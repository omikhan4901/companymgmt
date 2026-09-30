import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

export function Card({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return <section className={cn("rounded-[var(--radius-card)] border border-border bg-surface", className)} {...props} />;
}

export function CardHeader({ title, action, sub, className }: { title: ReactNode; action?: ReactNode; sub?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-start gap-3 px-5 pt-5", className)}>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <h2 className="text-[17px] font-semibold">{title}</h2>
        {sub && <p className="text-[13px] text-muted">{sub}</p>}
      </div>
      {action}
    </div>
  );
}

export function EmptyState({ icon, title, children, action }: { icon?: ReactNode; title: ReactNode; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
      {icon && <div className="grid size-12 place-items-center rounded-2xl bg-accent-soft text-accent-soft-text [&_svg]:size-6">{icon}</div>}
      <p className="font-display text-base font-semibold">{title}</p>
      {children && <div className="max-w-sm text-sm text-muted">{children}</div>}
      {action}
    </div>
  );
}
