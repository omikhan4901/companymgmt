import { intlLocale } from "@/i18n";

const COUNTRIES = [
  "BD", "IN", "PK", "LK", "NP", "BT", "MM", "MY", "SG", "ID", "PH", "TH", "VN", "AE", "SA", "QA", "KW", "OM", "BH",
  "GB", "IE", "US", "CA", "AU", "NZ", "DE", "FR", "IT", "ES", "NL", "SE", "NO", "DK", "FI", "PL", "TR", "EG", "NG",
  "KE", "ZA", "GH", "JP", "KR", "CN", "BR", "MX",
];

export function countryOptions(): { value: string; label: string }[] {
  const names = new Intl.DisplayNames([intlLocale()], { type: "region" });
  return COUNTRIES.map((code) => ({ value: code, label: names.of(code) ?? code })).sort((a, b) => a.label.localeCompare(b.label));
}

export function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

export function timezoneOptions(): { value: string; label: string }[] {
  const zones: string[] =
    typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : [browserTimezone(), "UTC"];
  return zones.map((z) => ({ value: z, label: z.replace(/_/g, " ") }));
}

/** A reasonable country guess from the browser's time zone. */
export function guessCountry(): string | undefined {
  const tz = browserTimezone();
  const map: Record<string, string> = {
    "Asia/Dhaka": "BD",
    "Asia/Kolkata": "IN",
    "Asia/Calcutta": "IN",
    "Asia/Karachi": "PK",
    "Asia/Colombo": "LK",
    "Asia/Kathmandu": "NP",
    "Asia/Singapore": "SG",
    "Asia/Kuala_Lumpur": "MY",
    "Asia/Dubai": "AE",
    "Asia/Riyadh": "SA",
    "Europe/London": "GB",
    "America/New_York": "US",
    "America/Chicago": "US",
    "America/Los_Angeles": "US",
    "Australia/Sydney": "AU",
  };
  return map[tz];
}

export const CURRENCIES = ["BDT", "INR", "PKR", "LKR", "NPR", "USD", "EUR", "GBP", "AED", "SAR", "MYR", "SGD", "IDR", "PHP", "CAD", "AUD", "NGN", "KES", "ZAR", "JPY"];
