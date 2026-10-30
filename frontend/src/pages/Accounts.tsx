import { useState, type FormEvent } from "react";
import { api, json } from "../lib/api";
import { useSession } from "../lib/session";
import { ACCOUNT_LABELS, type AccountType } from "../lib/types";
import { ErrorNote } from "../components/Sheet";
import { PdfHintsForm } from "../components/PdfHintsForm";

export function Accounts() {
  const { accounts, reloadAccounts } = useSession();
  const [name, setName] = useState("");
  const [type, setType] = useState<AccountType>("bank");
  const [institution, setInstitution] = useState("");
  const [last4, setLast4] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<number | null>(null);
  const showLast4 = type === "credit_card" || type === "debit_card" || type === "bank";

  async function add(e: FormEvent) {
    e.preventDefault();
    if (last4 && !/^\d{4}$/.test(last4)) return setError("Enter exactly the last 4 digits, nothing more.");
    try {
      await api("/accounts", { method: "POST", body: json({ name: name.trim(), account_type: type, institution: institution.trim() || null, last4: showLast4 ? last4 || null : null }) });
      setName(""); setInstitution(""); setLast4(""); setError(null);
      await reloadAccounts();
    } catch (err) { setError((err as Error).message); }
  }

  async function remove(id: number) {
    try { await api(`/accounts/${id}`, { method: "DELETE" }); setRowError(null); await reloadAccounts(); }
    catch (err) { setRowError((err as Error).message); }
    setConfirmId(null);
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section>
        <h1 className="text-2xl font-extrabold tracking-tight mb-4">Accounts</h1>
        <ErrorNote message={rowError} />
        <ul className="card divide-y divide-line mt-2">
          {accounts.map((a) => (
            <li key={a.id} className="flex items-center gap-3 px-4 py-3">
              <span className="flex-1 min-w-0">
                <span className="block font-semibold truncate">{a.name}{a.last4 && <span className="text-muted font-normal"> ending {a.last4}</span>}</span>
                <span className="block text-sm text-muted">{ACCOUNT_LABELS[a.account_type]}{a.institution ? `, ${a.institution}` : ""}</span>
              </span>
              {confirmId === a.id ? (
                <span className="flex gap-2">
                  <button className="btn-danger px-3 py-1.5 text-sm" onClick={() => remove(a.id)}>Delete</button>
                  <button className="btn-quiet px-3 py-1.5 text-sm" onClick={() => setConfirmId(null)}>Keep</button>
                </span>
              ) : (
                <button className="text-sm font-semibold text-muted hover:text-spend" onClick={() => setConfirmId(a.id)}>Delete</button>
              )}
            </li>
          ))}
        </ul>
      </section>

      <div className="space-y-6 self-start">
      <form onSubmit={add} className="card p-5 space-y-4" noValidate>
        <h2 className="text-lg font-bold">Add an account</h2>
        <div>
          <label className="label" htmlFor="aname">Name</label>
          <input id="aname" className="field" required maxLength={80} placeholder="e.g. HDFC Savings, SBI Card" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="atype">Type</label>
            <select id="atype" className="field" value={type} onChange={(e) => setType(e.target.value as AccountType)}>
              {Object.entries(ACCOUNT_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="ainst">Bank or app</label>
            <input id="ainst" className="field" maxLength={80} placeholder="Optional" value={institution} onChange={(e) => setInstitution(e.target.value)} />
          </div>
        </div>
        {showLast4 && (
          <div>
            <label className="label" htmlFor="alast4">Last 4 digits <span className="font-normal">(optional)</span></label>
            <input id="alast4" className="field w-28" inputMode="numeric" maxLength={4} autoComplete="off" value={last4}
              onChange={(e) => setLast4(e.target.value.replace(/\D/g, ""))} />
            <p className="mt-1 text-xs text-muted">Helps match statements later. Never enter the full number, CVV or PIN.</p>
          </div>
        )}
        <ErrorNote message={error} />
        <button className="btn-primary" disabled={!name.trim()}>Add account</button>
      </form>
      <section className="card p-5 space-y-3">
        <h2 className="text-lg font-bold">Locked statement PDFs</h2>
        <PdfHintsForm />
      </section>
      </div>
    </div>
  );
}
