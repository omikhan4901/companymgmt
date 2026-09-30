"use client";

import { Check } from "lucide-react";
import { RadioGroup as R, Switch as S } from "radix-ui";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/cn";

/** Large selectable cards (radio semantics), used in onboarding and settings. */
export function ChoiceGroup({ className, ...props }: ComponentProps<typeof R.Root>) {
  return <R.Root className={cn("grid gap-2", className)} {...props} />;
}

export function Choice({ value, label, hint, icon, className }: { value: string; label: ReactNode; hint?: ReactNode; icon?: ReactNode; className?: string }) {
  return (
    <R.Item
      value={value}
      className={cn(
        "group flex items-center gap-3 rounded-xl border border-border bg-surface px-3.5 py-3 text-left transition-colors hover:border-border-strong data-[state=checked]:border-accent data-[state=checked]:bg-accent-soft/60",
        className,
      )}
    >
      {icon && <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-surface-2 text-muted group-data-[state=checked]:bg-accent group-data-[state=checked]:text-on-accent [&_svg]:size-[18px]">{icon}</span>}
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-sm font-medium">{label}</span>
        {hint && <span className="text-[13px] text-muted">{hint}</span>}
      </span>
      <span className="grid size-5 shrink-0 place-items-center rounded-full border border-border-strong group-data-[state=checked]:border-accent group-data-[state=checked]:bg-accent">
        <R.Indicator>
          <Check className="size-3 text-on-accent" strokeWidth={3} aria-hidden="true" />
        </R.Indicator>
      </span>
    </R.Item>
  );
}

export function Switch({ className, ...props }: ComponentProps<typeof S.Root>) {
  return (
    <S.Root
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full bg-border-strong transition-colors data-[state=checked]:bg-accent disabled:opacity-50",
        className,
      )}
      {...props}
    >
      <S.Thumb className="block size-5 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-[22px]" />
    </S.Root>
  );
}
