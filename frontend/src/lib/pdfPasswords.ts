/**
 * Statement PDF passwords follow known patterns built from the cardholder's name,
 * date of birth and card number. If you choose, your name and date of birth are kept
 * in this browser only (never sent to Koshio's database). When a statement is locked,
 * the likely passwords are built here and sent once with that upload, where they're
 * tried in memory and thrown away.
 */
const KEY = "koshio.pdfHints";
const SKIP_KEY = "koshio.pdfHintsSkipped";

export interface PdfHints { name: string; dob: string } // dob as YYYY-MM-DD

export function loadHints(): PdfHints | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const h = JSON.parse(raw) as PdfHints;
    return h.name && /^\d{4}-\d{2}-\d{2}$/.test(h.dob) ? h : null;
  } catch { return null; }
}

export function saveHints(h: PdfHints) {
  try { localStorage.setItem(KEY, JSON.stringify({ name: h.name.trim(), dob: h.dob })); } catch { /* ignore */ }
}

export function forgetHints() {
  try { localStorage.removeItem(KEY); } catch { /* ignore */ }
}

/** Remember that this device chose to skip the opening step, so it isn't shown again. */
export function skipHintsSetup() {
  try { localStorage.setItem(SKIP_KEY, "1"); } catch { /* ignore */ }
}

/** Show the opening step when this device has neither saved details nor chosen to skip. */
export function needsHintsSetup(): boolean {
  try { return !loadHints() && localStorage.getItem(SKIP_KEY) !== "1"; } catch { return false; }
}

/**
 * Likely passwords, most likely first:
 *  - first 4 letters of the name in capitals + DDMM of birth (Axis, HDFC)
 *  - the same in lower case (used by some other banks)
 *  - DDMMYYYY of birth + last 4 digits of the card (SBI Card), for each card you've added
 *  - DDMMYYYY of birth on its own
 */
export function candidatePasswords(h: PdfHints, cardLast4s: (string | null | undefined)[]): string[] {
  const [y, m, d] = h.dob.split("-");
  const ddmm = d + m, ddmmyyyy = d + m + y;
  const words = h.name.toUpperCase().split(/\s+/).map((w) => w.replace(/[^A-Z]/g, "")).filter(Boolean);
  const joined = words.join("");
  const prefixes = Array.from(new Set([words[0]?.length >= 4 ? words[0].slice(0, 4) : "", joined.slice(0, 4)]))
    .filter((p) => p.length === 4);
  const last4s = Array.from(new Set(cardLast4s.filter((x): x is string => !!x && /^\d{4}$/.test(x))));
  const out = [
    ...prefixes.map((p) => p + ddmm),
    ...prefixes.map((p) => p.toLowerCase() + ddmm),
    ...last4s.map((l) => ddmmyyyy + l),
    ddmmyyyy,
  ];
  return Array.from(new Set(out)).slice(0, 20);
}
