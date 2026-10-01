import {
  forwardRef,
  type InputHTMLAttributes,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";

import { cn } from "@/lib/cn";

const control =
  "w-full rounded-[10px] border border-border bg-surface px-3 text-sm text-text placeholder:text-muted transition-colors hover:border-border-strong focus-visible:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/30 disabled:cursor-not-allowed disabled:opacity-60 aria-[invalid=true]:border-danger";

export const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement>
>(function Input({ className, ...props }, ref) {
  // File pickers get a button-like "Choose file" that sits in line with the file name.
  const file =
    props.type === "file" &&
    "cursor-pointer py-[5px] pl-1.5 file:mr-3 file:h-7 file:cursor-pointer file:rounded-md file:border-0 file:bg-surface-2 file:px-3 file:text-[13px] file:font-medium file:text-text hover:file:bg-border";
  return (
    <input
      ref={ref}
      className={cn(control, "h-10", file, className)}
      {...props}
    />
  );
});

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className, rows = 3, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      rows={rows}
      className={cn(control, "py-2 leading-relaxed", className)}
      {...props}
    />
  );
});

/** A native select: fully accessible, and uses the phone's own picker on mobile. */
export const Select = forwardRef<
  HTMLSelectElement,
  SelectHTMLAttributes<HTMLSelectElement>
>(function Select({ className, children, ...props }, ref) {
  return (
    <select
      ref={ref}
      className={cn(
        control,
        "h-10 appearance-none bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%238a8a94%22 stroke-width=%222%22><path d=%22m6 9 6 6 6-6%22/></svg>')] bg-[length:16px] bg-[right_10px_center] bg-no-repeat pr-9",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
});
