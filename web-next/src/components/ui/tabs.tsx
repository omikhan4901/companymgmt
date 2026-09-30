"use client";

import { Tabs as T } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "@/lib/cn";

export const Tabs = T.Root;
export const TabsContent = T.Content;

export function TabsList({ className, ...props }: ComponentProps<typeof T.List>) {
  return (
    <T.List
      className={cn("flex max-w-full gap-1 overflow-x-auto rounded-xl border border-border bg-surface p-1 [scrollbar-width:none]", className)}
      {...props}
    />
  );
}

export function TabsTrigger({ className, ...props }: ComponentProps<typeof T.Trigger>) {
  return (
    <T.Trigger
      className={cn(
        "inline-flex h-8 shrink-0 items-center gap-2 whitespace-nowrap rounded-lg px-3 text-sm font-medium text-muted transition-colors hover:text-text data-[state=active]:bg-accent-soft data-[state=active]:text-accent-soft-text",
        className,
      )}
      {...props}
    />
  );
}
