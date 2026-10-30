import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, json } from "../lib/api";
import { formatDate, formatINR } from "../lib/format";
import { useSession } from "../lib/session";
import type { SortGroup, SortGroups } from "../lib/types";
import { ErrorNote } from "../components/Sheet";

// The categories most payments end up in, shown as one-tap buttons. The rest are in "More".
const QUICK = ["Groceries", "Food and restaurants", "Fuel", "Travel", "Shopping", "Clothing and accessories",
  "Healthcare", "Family expenses", "Utilities", "Personal care", "Electronics", "Education"];

/** Quick sort: one card per payee, one tap per card. Each choice is remembered for good. */
export function Sort() {
  const { categories, touchData } = useSession();
  const [data, setData] = useState<SortGroups | null>(null);
  const [index, setIndex] = useState(0);
  const [done, setDone] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [last, setLast] = useState<string | null>(null);

  useEffect(() => { api<SortGroups>("/sorting/groups", { query: { limit: 100 } }).then(setData).catch((e) => setError(e.message)); }, []);

  const spending = useMemo(() => categories.filter((c) => c.kind === "expense"), [categories]);
  const quick = QUICK.map((n) => spending.find((c) => c.name === n)).filter(Boolean) as typeof spending;
  const more = spending.filter((c) => !QUICK.includes(c.name));
  const group: SortGroup | undefined = data?.groups[index];

  async function choose(categoryId: number) {
    if (!group) return;
    setSaving(true); setError(null);
    try {
      const r = await api<{ updated: number; category: string }>("/sorting/apply", {
        method: "POST", body: json({ payee_key: group.payee_key, category_id: categoryId }),
      });
      setLast(`${r.updated} payment${r.updated === 1 ? "" : "s"} to ${group.name} → ${r.category}`);
      setDone((d) => d + 1); setIndex((i) => i + 1); touchData();
    } catch (e) { setError((e as Error).message); }
    finally { setSaving(false); }
  }

  if (!data) return error ? <ErrorNote message={error} /> : <p className="text-muted">Loading…</p>;

  const total = data.groups.length;
  if (!group) return (
    <div className="space-y-4">
      <h1 className="text-2xl font-extrabold tracking-tight">Quick sort</h1>
      <section className="card p-6">
        <h2 className="text-lg font-bold">{done ? "All sorted" : "Nothing to sort"}</h2>
        <p className="mt-1 text-muted">
          {done ? `You sorted ${done} payee${done === 1 ? "" : "s"}. Koshio will use these choices on every future statement.`
            : "Every payment has a category. New ones will show up here after your next import."}
        </p>
        <Link to="/" className="btn-primary mt-4">Back to overview</Link>
      </section>
    </div>
  );

  const when = group.first_date === group.last_date ? formatDate(group.first_date)
    : `${formatDate(group.first_date)} to ${formatDate(group.last_date)}`;
  return (
    <div className="space-y-4 max-w-xl">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight">Quick sort</h1>
        <p className="text-muted">One tap per payee. Koshio remembers it for every future statement.</p>
      </div>
      <div className="h-1.5 rounded-full bg-line" aria-hidden="true">
        <div className="h-full rounded-full bg-brass transition-all" style={{ width: `${(index / total) * 100}%` }} />
      </div>
      <p className="text-sm text-muted">{index + 1} of {total}{data.group_count > total ? ` (showing the top ${total})` : ""}</p>

      <section className="card p-5 space-y-4" aria-live="polite">
        <div>
          <h2 className="text-xl font-bold break-words">{group.name}</h2>
          {group.upi_id && group.upi_id !== group.name && <p className="text-sm text-muted break-all">{group.upi_id}</p>}
        </div>
        <p className="text-[15px]">
          You paid this {group.count === 1 ? "once" : `${group.count} times`}
          {group.typical_amount ? `, usually ${formatINR(group.typical_amount)}` : ""}, {formatINR(group.total)} in all
          {group.usual_time ? `, mostly in the ${group.usual_time}` : ""}.
        </p>
        <p className="text-sm text-muted">{when}</p>
        {group.kind === "shop" && <p className="text-sm"><span className="font-semibold">Looks like a shop</span> (paid by scanning its QR code).</p>}
        {group.kind === "person" && <p className="text-sm"><span className="font-semibold">Looks like a personal UPI ID:</span> a person, or a small shop using one.</p>}

        <div className="grid grid-cols-2 gap-2">
          {quick.map((c) => (
            <button key={c.id} disabled={saving} onClick={() => choose(c.id)}
              className="rounded-lg border border-line px-3 py-2.5 text-left text-[15px] font-semibold hover:border-ink hover:bg-paper disabled:opacity-50">
              {c.name}
            </button>
          ))}
        </div>
        {more.length > 0 && (
          <select className="field" value="" disabled={saving} aria-label="Other category"
            onChange={(e) => e.target.value && choose(Number(e.target.value))}>
            <option value="">More categories…</option>
            {more.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        )}
        <ErrorNote message={error} />
        <div className="flex justify-between gap-3 pt-1">
          <button className="btn-quiet" disabled={index === 0 || saving} onClick={() => setIndex((i) => i - 1)}>Back</button>
          <button className="btn-quiet" disabled={saving} onClick={() => setIndex((i) => i + 1)}>Not sure, skip</button>
        </div>
      </section>
      {last && <p className="text-sm text-muted" role="status">Saved: {last}.</p>}
    </div>
  );
}
