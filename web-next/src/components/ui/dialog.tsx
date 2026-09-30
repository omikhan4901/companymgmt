"use client";

import { X } from "lucide-react";
import { Dialog as D } from "radix-ui";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

export const Dialog = D.Root;
export const DialogTrigger = D.Trigger;
export const DialogClose = D.Close;

interface ContentProps {
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
  closeLabel?: string;
}

/** A centred dialog on desktop that becomes a bottom sheet on phones. */
export function DialogContent({ title, description, children, footer, className, closeLabel = "Close" }: ContentProps) {
  return (
    <D.Portal>
      <D.Overlay className="fixed inset-0 z-40 bg-overlay backdrop-blur-[2px]" />
      <D.Content
        className={cn(
          "fixed inset-x-0 bottom-0 z-50 flex max-h-[92dvh] flex-col rounded-t-[22px] border border-border bg-surface text-text shadow-2xl sm:inset-auto sm:left-1/2 sm:top-1/2 sm:w-[min(560px,calc(100vw-32px))] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-[20px]",
          className,
        )}
      >
        <div className="flex items-start gap-3 px-5 pb-2 pt-5">
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <D.Title className="font-display text-lg font-semibold">{title}</D.Title>
            {description ? (
              <D.Description className="text-sm text-muted">{description}</D.Description>
            ) : (
              <D.Description className="sr-only">{title}</D.Description>
            )}
          </div>
          <D.Close className="grid size-9 place-items-center rounded-lg text-muted hover:bg-surface-2 hover:text-text" aria-label={closeLabel}>
            <X className="size-4" aria-hidden="true" />
          </D.Close>
        </div>
        <div className="overflow-y-auto px-5 pb-5 pt-2">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-border px-5 py-4">{footer}</div>}
      </D.Content>
    </D.Portal>
  );
}

/** A panel from the right on desktop (a bottom sheet on phones), for longer forms. */
export function SheetContent({ title, description, children, footer, closeLabel = "Close" }: ContentProps) {
  return (
    <D.Portal>
      <D.Overlay className="fixed inset-0 z-40 bg-overlay backdrop-blur-[2px]" />
      <D.Content className="fixed inset-x-0 bottom-0 z-50 flex max-h-[94dvh] flex-col rounded-t-[22px] border border-border bg-surface text-text shadow-2xl sm:inset-y-0 sm:left-auto sm:right-0 sm:max-h-none sm:w-[min(520px,100vw)] sm:rounded-none sm:rounded-l-[22px]">
        <div className="flex items-start gap-3 border-b border-border px-5 py-4">
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <D.Title className="font-display text-lg font-semibold">{title}</D.Title>
            {description ? <D.Description className="text-sm text-muted">{description}</D.Description> : <D.Description className="sr-only">{title}</D.Description>}
          </div>
          <D.Close className="grid size-9 place-items-center rounded-lg text-muted hover:bg-surface-2 hover:text-text" aria-label={closeLabel}>
            <X className="size-4" aria-hidden="true" />
          </D.Close>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-5">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-border px-5 py-4">{footer}</div>}
      </D.Content>
    </D.Portal>
  );
}
