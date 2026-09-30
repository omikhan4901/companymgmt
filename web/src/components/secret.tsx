"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

/** A value to share once (a code or temporary password), with a copy button. */
export function Secret({ label, value, testId }: { label: string; value: string; testId?: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard can be blocked; the value is still selectable.
    }
  };
  return (
    <div className="flex items-center gap-3 rounded-xl border border-border bg-surface-2 px-3 py-2.5" data-testid={testId}>
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="text-xs text-muted">{label}</span>
        <code className="select-all truncate font-mono text-base">{value}</code>
      </div>
      <button
        type="button"
        onClick={() => void copy()}
        className="grid size-9 shrink-0 place-items-center rounded-lg text-muted hover:bg-surface hover:text-text"
        aria-label={`${t("common.copy")}: ${label}`}
      >
        {copied ? <Check className="size-4 text-success-text" aria-hidden="true" /> : <Copy className="size-4" aria-hidden="true" />}
      </button>
      <span className="sr-only" aria-live="polite">
        {copied ? t("common.copied") : ""}
      </span>
    </div>
  );
}
