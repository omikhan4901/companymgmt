import { cn } from "@/lib/cn";
import { initials } from "@/lib/format";

const tones = ["bg-accent-soft text-accent-soft-text", "bg-success-soft text-success-text", "bg-warn-soft text-warn-text", "bg-surface-2 text-text"];

export function Avatar({ name, className }: { name: string; className?: string }) {
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return (
    <span className={cn("inline-grid size-8 shrink-0 place-items-center rounded-full text-[11px] font-semibold", tones[hash % tones.length], className)} aria-hidden="true">
      {initials(name)}
    </span>
  );
}
