import { normalizeDigits } from "./format";

/** Minor units (paisa, cents) from what someone typed: "20,800", "২০৮০০", "1250.5". */
export function toMinor(text: string, unit = 100): number | null {
  const clean = normalizeDigits(text).replace(/[,\s]/g, "").trim();
  if (!clean) return 0;
  if (!/^-?\d+(\.\d{0,2})?$/.test(clean)) return null;
  return Math.round(Number(clean) * unit);
}

/** The value to show in an input for an amount in minor units ("20800", "1250.5"). */
export function fromMinor(minor: number | null | undefined, unit = 100): string {
  if (minor === null || minor === undefined) return "";
  const whole = minor / unit;
  return Number.isInteger(whole) ? String(whole) : whole.toFixed(2);
}
