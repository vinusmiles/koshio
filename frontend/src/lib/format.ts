const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const inrWhole = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** ₹1,25,000.50 — amounts arrive from the API as exact decimal strings. */
export function formatINR(value: string | number | null | undefined, opts: { whole?: boolean } = {}): string {
  const n = typeof value === "string" ? Number(value) : value ?? 0;
  if (!Number.isFinite(n)) return "—";
  const f = opts.whole ? inrWhole : inr;
  // "−₹500" reads better than "-₹500".
  return n < 0 ? "−" + f.format(Math.abs(n)) : f.format(n);
}

/** "2026-10-05" -> "05 Oct 2026". Uses the date part only, so no timezone shift. */
export function formatDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d} ${MONTHS[Number(m) - 1]} ${y}`;
}

/** "2026-10" -> "Oct 26" for chart axes. */
export function formatMonth(ym: string): string {
  const [y, m] = ym.split("-");
  return `${MONTHS[Number(m) - 1]} ${y.slice(2)}`;
}

/** Today's date in India as YYYY-MM-DD. */
export function todayIST(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(new Date());
}

/** Accepts "1,250.5", "₹ 1250", "1250"; returns "1250.50", or null if not a valid positive amount. */
export function parseAmount(input: string): string | null {
  const cleaned = input.replace(/[₹,\s]/g, "");
  if (!/^\d+(\.\d{1,2})?$/.test(cleaned)) return null;
  const n = Number(cleaned);
  if (n <= 0 || n > 999999999999.99) return null;
  return n.toFixed(2);
}

/** "AXIS BANK RUPAY CREDIT CARD 652111XXXXXXXX77" -> "Axis card ••77";
 *  "Axis Bank Ltd. XXXX123456" -> "Axis a/c ••3456"; "UPI Lite" stays. */
export function shortFunding(f: string | null | undefined): string | null {
  if (!f) return null;
  const text = f.trim();
  const masked = text.match(/([X*\d]*[X*]+[X*\d]*\d{2,})\s*$/i);
  if (!masked) return text.slice(0, 30);
  const digits = masked[1].match(/(\d{2,4})$/)![1];
  const lead = text.slice(0, masked.index).trim().split(/\s+/)[0] ?? "";
  const bank = lead && /[a-z]/i.test(lead) ? lead[0].toUpperCase() + lead.slice(1).toLowerCase() + " " : "";
  const isCard = /credit card|debit card/i.test(text) || /^\d{4,6}X{4,}\d{2,4}$/i.test(masked[1]);
  return isCard ? `${bank}card ••${digits}` : `${bank}a/c ••${digits.slice(-4)}`;
}
