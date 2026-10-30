import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { formatDate, formatINR, shortFunding } from "../lib/format";
import { useSession } from "../lib/session";
import { INFLOW, METHOD_LABELS, OUTFLOW, TYPE_LABELS, type Transaction, type TransactionPage, type TxnType } from "../lib/types";
import { ErrorNote } from "../components/Sheet";

const FILTERS: [string, string, TxnType[] | undefined][] = [
  ["all", "All", undefined],
  ["out", "Spending", ["expense", "fee", "interest"]],
  ["in", "Income", ["income", "reimbursement"]],
  ["refund", "Refunds", ["refund"]],
  ["move", "Transfers", ["transfer", "card_payment"]],
  ["review", "To review", undefined],
];
const PAGE = 50;

export function Transactions({ onEdit }: { onEdit: (t: Transaction) => void }) {
  const { dataVersion, categories } = useSession();
  const [params] = useSearchParams();
  const [filter, setFilter] = useState(params.get("review") ? "review" : "all");
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [items, setItems] = useState<Transaction[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { const t = setTimeout(() => setSearch(q), 300); return () => clearTimeout(t); }, [q]);

  useEffect(() => {
    let live = true;
    setLoading(true);
    const types = FILTERS.find((f) => f[0] === filter)?.[2];
    const uncategorised = categoryId === "none";
    api<TransactionPage>("/transactions", { query: {
      transaction_type: types, q: search, page, page_size: PAGE,
      category_id: categoryId && !uncategorised ? categoryId : undefined,
      uncategorised: uncategorised || undefined,
      unreviewed: filter === "review" || undefined,
    } }).then((r) => {
      if (!live) return;
      setItems((prev) => (page === 1 ? r.items : [...prev, ...r.items]));
      setTotal(r.total); setError(null);
    }).catch((e) => live && setError(e.message)).finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [filter, search, categoryId, page, dataVersion]);

  // Any filter change starts from the first page again.
  useEffect(() => { setPage(1); }, [filter, search, categoryId, dataVersion]);

  const groups = items.reduce<Record<string, Transaction[]>>((acc, t) => {
    (acc[t.transaction_date] ||= []).push(t); return acc;
  }, {});

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-extrabold tracking-tight">Transactions</h1>

      <div className="flex flex-col sm:flex-row gap-3">
        <input type="search" className="field sm:max-w-xs" placeholder="Search merchant, description or note"
          aria-label="Search transactions" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className="field sm:max-w-[14rem]" aria-label="Category" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
          <option value="">All categories</option>
          <option value="none">Uncategorised</option>
          {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1" role="group" aria-label="Type">
        {FILTERS.map(([key, label]) => (
          <button key={key} onClick={() => setFilter(key)} aria-pressed={filter === key}
            className={`shrink-0 rounded-full border px-3 py-1.5 text-sm font-semibold ${filter === key ? "border-ink bg-ink text-paper" : "border-line text-muted hover:text-ink"}`}>
            {label}
          </button>
        ))}
      </div>

      <ErrorNote message={error} />
      {!loading && items.length === 0 && !error && (
        <p className="card p-6 text-muted">{search || filter !== "all" || categoryId ? "No transactions match these filters." : "No transactions yet. Use Add transaction to record one."}</p>
      )}

      <div className="space-y-5">
        {Object.entries(groups).map(([day, rows]) => (
          <section key={day}>
            <h2 className="mb-2 text-sm font-semibold text-muted">{formatDate(day)}</h2>
            <ul className="card divide-y divide-line">
              {rows.map((t) => <Row key={t.id} t={t} onClick={() => onEdit(t)} />)}
            </ul>
          </section>
        ))}
      </div>

      {items.length < total && (
        <button className="btn-quiet w-full" disabled={loading} onClick={() => setPage((p) => p + 1)}>
          {loading ? "Loading…" : `Show more (${total - items.length} left)`}
        </button>
      )}
      {total > 0 && <p className="text-center text-sm text-muted">{total} transaction{total === 1 ? "" : "s"}</p>}
    </div>
  );
}

function Row({ t, onClick }: { t: Transaction; onClick: () => void }) {
  const out = OUTFLOW.includes(t.transaction_type);
  const inn = INFLOW.includes(t.transaction_type);
  const title = t.merchant_name || t.description || TYPE_LABELS[t.transaction_type];
  const meta = [t.category_name ?? (t.is_transfer ? null : "Uncategorised"), t.account_name,
    shortFunding(t.funding_source) ? `via ${shortFunding(t.funding_source)}` : METHOD_LABELS[t.payment_method]]
    .filter(Boolean).join(", ");
  return (
    <li>
      <button onClick={onClick} className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-paper">
        <span className="min-w-0 flex-1">
          <span className="block truncate font-semibold">{title}</span>
          <span className="block truncate text-sm text-muted">
            {t.transaction_type !== "expense" && <span className="mr-1.5 font-semibold">{TYPE_LABELS[t.transaction_type]}.</span>}
            {meta}
          </span>
        </span>
        {!t.is_reviewed && <span className="rounded-full bg-brass/15 px-2 py-0.5 text-xs font-semibold text-brass">Review</span>}
        <span className={`shrink-0 font-bold ${out ? "text-spend" : inn ? "text-earn" : "text-muted"}`}>
          {out ? "−" : inn ? "+" : ""}{formatINR(t.amount)}
        </span>
      </button>
    </li>
  );
}
