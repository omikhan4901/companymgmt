"use client";

import { useState } from "react";

import { cn } from "@/lib/cn";

export interface Bar {
  key: string;
  /** Short axis label, e.g. "28". */
  label: string;
  /** Full label for the tooltip and the table, e.g. "Mon 28 Sep". */
  name: string;
  value: number;
  /** Formatted value, e.g. "31 h 20 min". */
  display: string;
  highlight?: boolean;
}

/**
 * One series of bars (no legend: the card title names it). Bars have rounded tops on the
 * baseline, a 2 px gap, a tooltip on hover or focus, and a table for screen readers.
 */
export function BarChart({ bars, label, height = 160 }: { bars: Bar[]; label: string; height?: number }) {
  const [hover, setHover] = useState<string | null>(null);
  const max = Math.max(1, ...bars.map((b) => b.value));
  const active = bars.find((b) => b.key === hover);
  return (
    <figure className="flex flex-col gap-2">
      <div className="h-5 text-[13px] text-muted" aria-hidden="true">
        {active ? (
          <span>
            <span className="font-medium text-text">{active.display}</span> · {active.name}
          </span>
        ) : null}
      </div>
      <div className="flex items-end gap-[2px] border-b border-border" style={{ height }} aria-hidden="true" onMouseLeave={() => setHover(null)}>
        {bars.map((b) => (
          <div key={b.key} className="flex h-full flex-1 items-end" onMouseEnter={() => setHover(b.key)}>
            <div
              className={cn(
                "w-full rounded-t-[4px] transition-colors",
                b.highlight ? "bg-accent" : b.value ? "bg-bar hover:bg-border-strong" : "bg-bar-off",
                hover === b.key && !b.highlight && "bg-border-strong",
              )}
              style={{ height: `${Math.max(b.value ? 4 : 2, (b.value / max) * (height - 4))}px` }}
            />
          </div>
        ))}
      </div>
      <div className="flex gap-[2px] text-[11px] text-muted" aria-hidden="true">
        {bars.map((b, i) => (
          <span key={b.key} className="flex-1 text-center tabular-nums">
            {i % 2 === bars.length % 2 || bars.length <= 7 ? b.label : ""}
          </span>
        ))}
      </div>
      <table className="sr-only">
        <caption>{label}</caption>
        <tbody>
          {bars.map((b) => (
            <tr key={b.key}>
              <th scope="row">{b.name}</th>
              <td>{b.display}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
