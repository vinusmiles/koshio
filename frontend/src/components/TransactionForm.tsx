import { useEffect, useMemo, useState, type FormEvent } from "react";
import { api, json } from "../lib/api";
import { formatDate, parseAmount, todayIST } from "../lib/format";
import { useSession } from "../lib/session";
import { METHOD_LABELS, TYPE_LABELS, type AccountType, type PaymentMethod, type Transaction, type TxnType } from "../lib/types";
import { ErrorNote, Sheet } from "./Sheet";

const CHOICES: TxnType[] = ["expense", "income", "refund", "transfer", "card_payment", "fee", "interest", "reimbursement"];
const CATEGORY_KIND: Partial<Record<TxnType, "expense" | "income" | "transfer">> = {
  expense: "expense", fee: "expense", interest: "expense", refund: "expense",
  income: "income", reimbursement: "income", transfer: "transfer", card_payment: "transfer",
};
const MOVES_MONEY = (t: TxnType) => t === "transfer" || t === "card_payment";
const METHOD_FOR: Partial<Record<AccountType, PaymentMethod>> = {
  credit_card: "credit_card", debit_card: "debit_card", cash: "cash", bank: "bank_transfer", upi: "upi",
};

export function TransactionForm({ existing, onClose, onSaved }: {
  existing?: Transaction; onClose: () => void; onSaved: () => void;
}) {
  const { accounts, categories } = useSession();
  const [type, setType] = useState<TxnType>(existing?.transaction_type ?? "expense");
  const [amount, setAmount] = useState(existing ? existing.amount : "");
  const [date, setDate] = useState(existing?.transaction_date ?? todayIST());
  const [merchant, setMerchant] = useState(existing?.merchant_name ?? "");
  const [categoryId, setCategoryId] = useState<string>(existing?.category_id?.toString() ?? "");
  const [accountId, setAccountId] = useState<string>(existing?.account_id?.toString() ?? "");
  const [toAccountId, setToAccountId] = useState<string>(existing?.counterparty_account_id?.toString() ?? "");
  const [method, setMethod] = useState<PaymentMethod>(existing?.payment_method ?? "upi");
  const [notes, setNotes] = useState(existing?.notes ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  // "Use this category for every payment to this payee", for imported transactions.
  const [applyAll, setApplyAll] = useState(false);
  const [payeeCount, setPayeeCount] = useState(0);
  useEffect(() => {
    if (!existing?.payee_key) return;
    api<{ count: number }>("/sorting/payee-count", { query: { payee_key: existing.payee_key } })
      .then((r) => setPayeeCount(r.count)).catch(() => {});
  }, [existing?.payee_key]);

  const kind = CATEGORY_KIND[type];
  const cats = useMemo(() => categories.filter((c) => c.kind === kind), [categories, kind]);
  const cards = accounts.filter((a) => a.account_type === "credit_card");
  const toChoices = type === "card_payment" ? cards : accounts.filter((a) => a.id.toString() !== accountId);

  function pickType(t: TxnType) {
    setType(t);
    if (CATEGORY_KIND[t] !== kind) setCategoryId("");
    if (t === "card_payment") {
      setMethod("bank_transfer");
      const billCat = categories.find((c) => c.name === "Credit card bill payment");
      if (billCat) setCategoryId(billCat.id.toString());
    }
  }

  function pickAccount(id: string) {
    setAccountId(id);
    const acc = accounts.find((a) => a.id.toString() === id);
    const m = acc && METHOD_FOR[acc.account_type];
    if (m && !MOVES_MONEY(type)) setMethod(m);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    const amt = parseAmount(amount);
    if (!amt) return setError("Enter an amount above zero, with at most two decimal places.");
    if (MOVES_MONEY(type) && (!accountId || !toAccountId)) {
      return setError(type === "card_payment" ? "Choose the account you paid from and the card you paid." : "Choose both accounts for the transfer.");
    }
    const body = {
      transaction_type: type, amount: amt, transaction_date: date, payment_method: method,
      merchant_name: merchant || null, notes: notes || null,
      category_id: categoryId ? Number(categoryId) : null,
      account_id: accountId ? Number(accountId) : null,
      counterparty_account_id: MOVES_MONEY(type) && toAccountId ? Number(toAccountId) : null,
      // A transfer or card bill recorded here is always money leaving the "from" account.
      direction: MOVES_MONEY(type) ? "debit" : null,
      is_reviewed: true,
    };
    setSaving(true); setError(null);
    try {
      if (existing) await api(`/transactions/${existing.id}`, { method: "PATCH", body: json(body) });
      else await api("/transactions", { method: "POST", body: json(body) });
      if (applyAll && existing?.payee_key && categoryId && kind === "expense") {
        await api("/sorting/apply", { method: "POST", body: json({
          payee_key: existing.payee_key, category_id: Number(categoryId), only_uncategorised: false }) });
      }
      onSaved();
    } catch (err) {
      setError((err as Error).message);
    } finally { setSaving(false); }
  }

  async function remove() {
    if (!existing) return;
    setSaving(true);
    try { await api(`/transactions/${existing.id}`, { method: "DELETE" }); onSaved(); }
    catch (err) { setError((err as Error).message); setSaving(false); }
  }

  const fromLabel = type === "card_payment" ? "Paid from" : MOVES_MONEY(type) ? "From account" :
    kind === "income" || type === "refund" ? "Received into" : "Paid from";

  return (
    <Sheet title={existing ? "Edit transaction" : "Add transaction"} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <fieldset>
          <legend className="label">What happened</legend>
          <div className="flex flex-wrap gap-2">
            {CHOICES.map((t) => (
              <button type="button" key={t} onClick={() => pickType(t)} aria-pressed={type === t}
                className={`rounded-full border px-3 py-1.5 text-sm font-semibold ${type === t ? "border-ink bg-ink text-paper" : "border-line text-muted hover:text-ink"}`}>
                {TYPE_LABELS[t]}
              </button>
            ))}
          </div>
          {MOVES_MONEY(type) && (
            <p className="mt-2 text-sm text-muted">Moving your own money. Koshio won't count this as spending or income.</p>
          )}
        </fieldset>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="amt">Amount (₹)</label>
            <input id="amt" className="field text-lg font-bold" inputMode="decimal" autoComplete="off"
              placeholder="0.00" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="date">Date</label>
            <input id="date" type="date" className="field" value={date} max={todayIST()} onChange={(e) => setDate(e.target.value)} />
          </div>
        </div>

        {!MOVES_MONEY(type) && (
          <div>
            <label className="label" htmlFor="merchant">{kind === "income" ? "From whom" : "Where"}</label>
            <input id="merchant" className="field" maxLength={120} placeholder={kind === "income" ? "e.g. Employer" : "e.g. Ratnadeep Supermarket"}
              value={merchant} onChange={(e) => setMerchant(e.target.value)} />
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="acc">{fromLabel}</label>
            <select id="acc" className="field" value={accountId} onChange={(e) => pickAccount(e.target.value)}>
              <option value="">{MOVES_MONEY(type) ? "Choose…" : "Not specified"}</option>
              {accounts.filter((a) => type !== "card_payment" || a.account_type !== "credit_card").map((a) => (
                <option key={a.id} value={a.id}>{a.name}{a.last4 ? ` ••${a.last4}` : ""}</option>
              ))}
            </select>
          </div>
          {MOVES_MONEY(type) ? (
            <div>
              <label className="label" htmlFor="to">{type === "card_payment" ? "Card paid" : "To account"}</label>
              <select id="to" className="field" value={toAccountId} onChange={(e) => setToAccountId(e.target.value)}>
                <option value="">Choose…</option>
                {toChoices.map((a) => <option key={a.id} value={a.id}>{a.name}{a.last4 ? ` ••${a.last4}` : ""}</option>)}
              </select>
              {type === "card_payment" && cards.length === 0 && (
                <p className="mt-1 text-xs text-muted">Add your credit card under Accounts first.</p>
              )}
            </div>
          ) : (
            <div>
              <label className="label" htmlFor="method">Paid by</label>
              <select id="method" className="field" value={method} onChange={(e) => setMethod(e.target.value as PaymentMethod)}>
                {Object.entries(METHOD_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
          )}
        </div>

        {!MOVES_MONEY(type) && (
          <div>
            <label className="label" htmlFor="cat">Category</label>
            <select id="cat" className="field" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
              <option value="">Uncategorised</option>
              {cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            {type === "refund" && <p className="mt-1 text-xs text-muted">Pick the category of the original purchase so the refund comes off it.</p>}
            {existing?.payee_key && kind === "expense" && categoryId && (
              <label className="mt-2 flex items-start gap-2 text-sm">
                <input type="checkbox" className="mt-0.5 h-4 w-4" checked={applyAll} onChange={(e) => setApplyAll(e.target.checked)} />
                <span>Use this category for {payeeCount > 1 ? `all ${payeeCount} payments` : "every payment"} to this payee, and in future statements</span>
              </label>
            )}
          </div>
        )}

        <div>
          <label className="label" htmlFor="notes">Note <span className="font-normal">(optional)</span></label>
          <textarea id="notes" rows={2} className="field" maxLength={2000} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>

        {existing?.origin === "import" && existing.raw_description && (
          <p className="rounded-lg bg-paper px-3 py-2 text-sm text-muted">Statement text: {existing.raw_description}</p>
        )}

        <ErrorNote message={error} />

        <div className="flex flex-wrap items-center gap-3 pt-1">
          <button className="btn-primary flex-1" disabled={saving}>{saving ? "Saving…" : existing ? "Save changes" : "Add transaction"}</button>
          {existing && !confirmDelete && <button type="button" className="btn-danger" onClick={() => setConfirmDelete(true)}>Delete</button>}
        </div>
        {existing && confirmDelete && (
          <div className="rounded-lg border border-spend/40 p-3 text-sm">
            <p className="mb-2">Delete this {formatDate(existing.transaction_date)} transaction for good?</p>
            <div className="flex gap-2">
              <button type="button" className="btn-danger" onClick={remove} disabled={saving}>Yes, delete it</button>
              <button type="button" className="btn-quiet" onClick={() => setConfirmDelete(false)}>Keep it</button>
            </div>
          </div>
        )}
      </form>
    </Sheet>
  );
}
