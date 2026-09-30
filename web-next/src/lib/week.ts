/** Calendar helpers on YYYY-MM-DD strings (no time zone shifts). */

function parse(day: string): Date {
  const [y, m, d] = day.split("-").map(Number);
  return new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1));
}

function fmt(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function addDays(day: string, n: number): string {
  const date = parse(day);
  date.setUTCDate(date.getUTCDate() + n);
  return fmt(date);
}

/** ISO weekday, Monday = 1 … Sunday = 7. */
export function isoWeekday(day: string): number {
  return ((parse(day).getUTCDay() + 6) % 7) + 1;
}

/** The first day of the week containing `day`, for a week that starts on `weekStart` (1–7). */
export function startOfWeek(day: string, weekStart: number): string {
  return addDays(day, -((isoWeekday(day) - weekStart + 7) % 7));
}

/** Every day from `start` to `end`, inclusive. */
export function daysBetween(start: string, end: string): string[] {
  const out: string[] = [];
  for (let d = start; d <= end && out.length < 400; d = addDays(d, 1)) out.push(d);
  return out;
}

/** The last day (YYYY-MM-DD) of a month given as YYYY-MM. */
export function lastDayOfMonth(month: string): string {
  const [y, m] = month.split("-").map(Number);
  return new Date(Date.UTC(y ?? 1970, m ?? 1, 0)).toISOString().slice(0, 10);
}
