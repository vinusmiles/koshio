import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../lib/api";
import { formatDate, formatINR, shortFunding } from "../lib/format";
import { useSession } from "../lib/session";
import { candidatePasswords, loadHints } from "../lib/pdfPasswords";
import { PdfHintsForm } from "./PdfHintsForm";
import { SOURCE_LABELS, TYPE_LABELS, type Field, type ImportBatch, type Preview, type PreviewRow, type Source, type TxnType } from "../lib/types";
import { ErrorNote, Sheet } from "./Sheet";

const FIELD_LABELS: [Field, string][] = [
  ["date", "Date"], ["description", "Description or narration"], ["debit", "Money out (debit / withdrawal)"],
  ["credit", "Money in (credit / deposit)"], ["amount", "Single amount column"], ["dr_cr", "Dr/Cr indicator"],
  ["reference", "Reference number"], ["merchant", "Merchant or payee"], ["time", "Time"],
];
const OUT_TYPES: TxnType[] = ["expense", "fee", "interest", "transfer", "card_payment", "adjustment"];
const IN_TYPES: TxnType[] = ["income", "refund", "reimbursement", "transfer", "card_payment", "adjustment"];
const KIND_FOR: Partial<Record<TxnType, string>> = { expense: "expense", fee: "expense", interest: "expense", refund: "expense", income: "income", reimbursement: "income" };

interface Options { header_row?: number | null; mapping?: Record<Field, number | null>; date_format?: string; amount_sign?: string }
interface Edit { skip?: boolean; category_id?: number | null; transaction_type?: TxnType }

export function ImportPreview({ file, accountId, onDone, onCancel }: {
  file: File; accountId: number; onDone: (b: ImportBatch) => void; onCancel: () => void;
}) {
  const { categories, accounts } = useSession();
  const [opts, setOpts] = useState<Options>({});
  const [p, setP] = useState<Preview | null>(null);
  const [source, setSource] = useState<Source | null>(null);
  const [edits, setEdits] = useState<Record<number, Edit>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCols, setShowCols] = useState(false);
  const [limit, setLimit] = useState(30);
  const [showOther, setShowOther] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [saving, setSaving] = useState(false);
  // A statement PDF's password lives only here, in memory, for this one file.
  const [password, setPassword] = useState("");
  const [needPassword, setNeedPassword] = useState<string | null>(null);
  const [typed, setTyped] = useState("");
  const [attempt, setAttempt] = useState(0);
  // Guesses built on this device from the saved name and date of birth, and the password that worked.
  const [guesses, setGuesses] = useState<string[] | null>(null);
  const [guessesFailed, setGuessesFailed] = useState(false);
  const [unlocked, setUnlocked] = useState<string | null>(null);

  function guessesFor(): string[] | null {
    const hints = loadHints();
    if (!hints) return null;
    const own = accounts.find((a) => a.id === accountId)?.last4;
    const cards = accounts.filter((a) => a.account_type === "credit_card" || a.account_type === "debit_card").map((a) => a.last4);
    const list = candidatePasswords(hints, [own, ...cards]);
    return list.length ? list : null;
  }

  useEffect(() => {
    let live = true;
    setLoading(true);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("account_id", String(accountId));
    fd.append("options", JSON.stringify(opts));
    if (password) fd.append("password", password);
    else if (guesses) fd.append("passwords", JSON.stringify(guesses));
    api<Preview & { password_index: number | null }>("/imports/preview", { method: "POST", body: fd })
      .then((r) => {
        if (!live) return;
        if (r.password_index !== null && r.password_index !== undefined) {
          setUnlocked(password || guesses?.[r.password_index] || null);
        }
        setP(r); setError(null); setNeedPassword(null);
        setSource((s) => s ?? r.suggested_source);
        if (r.problems.length) setShowCols(true);
      })
      .catch((e) => {
        if (!live) return;
        if (e instanceof ApiError && e.code?.startsWith("pdf_password")) {
          const auto = !password && !guesses ? guessesFor() : null;
          if (auto) { setGuesses(auto); return; }   // quietly try the saved patterns first
          if (guesses && !password) setGuessesFailed(true);
          setNeedPassword(e.code === "pdf_password_wrong" && guesses && !password
            ? "This PDF is password-protected. The usual patterns didn't open it, so please type its password." : e.message);
          setError(null);
        } else setError(e.message);
      })
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [file, accountId, opts, password, attempt, guesses]);

  const ready = useMemo(() => p?.rows.filter((r) => r.status === "ready") ?? [], [p]);
  const others = useMemo(() => p?.rows.filter((r) => r.status !== "ready") ?? [], [p]);
  const included = ready.filter((r) => !edits[r.row_number]?.skip).length;

  function setOpt(next: Partial<Options>) {
    setEdits({});  // row numbers may change meaning when columns change
    setOpts((o) => ({ ...o, ...(p ? { header_row: p.header_row, mapping: p.mapping } : {}), ...next }));
  }

  async function commit() {
    if (!p || !source) return;
    setSaving(true); setError(null);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("account_id", String(accountId));
    fd.append("source_provider", source);
    fd.append("options", JSON.stringify({ ...opts, header_row: p.header_row, mapping: p.mapping, date_format: p.date_format, amount_sign: p.amount_sign }));
    fd.append("overrides", JSON.stringify(edits));
    if (unlocked) fd.append("password", unlocked);
    try { onDone(await api<ImportBatch>("/imports/commit", { method: "POST", body: fd })); }
    catch (e) { setError((e as Error).message); setConfirming(false); }
    finally { setSaving(false); }
  }

  if (needPassword) return (
    <form className="card p-4 sm:p-5 space-y-3" onSubmit={(e) => { e.preventDefault(); setPassword(typed); setAttempt((n) => n + 1); }}>
      <h2 className="text-lg font-bold break-all">{file.name}</h2>
      <p>{needPassword}</p>
      <div>
        <label className="label" htmlFor="pdfpw">PDF password</label>
        <input id="pdfpw" type="password" className="field sm:max-w-xs" autoComplete="off" autoFocus value={typed}
          onChange={(e) => setTyped(e.target.value)} />
        <p className="mt-1.5 max-w-prose text-xs text-muted">
          This is the password for the PDF file only, usually explained in the email the statement came with (often part of your name plus your date of birth). Koshio uses it to open this file once and doesn't save it. Never enter your net banking password, card PIN, CVV or OTP.
        </p>
      </div>
      <div className="flex gap-3">
        <button className="btn-primary" disabled={!typed || loading}>{loading ? "Opening…" : "Open PDF"}</button>
        <button type="button" className="btn-quiet" onClick={onCancel}>Cancel</button>
      </div>
      {!guessesFailed && (
        <div className="border-t border-line pt-3">
          <PdfHintsForm compact onSaved={() => { const g = guessesFor(); if (g) { setNeedPassword(null); setGuesses(g); } }} />
        </div>
      )}
    </form>
  );

  if (!p) return loading ? <p className="card p-5 text-muted">Reading {file.name}…</p> : (
    <div className="space-y-3"><ErrorNote message={error} /><button className="btn-quiet" onClick={onCancel}>Choose another file</button></div>
  );

  const blocked = p.problems.length > 0 || included === 0;
  return (
    <div className="space-y-5">
      <section className="card p-4 sm:p-5 space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-lg font-bold break-all">{file.name}</h2>
          {p.date_from && <p className="text-sm text-muted">{formatDate(p.date_from)} to {formatDate(p.date_to!)}</p>}
        </div>
        <dl className="grid grid-cols-2 sm:grid-cols-5 gap-px overflow-hidden rounded-lg border border-line bg-line text-center">
          <Count label="Rows found" n={p.counts.detected} wide />
          <Count label="Ready to import" n={p.counts.ready} strong />
          <Count label="Already in Koshio" n={p.counts.duplicate} />
          <Count label="Couldn't be read" n={p.counts.invalid} warn={p.counts.invalid > 0} />
          <Count label="Not transactions" n={p.counts.unrecognised} />
        </dl>
        {p.previous_import && (
          <p className="rounded-lg bg-brass/10 px-3 py-2 text-sm">
            You imported this exact file on {formatDate(p.previous_import.created_at)}. Rows already in Koshio will be skipped, so nothing gets counted twice.
          </p>
        )}
        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="src">This statement is from</label>
            <select id="src" className="field" value={source ?? ""} onChange={(e) => setSource(e.target.value as Source)}>
              {Object.entries(SOURCE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          {p.date_format_options.length > 1 && (
            <div>
              <label className="label" htmlFor="dfmt">Date format{p.date_format_ambiguous && <span className="text-spend"> (please choose)</span>}</label>
              <select id="dfmt" className="field" value={p.date_format_ambiguous ? "" : p.date_format ?? ""}
                onChange={(e) => setOpt({ date_format: e.target.value })}>
                {p.date_format_ambiguous && <option value="">Choose…</option>}
                {p.date_format_options.map((f) => <option key={f} value={f}>{f}{p.rows[0]?.raw && p.mapping.date !== null ? ` (e.g. ${p.rows.find((r) => r.status !== "unrecognised")?.raw[p.mapping.date!] ?? ""})` : ""}</option>)}
              </select>
            </div>
          )}
        </div>
        {p.needs_amount_sign && (
          <fieldset>
            <legend className="label">This file has one amount column. A plain amount means…</legend>
            <div className="flex flex-wrap gap-2">
              {([["positive_is_debit", "Money spent (usual for card statements)"], ["negative_is_debit", "Money received (minus means spent)"]] as const).map(([v, l]) => (
                <button key={v} type="button" aria-pressed={p.amount_sign === v} onClick={() => setOpt({ amount_sign: v })}
                  className={`rounded-full border px-3 py-1.5 text-sm font-semibold ${p.amount_sign === v ? "border-ink bg-ink text-paper" : "border-line text-muted"}`}>{l}</button>
              ))}
            </div>
          </fieldset>
        )}
        {p.problems.map((m) => <ErrorNote key={m} message={m} />)}
        {p.ai_used && (
          <p className="text-sm text-muted">Categories marked <span className="font-semibold text-brass">AI</span> were suggested from merchant names only. Check them before importing.</p>
        )}
        <button className="text-sm font-semibold text-muted hover:text-ink" onClick={() => setShowCols((v) => !v)} aria-expanded={showCols}>
          {showCols ? "Hide columns" : "Check or change which column is which"}
        </button>
        {showCols && <Columns p={p} onChange={setOpt} />}
        {loading && <p className="text-sm text-muted">Updating…</p>}
      </section>

      {ready.length > 0 && (
        <section>
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-bold">Ready to import</h2>
            <p className="text-sm text-muted">Untick anything you don't want. Change a type or category now, or later.</p>
          </div>
          <ul className="card divide-y divide-line">
            {ready.slice(0, limit).map((r) => (
              <ReadyRow key={r.row_number} r={r} edit={edits[r.row_number] ?? {}} categories={categories}
                onEdit={(e) => setEdits((all) => ({ ...all, [r.row_number]: { ...all[r.row_number], ...e } }))} />
            ))}
          </ul>
          {ready.length > limit && <button className="btn-quiet mt-3 w-full" onClick={() => setLimit((l) => l + 100)}>Show more ({ready.length - limit} left)</button>}
        </section>
      )}

      {others.length > 0 && (
        <section>
          <button className="font-bold" onClick={() => setShowOther((v) => !v)} aria-expanded={showOther}>
            {showOther ? "Hide" : "Show"} the {others.length} row{others.length === 1 ? "" : "s"} that won't be imported
          </button>
          {showOther && (
            <ul className="card mt-2 divide-y divide-line text-sm">
              {others.map((r) => (
                <li key={r.row_number} className="px-4 py-2.5">
                  <span className="font-semibold">Row {r.row_number}. </span>
                  <span className={r.status === "invalid" ? "text-spend" : "text-muted"}>{r.message}</span>
                  <span className="block truncate text-muted">{r.raw.filter(Boolean).join("  |  ")}</span>
                </li>
              ))}
            </ul>
          )}
          {p.counts.invalid > 0 && <p className="mt-2 text-sm text-muted">Rows that couldn't be read are saved with the import, so you can check them and add them by hand.</p>}
        </section>
      )}

      <ErrorNote message={error} />
      <div className="sticky bottom-20 sm:bottom-4 z-20 flex gap-3 rounded-card border border-line bg-surface p-3">
        <button className="btn-primary flex-1" data-action="start-import" disabled={blocked || loading} onClick={() => setConfirming(true)}>
          Import {included} transaction{included === 1 ? "" : "s"}
        </button>
        <button className="btn-quiet" onClick={onCancel}>Cancel</button>
      </div>

      {confirming && (
        <Sheet title="Import these transactions?" onClose={() => setConfirming(false)}>
          <ul className="mb-4 space-y-1 text-[15px]">
            <li>{included} new transaction{included === 1 ? "" : "s"} will be added, marked “to review”.</li>
            {p.counts.duplicate > 0 && <li>{p.counts.duplicate} already in Koshio will be skipped.</li>}
            {ready.length - included > 0 && <li>{ready.length - included} you unticked will be left out.</li>}
            {p.counts.invalid + p.counts.unrecognised > 0 && <li>{p.counts.invalid + p.counts.unrecognised} other rows will be saved as problems to check.</li>}
          </ul>
          <p className="mb-4 text-sm text-muted">You can undo this later by deleting the import from the history.</p>
          <button className="btn-primary w-full" data-action="confirm-import" onClick={commit} disabled={saving}>{saving ? "Importing…" : "Import"}</button>
        </Sheet>
      )}
    </div>
  );
}

function Count({ label, n, strong, warn, wide }: { label: string; n: number; strong?: boolean; warn?: boolean; wide?: boolean }) {
  return (
    <div className={`bg-surface px-2 py-3 ${wide ? "col-span-2 sm:col-span-1" : ""}`}>
      <dd className={`text-xl font-bold ${warn ? "text-spend" : strong ? "" : "text-muted"}`}>{n}</dd>
      <dt className="text-xs text-muted">{label}</dt>
    </div>
  );
}

function Columns({ p, onChange }: { p: Preview; onChange: (o: Options) => void }) {
  const setField = (f: Field, v: string) => onChange({ mapping: { ...p.mapping, [f]: v === "" ? null : Number(v) } });
  return (
    <div className="space-y-3 rounded-lg border border-line p-3">
      <div>
        <label className="label" htmlFor="hdr">Heading row</label>
        <select id="hdr" className="field" value={p.header_row ?? ""}
          onChange={(e) => onChange({ header_row: Number(e.target.value), mapping: undefined })}>
          {p.header_row === null && <option value="">Choose the row with the column names…</option>}
          {p.top_rows.map((r, i) => r.some(Boolean) && (
            <option key={i} value={i}>Row {i + 1}: {r.filter(Boolean).slice(0, 5).join(", ").slice(0, 70)}</option>
          ))}
        </select>
      </div>
      {p.header_row !== null && (
        <div className="grid sm:grid-cols-2 gap-3">
          {FIELD_LABELS.map(([f, l]) => (
            <div key={f}>
              <label className="label" htmlFor={`f-${f}`}>{l}</label>
              <select id={`f-${f}`} className="field" value={p.mapping[f] ?? ""} onChange={(e) => setField(f, e.target.value)}>
                <option value="">Not in this file</option>
                {p.columns.map((c, i) => <option key={i} value={i}>{c || `Column ${i + 1}`}</option>)}
              </select>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ReadyRow({ r, edit, categories, onEdit }: {
  r: PreviewRow; edit: Edit; categories: { id: number; name: string; kind: string }[]; onEdit: (e: Edit) => void;
}) {
  const type = edit.transaction_type ?? r.transaction_type!;
  const cat = "category_id" in edit ? edit.category_id : r.category_id;
  const kind = KIND_FOR[type];
  const out = r.direction === "debit";
  return (
    <li className={`px-4 py-3 ${edit.skip ? "opacity-50" : ""}`}>
      <div className="flex items-start gap-3">
        <input type="checkbox" className="mt-1 h-5 w-5 accent-current" checked={!edit.skip} aria-label="Include this row"
          onChange={(e) => onEdit({ skip: !e.target.checked })} />
        <div className="min-w-0 flex-1">
          <div className="flex justify-between gap-3">
            <span className="truncate font-semibold">{r.merchant_name || r.description}</span>
            <span className={`shrink-0 font-bold ${out ? "text-spend" : "text-earn"}`}>{out ? "−" : "+"}{formatINR(r.amount)}</span>
          </div>
          <p className="truncate text-sm text-muted">
            {formatDate(r.transaction_date!)}{r.time ? ` ${r.time.slice(0, 5)}` : ""}
            {shortFunding(r.funding_source) ? `, via ${shortFunding(r.funding_source)}` : r.description && r.merchant_name ? `, ${r.description}` : ""}
          </p>
          {!edit.skip && (
            <div className="mt-2 grid grid-cols-2 gap-2">
              <select className="field py-1.5 text-sm" aria-label="Type" value={type}
                onChange={(e) => onEdit({ transaction_type: e.target.value as TxnType, ...(KIND_FOR[e.target.value as TxnType] !== kind ? { category_id: null } : {}) })}>
                {(out ? OUT_TYPES : IN_TYPES).map((t) => <option key={t} value={t}>{TYPE_LABELS[t]}</option>)}
              </select>
              {kind ? (
                <select className="field py-1.5 text-sm" aria-label="Category" value={cat ?? ""}
                  onChange={(e) => onEdit({ category_id: e.target.value ? Number(e.target.value) : null })}>
                  <option value="">Uncategorised</option>
                  {categories.filter((c) => c.kind === kind).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              ) : <span className="self-center text-xs text-muted">Not counted as spending or income</span>}
              {kind && !("category_id" in edit) && r.category_id && (r.category_source === "ai" || r.category_source === "rule" || r.category_source === "history") && (
                <span className="col-span-2 text-xs font-semibold text-brass">
                  {r.category_source === "ai" ? "AI suggestion" : "Remembered from your earlier choice"}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </li>
  );
}
