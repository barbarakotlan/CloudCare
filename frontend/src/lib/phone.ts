/**
 * Mobile numbers in E.164 (`+15551234567`), US by default. Mirrors
 * backend/app/outreach/phone.py so the form rejects what the API would reject:
 * emergency and service numbers (911, N11 codes, short codes) are never accepted.
 */

export type PhoneCheck = { ok: true; e164: string } | { ok: false; error: string };

const E164 = /^\+[1-9]\d{7,14}$/;
const NANP = /^\+1([2-9]\d{2})([2-9]\d{2})(\d{4})$/;
const EMERGENCY = new Set([
  "911", "112", "999", "000", "110", "119", "100", "101", "102", "108", "111", "118", "120", "122", "190", "192", "193", "199",
]);

const CANT_USE = "That number can't be used. Enter your own mobile number.";

/** Turns what a person typed into E.164, or explains what's wrong. */
export function toE164(raw: string, defaultCountryCode = "1"): PhoneCheck {
  const trimmed = raw.trim();
  if (!trimmed) return { ok: false, error: "Enter a mobile number." };
  const plus = trimmed.startsWith("+");
  const bare = trimmed.replace(/\D/g, "");
  if (!bare) return { ok: false, error: "Enter a mobile number using digits." };
  if (EMERGENCY.has(bare) || bare.length <= 6) return { ok: false, error: CANT_USE };

  let e164: string;
  if (plus) {
    e164 = `+${bare}`;
  } else if (defaultCountryCode === "1" && bare.length === 11 && bare.startsWith("1")) {
    e164 = `+${bare}`;
  } else if (bare.length === 10 && defaultCountryCode) {
    e164 = `+${defaultCountryCode}${bare}`;
  } else {
    return { ok: false, error: "Enter a 10-digit US number, or start with + and your country code." };
  }

  if (!E164.test(e164)) {
    return { ok: false, error: "That doesn't look like a mobile number. Check the digits and try again." };
  }
  if (e164.startsWith("+1")) {
    const m = NANP.exec(e164);
    if (!m) return { ok: false, error: "That isn't a valid US or Canadian number. Check the area code." };
    const [, area, exchange] = m;
    // N11 codes (211 … 911) are service numbers, never a person's phone.
    if (area.slice(1) === "11" || exchange.slice(1) === "11") return { ok: false, error: CANT_USE };
  }
  return { ok: true, e164 };
}

/** Optional field: empty is fine, anything typed must be a usable number. */
export function optionalE164(raw: string): PhoneCheck | { ok: true; e164: null } {
  return raw.trim() ? toE164(raw) : { ok: true, e164: null };
}

/** "+15552345678" → "(555) 234-5678"; other countries keep the E.164 form. */
export function formatPhone(e164: string | null | undefined): string {
  if (!e164) return "";
  const us = /^\+1(\d{3})(\d{3})(\d{4})$/.exec(e164);
  if (us) return `(${us[1]}) ${us[2]}-${us[3]}`;
  return e164;
}

/** Pretty-prints while typing a US number; leaves international input alone. */
export function formatAsTyped(raw: string): string {
  if (raw.trim().startsWith("+")) return raw;
  const digits = raw.replace(/\D/g, "");
  const d = digits.length === 11 && digits.startsWith("1") ? digits.slice(1) : digits;
  if (d.length > 10) return raw;
  if (d.length < 4) return d;
  if (d.length < 7) return `(${d.slice(0, 3)}) ${d.slice(3)}`;
  return `(${d.slice(0, 3)}) ${d.slice(3, 6)}-${d.slice(6)}`;
}

/** Masked for status text: "···1234". */
export function maskedLast4(last4: string | null | undefined): string {
  return last4 ? `···${last4}` : "your phone";
}

export function last4Of(e164: string | null | undefined): string | null {
  const digits = (e164 ?? "").replace(/\D/g, "");
  return digits.length >= 4 ? digits.slice(-4) : null;
}
