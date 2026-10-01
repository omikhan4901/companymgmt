import { intlLocale } from "@/i18n";

/** Formats dates and times in a given IANA time zone (the branch's or workspace's). */
export function formatTime(iso: string | null | undefined, timeZone: string): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat(intlLocale(), { hour: "numeric", minute: "2-digit", timeZone }).format(new Date(iso));
}

export function formatDateTime(iso: string | null | undefined, timeZone: string): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat(intlLocale(), {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    timeZone,
  }).format(new Date(iso));
}

/** A calendar date (YYYY-MM-DD) shown as a date, never shifted by time zones. */
export function formatDay(day: string | null | undefined, opts: Intl.DateTimeFormatOptions = {}): string {
  if (!day) return "";
  const [y, m, d] = day.split("-").map(Number);
  const date = new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1));
  return new Intl.DateTimeFormat(intlLocale(), { day: "numeric", month: "short", year: "numeric", timeZone: "UTC", ...opts }).format(date);
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat(intlLocale()).format(value);
}

/** A year without a thousands separator ("2027", "২০২৭"). */
export function formatYear(year: number): string {
  return new Intl.NumberFormat(intlLocale(), { useGrouping: false }).format(year);
}

export function formatMoney(cents: number, currency: string): string {
  return new Intl.NumberFormat(intlLocale(), { style: "currency", currency, maximumFractionDigits: cents % 100 ? 2 : 0 }).format(cents / 100);
}

export function splitMinutes(total: number): { h: number; m: number } {
  const safe = Math.max(0, Math.floor(total));
  return { h: Math.floor(safe / 60), m: safe % 60 };
}

/** "7 h 05 min" style duration in the current language. */
export function formatDuration(total: number | null | undefined, t: (key: string, v?: Record<string, unknown>) => string): string {
  if (total === null || total === undefined) return "–";
  const { h, m } = splitMinutes(total);
  if (h === 0) return t("common.minutes", { count: formatNumber(m) });
  return t("common.hoursMinutes", { h: formatNumber(h), m: formatNumber(m) });
}

/** Today's date (YYYY-MM-DD) in a time zone. */
export function todayIn(timeZone: string, now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(now);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

/** Converts Bangla digits typed by the user into ASCII digits. */
export function normalizeDigits(value: string): string {
  return value.replace(/[০-৯]/g, (d) => String("০১২৩৪৫৬৭৮৯".indexOf(d)));
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const first = parts[0]?.[0] ?? "?";
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? "") : "";
  return (first + last).toUpperCase();
}

/** Local wall time in a zone → ISO instant (used by date-time inputs). */
export function zonedToIso(local: string, timeZone: string): string {
  // `local` is "YYYY-MM-DDTHH:mm". Find the offset of that wall time in the zone.
  const [datePart, timePart] = local.split("T");
  const [y, mo, d] = (datePart ?? "").split("-").map(Number);
  const [h, mi] = (timePart ?? "").split(":").map(Number);
  const guess = Date.UTC(y ?? 1970, (mo ?? 1) - 1, d ?? 1, h ?? 0, mi ?? 0);
  const offset = zoneOffsetMinutes(new Date(guess), timeZone);
  let instant = guess - offset * 60_000;
  // Re-check once near DST changes.
  const offset2 = zoneOffsetMinutes(new Date(instant), timeZone);
  if (offset2 !== offset) instant = guess - offset2 * 60_000;
  return new Date(instant).toISOString();
}

/** ISO instant → "YYYY-MM-DDTHH:mm" wall time in a zone (for date-time inputs). */
export function isoToZoned(iso: string, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(iso));
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "00";
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}`;
}

function zoneOffsetMinutes(date: Date, timeZone: string): number {
  const wall = isoToZoned(date.toISOString(), timeZone);
  const [dp, tp] = wall.split("T");
  const [y, mo, d] = (dp ?? "").split("-").map(Number);
  const [h, mi] = (tp ?? "").split(":").map(Number);
  const asUtc = Date.UTC(y ?? 1970, (mo ?? 1) - 1, d ?? 1, h ?? 0, mi ?? 0);
  return Math.round((asUtc - Math.floor(date.getTime() / 60_000) * 60_000) / 60_000);
}

/** "5 minutes ago", "yesterday", or a date for anything older than a week. */
export function formatAgo(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  const seconds = Math.round((then.getTime() - now.getTime()) / 1000);
  const rtf = new Intl.RelativeTimeFormat(intlLocale(), { numeric: "auto" });
  const abs = Math.abs(seconds);
  if (abs < 45) return rtf.format(0, "second");
  if (abs < 3600) return rtf.format(Math.round(seconds / 60), "minute");
  if (abs < 86_400) return rtf.format(Math.round(seconds / 3600), "hour");
  if (abs < 7 * 86_400) return rtf.format(Math.round(seconds / 86_400), "day");
  return new Intl.DateTimeFormat(intlLocale(), { day: "numeric", month: "short", year: "numeric" }).format(then);
}
