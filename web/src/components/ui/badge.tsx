import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

const badge = cva("inline-flex items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-semibold", {
  variants: {
    tone: {
      neutral: "bg-surface-2 text-muted ring-1 ring-inset ring-border",
      accent: "bg-accent-soft text-accent-soft-text",
      success: "bg-success-soft text-success-text",
      warn: "bg-warn-soft text-warn-text",
      danger: "bg-danger-soft text-danger-text",
    },
  },
  defaultVariants: { tone: "neutral" },
});

export function Badge({ className, tone, ...props }: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badge>) {
  return <span className={cn(badge({ tone }), className)} {...props} />;
}
