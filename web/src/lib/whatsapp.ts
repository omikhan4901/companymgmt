import { normalizeDigits } from "./format";

/** A WhatsApp link with a polite reminder, for phones in local or international form. */
export function whatsappLink(phone: string, text: string, country: string | null | undefined): string | null {
  let digits = normalizeDigits(phone).replace(/[^\d+]/g, "");
  if (!digits) return null;
  if (digits.startsWith("+")) digits = digits.slice(1);
  else if (digits.startsWith("00")) digits = digits.slice(2);
  else if (country === "BD" && digits.startsWith("0")) digits = `88${digits}`;
  return `https://wa.me/${digits}?text=${encodeURIComponent(text)}`;
}
