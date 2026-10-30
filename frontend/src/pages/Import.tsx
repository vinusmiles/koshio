import { useEffect, useRef, useState, type DragEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { formatDate } from "../lib/format";
import { useSession } from "../lib/session";
import { SOURCE_LABELS, type ImportBatch, type ImportIssue } from "../lib/types";
import { ImportPreview } from "../components/ImportPreview";
import { ErrorNote } from "../components/Sheet";

const ACCEPT = ".pdf,.csv,.xls,.xlsx,.txt,application/pdf";

export function Import() {
  const { accounts, touchData, dataVersion } = useSession();
  const [queue, setQueue] = useState<File[]>([]);
  const [accountId, setAccountId] = useState<number | null>(null);
  const [started, setStarted] = useState(false);
  const [results, setResults] = useState<ImportBatch[]>([]);
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const importable = accounts.filter((a) => a.account_type !== "cash");
  const current = queue[0];

  function addFiles(list: FileList | null) {
    if (!list) return;
    const files = Array.from(list);  // copy now: the browser empties the list when the input is reset
    setQueue((q) => [...q, ...files]);
  }
  function next() {
    setQueue((q) => q.slice(1));
    if (queue.length <= 1) setStarted(false);
  }
  function onDrop(e: DragEvent) { e.preventDefault(); setDrag(false); addFiles(e.dataTransfer.files); }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight">Import statements</h1>
        <p className="mt-1 max-w-prose text-muted">
          Add the PDF statement from PhonePe, Google Pay, Paytm or your credit card email, or a bank statement as PDF, CSV or Excel. Koshio reads it, shows you everything before saving, and never imports the same transaction twice. The file itself isn't kept.
        </p>
      </div>

      {results.length > 0 && !started && (
        <section className="card p-4 sm:p-5">
          <h2 className="font-bold mb-2">Done</h2>
          <ul className="space-y-1.5 text-[15px]">
            {results.map((b) => (
              <li key={b.id}><span className="font-semibold">{b.filename}:</span> {b.records_imported} added
                {b.records_duplicate > 0 && `, ${b.records_duplicate} already there`}
                {b.records_skipped > 0 && `, ${b.records_skipped} left out`}
                {b.records_failed > 0 && <span className="text-spend">, {b.records_failed} couldn't be read</span>}.</li>
            ))}
          </ul>
          <Link to="/transactions?review=1" className="btn-quiet mt-3">Review imported transactions</Link>
        </section>
      )}

      {!started ? (
        <section className="card p-4 sm:p-5 space-y-4">
          <div>
            <label className="label" htmlFor="acc">Which account is this statement for?</label>
            {importable.length === 0 ? (
              <p className="text-sm">First <Link className="font-semibold underline" to="/accounts">add the bank account or card</Link> the statement belongs to.</p>
            ) : (
              <select id="acc" className="field sm:max-w-sm" value={accountId ?? ""} onChange={(e) => setAccountId(e.target.value ? Number(e.target.value) : null)}>
                <option value="">Choose an account…</option>
                {importable.map((a) => <option key={a.id} value={a.id}>{a.name}{a.last4 ? ` ending ${a.last4}` : ""}</option>)}
              </select>
            )}
            <p className="mt-1 text-xs text-muted">For PhonePe, Google Pay or Paytm statements, add the app as a UPI account under Accounts and pick it here. If the same payment is also in your bank statement, Koshio spots it by its UPI reference and counts it once.</p>
          </div>

          <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={onDrop}
            className={`rounded-card border-2 border-dashed p-6 text-center ${drag ? "border-brass bg-brass/5" : "border-line"}`}>
            <p className="font-semibold">Drop statement files here</p>
            <p className="text-sm text-muted mb-3">PDF up to 15 MB; CSV, XLS or XLSX up to 5 MB</p>
            <button type="button" className="btn-quiet" onClick={() => input.current?.click()}>Choose files</button>
            <input ref={input} type="file" accept={ACCEPT} multiple className="sr-only" onChange={(e) => { addFiles(e.target.files); e.target.value = ""; }} />
          </div>

          {queue.length > 0 && (
            <ul className="space-y-1 text-[15px]">
              {queue.map((f, i) => (
                <li key={i} className="flex items-center justify-between gap-3">
                  <span className="truncate">{f.name} <span className="text-muted">({Math.max(1, Math.round(f.size / 1024))} KB)</span></span>
                  <button className="text-sm font-semibold text-muted hover:text-spend" onClick={() => setQueue((q) => q.filter((_, j) => j !== i))}>Remove</button>
                </li>
              ))}
            </ul>
          )}
          <button className="btn-primary" disabled={!queue.length || !accountId} onClick={() => { setResults([]); setStarted(true); }}>
            {queue.length > 1 ? `Check ${queue.length} files` : "Check file"}
          </button>
        </section>
      ) : current && accountId ? (
        <>
          {queue.length > 1 && <p className="text-sm text-muted">File 1 of {queue.length}</p>}
          <ImportPreview key={current.name + current.size + current.lastModified} file={current} accountId={accountId}
            onCancel={next} onDone={(b) => { setResults((r) => [...r, b]); touchData(); next(); }} />
        </>
      ) : null}

      <History version={dataVersion} onChange={touchData} />
    </div>
  );
}

const STATUS: Record<ImportBatch["status"], string> = {
  completed: "Imported", completed_with_issues: "Imported, some rows need a look", nothing_new: "Nothing new",
};

function History({ version, onChange }: { version: number; onChange: () => void }) {
  const [rows, setRows] = useState<ImportBatch[] | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [confirm, setConfirm] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { api<ImportBatch[]>("/imports").then(setRows).catch((e) => setError(e.message)); }, [version]);

  async function remove(id: number) {
    try { await api(`/imports/${id}`, { method: "DELETE" }); setConfirm(null); onChange(); }
    catch (e) { setError((e as Error).message); }
  }

  if (!rows) return null;
  return (
    <section>
      <h2 className="mb-2 text-lg font-bold">Import history</h2>
      <ErrorNote message={error} />
      {rows.length === 0 ? <p className="text-muted">No statements imported yet.</p> : (
        <ul className="card divide-y divide-line">
          {rows.map((b) => (
            <li key={b.id} className="px-4 py-3">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <span className="font-semibold break-all">{b.filename}</span>
                <span className="text-sm text-muted">{formatDate(b.created_at)}</span>
              </div>
              <p className="text-sm text-muted">
                {[b.account_name, SOURCE_LABELS[b.source_provider], b.date_from && `${formatDate(b.date_from)} to ${formatDate(b.date_to!)}`].filter(Boolean).join(", ")}
              </p>
              <p className="text-sm mt-0.5">
                <span className={b.status === "completed_with_issues" ? "text-spend" : ""}>{STATUS[b.status]}.</span>{" "}
                {b.records_detected} rows: {b.records_imported} added, {b.records_duplicate} already there
                {b.records_skipped > 0 && `, ${b.records_skipped} left out`}
                {b.records_failed > 0 && `, ${b.records_failed} unreadable`}
                {b.records_unrecognised > 0 && `, ${b.records_unrecognised} not transactions`}.
              </p>
              <div className="mt-2 flex flex-wrap gap-3 text-sm font-semibold">
                {(b.records_failed > 0 || b.records_unrecognised > 0) && (
                  <button className="text-muted hover:text-ink" onClick={() => setOpen(open === b.id ? null : b.id)}>
                    {open === b.id ? "Hide rows" : `Show rows not imported${b.open_issues ? ` (${b.open_issues} to check)` : ""}`}
                  </button>
                )}
                {confirm === b.id ? (
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="font-normal">Delete this import and its {b.records_imported} transactions?</span>
                    <button className="btn-danger px-3 py-1" onClick={() => remove(b.id)}>Delete</button>
                    <button className="btn-quiet px-3 py-1" onClick={() => setConfirm(null)}>Keep</button>
                  </span>
                ) : <button className="text-muted hover:text-spend" onClick={() => setConfirm(b.id)}>Delete import</button>}
              </div>
              {open === b.id && <Issues batchId={b.id} onChange={onChange} />}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Issues({ batchId, onChange }: { batchId: number; onChange: () => void }) {
  const [items, setItems] = useState<ImportIssue[]>([]);
  useEffect(() => { api<ImportIssue[]>(`/imports/${batchId}/issues`).then(setItems).catch(() => {}); }, [batchId]);
  async function toggle(i: ImportIssue) {
    await api(`/imports/issues/${i.id}`, { method: "PATCH", body: JSON.stringify({ resolved: !i.resolved }) });
    setItems((all) => all.map((x) => (x.id === i.id ? { ...x, resolved: !x.resolved } : x)));
    onChange();
  }
  return (
    <ul className="mt-2 space-y-2 text-sm">
      {items.map((i) => (
        <li key={i.id} className={`rounded-lg border border-line p-2.5 ${i.resolved ? "opacity-60" : ""}`}>
          <p><span className="font-semibold">Row {i.row_number}.</span> <span className={i.kind === "invalid" ? "text-spend" : "text-muted"}>{i.message}</span></p>
          <p className="break-all text-muted">{i.raw.filter(Boolean).join("  |  ")}</p>
          {i.kind === "invalid" && (
            <button className="mt-1 font-semibold text-muted hover:text-ink" onClick={() => toggle(i)}>
              {i.resolved ? "Mark as not handled" : "Mark as handled (I added it by hand or it's not needed)"}
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}
