"use client";

import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from "react";

import { cn } from "@/lib/cn";

interface FieldProps {
  label: ReactNode;
  children: ReactElement<Record<string, unknown>>;
  help?: ReactNode;
  error?: string;
  optional?: string;
  className?: string;
  /** Visually hide the label (it stays available to screen readers). */
  hideLabel?: boolean;
}

/** Label, control, help text and error, wired together with ids for screen readers. */
export function Field({ label, children, help, error, optional, className, hideLabel }: FieldProps) {
  const id = useId();
  const helpId = `${id}-help`;
  const errorId = `${id}-error`;
  const describedBy = [help ? helpId : null, error ? errorId : null].filter(Boolean).join(" ") || undefined;
  const control = isValidElement(children)
    ? cloneElement(children, {
        id: (children.props.id as string | undefined) ?? id,
        "aria-describedby": describedBy,
        "aria-invalid": error ? true : undefined,
      })
    : children;
  const controlId = isValidElement(children) ? ((children.props.id as string | undefined) ?? id) : id;
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={controlId} className={cn("text-sm font-medium", hideLabel && "sr-only")}>
        {label}
        {optional && <span className="ml-1 font-normal text-muted">({optional})</span>}
      </label>
      {control}
      {help && !error && (
        <p id={helpId} className="text-[13px] text-muted">
          {help}
        </p>
      )}
      {error && (
        <p id={errorId} className="text-[13px] font-medium text-danger" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
