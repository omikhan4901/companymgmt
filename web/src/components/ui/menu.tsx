"use client";

import { DropdownMenu as M } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "@/lib/cn";

export const Menu = M.Root;
export const MenuTrigger = M.Trigger;
export const MenuSeparator = (props: ComponentProps<typeof M.Separator>) => <M.Separator className="my-1 h-px bg-border" {...props} />;
export const MenuLabel = ({ className, ...props }: ComponentProps<typeof M.Label>) => (
  <M.Label className={cn("px-2.5 py-1.5 text-xs font-semibold text-muted", className)} {...props} />
);

export function MenuContent({ className, align = "end", ...props }: ComponentProps<typeof M.Content>) {
  return (
    <M.Portal>
      <M.Content
        align={align}
        sideOffset={6}
        className={cn("z-50 min-w-52 rounded-xl border border-border bg-surface p-1 text-sm text-text shadow-xl", className)}
        {...props}
      />
    </M.Portal>
  );
}

export function MenuItem({ className, ...props }: ComponentProps<typeof M.Item>) {
  return (
    <M.Item
      className={cn(
        "flex cursor-pointer select-none items-center gap-2 rounded-lg px-2.5 py-2 outline-none data-[disabled]:opacity-50 data-[highlighted]:bg-surface-2 [&_svg]:size-4 [&_svg]:text-muted",
        className,
      )}
      {...props}
    />
  );
}
