import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

const tones = {
  error: { box: "bg-danger-soft text-danger-text", icon: XCircle },
  warn: { box: "bg-warn-soft text-warn-text", icon: AlertTriangle },
  success: { box: "bg-success-soft text-success-text", icon: CheckCircle2 },
  info: { box: "bg-accent-soft text-accent-soft-text", icon: Info },
} as const;

/** An inline message. Errors are announced to screen readers. */
export function Alert({ tone = "info", title, children, action, className }: { tone?: keyof typeof tones; title?: ReactNode; children?: ReactNode; action?: ReactNode; className?: string }) {
  const { box, icon: Icon } = tones[tone];
  return (
    <div role={tone === "error" ? "alert" : "status"} className={cn("flex items-start gap-3 rounded-xl px-3.5 py-3 text-sm", box, className)}>
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className="leading-relaxed">{children}</div>}
      </div>
      {action}
    </div>
  );
}
