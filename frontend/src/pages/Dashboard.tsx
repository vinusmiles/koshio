import { useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../lib/api";
import { formatDate, formatINR, formatMonth, todayIST } from "../lib/format";
import { useSession } from "../lib/session";
import type { CategoryPoint, MonthPoint, Summary } from "../lib/types";
import { useAsync } from "../lib/useAsync";
import { ErrorNote } from "../components/Sheet";

const PRESETS = [
  ["current_month", "This month"], ["previous_month", "Last month"], ["last_3_months", "Last 3 months"],
  ["last_6_months", "Last 6 months"], ["fy_to_date", "This financial year"], ["previous_fy", "Last financial year"],
  ["custom", "Custom dates"],
] as const;

export function Dashboard({ onAdd }: { onAdd: () => void }) {
  const { dataVersion } = useSession();
  const [preset, setPreset] = useState<string>("current_month");
  const [start, setStart] = useState(todayIST().slice(0, 8) + "01");
  const [end, setEnd] = useState(todayIST());
  const query = preset === "custom" ? { preset, start, end } : { preset };
  const key = [preset, start, end, dataVersion];

  const summary = useAsync(() => api<Summary>("/dashboard/summary", { query }), key);
  const cats = useAsync(() => api<CategoryPoint[]>("/dashboard/categories", { query }), key);
  const monthly = useAsync(() => api<MonthPoint[]>("/dashboard/monthly"), [dataVersion]);

  const s = summary.data;
  const nothingYet = monthly.data && monthly.data.every((m) => Number(m.expenses) === 0 && Number(m.income) === 0) && s?.transaction_count === 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="label" htmlFor="period">Period</label>
          <select id="period" className="field w-auto pr-8" value={preset} onChange={(e) => setPreset(e.target.value)}>
            {PRESETS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        {preset === "custom" && (
          <>
            <div><label className="label" htmlFor="from">From</label><input id="from" type="date" className="field" value={start} onChange={(e) => setStart(e.target.value)} /></div>
            <div><label className="label" htmlFor="to">To</label><input id="to" type="date" className="field" value={end} onChange={(e) => setEnd(e.target.value)} /></div>
          </>
        )}
      </div>

      <ErrorNote message={summary.error} />

      {s && <Statement s={s} />}

      {nothingYet ? (
        <section className="card p-6 sm:p-8">
          <h2 className="text-lg font-bold">Nothing to show yet</h2>
          <p className="mt-2 max-w-prose text-muted">
            Import a bank, card or UPI statement, or add transactions by hand, and your overview takes shape here.
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <Link className="btn-primary" to="/import">Import a statement</Link>
            <button className="btn-quiet" onClick={onAdd}>Add by hand</button>
          </div>
        </section>
      ) : s && (
        <>
          <section aria-label="Key figures" className="grid grid-cols-2 lg:grid-cols-3 gap-px overflow-hidden rounded-card border border-line bg-line">
            <Figure label="Spent" value={formatINR(s.total_expenses)}
              hint={Number(s.total_refunds) > 0 ? `Before refunds. ${formatINR(s.net_expenses)} after.` : "Purchases, fees and interest"} />
            <Figure label="Income" value={formatINR(s.total_income)} hint="Including reimbursements" />
            <Figure label="Net cash flow" value={formatINR(s.net_cash_flow)} tone={Number(s.net_cash_flow) < 0 ? "spend" : "earn"} hint="Income minus spending after refunds" />
            <Figure label="Refunds" value={formatINR(s.total_refunds)} hint="Taken off your spending" />
            <Figure label="Card outstanding" hint={s.credit_card_outstanding.note}
              value={s.credit_card_outstanding.amount === null ? "—" : `≈ ${formatINR(s.credit_card_outstanding.amount)}`} />
            <Figure label="To review" value={String(s.unreviewed_count)} hint={s.unreviewed_count ? "Transactions waiting for a check" : "All checked"} />
          </section>

          <div className="grid gap-6 lg:grid-cols-5">
            <section className="card p-4 sm:p-5 lg:col-span-3">
              <h2 className="font-bold">Last 12 months</h2>
              <p className="text-sm text-muted mb-3">Spending after refunds, against income</p>
              <div className="h-64">
                {monthly.data && (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={monthly.data.map((m) => ({ month: formatMonth(m.month), Spent: Number(m.expenses), Income: Number(m.income) }))}
                      margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                      <CartesianGrid vertical={false} stroke="rgb(var(--line))" />
                      <XAxis dataKey="month" tick={{ fill: "rgb(var(--muted))", fontSize: 12 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                      <YAxis width={56} tick={{ fill: "rgb(var(--muted))", fontSize: 12 }} tickLine={false} axisLine={false}
                        tickFormatter={(v: number) => (v >= 100000 ? `${(v / 100000).toFixed(1)}L` : v >= 1000 ? `${Math.round(v / 1000)}k` : String(v))} />
                      <Tooltip formatter={(v: number) => formatINR(v)} cursor={{ fill: "rgb(var(--line) / 0.4)" }}
                        contentStyle={{ background: "rgb(var(--surface))", border: "1px solid rgb(var(--line))", borderRadius: 10, color: "rgb(var(--ink))" }} />
                      <Legend iconType="circle" wrapperStyle={{ fontSize: 13 }} />
                      <Bar dataKey="Spent" fill="rgb(var(--spend))" radius={[3, 3, 0, 0]} />
                      <Bar dataKey="Income" fill="rgb(var(--earn))" radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </section>

            <section className="card p-4 sm:p-5 lg:col-span-2">
              <h2 className="font-bold">Where it went</h2>
              <p className="text-sm text-muted mb-4">{s.period.label}, by category</p>
              {cats.data && cats.data.length === 0 && <p className="text-muted">No spending in this period.</p>}
              <ul className="space-y-3">
                {cats.data?.map((c) => {
                  const total = Number(s.net_expenses) || 1;
                  const pct = Math.max(0, Math.min(100, (Number(c.amount) / total) * 100));
                  return (
                    <li key={c.category_id ?? "none"}>
                      <div className="flex justify-between gap-3 text-[15px]">
                        <span className={c.category_id ? "" : "text-muted"}>{c.name}</span>
                        <span className="font-semibold">{formatINR(c.amount)}</span>
                      </div>
                      <div className="mt-1 h-1.5 rounded-full bg-paper" aria-hidden="true">
                        <div className="h-full rounded-full bg-brass" style={{ width: `${pct}%` }} />
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>
          </div>
        </>
      )}
    </div>
  );
}

/** The headline: the period described as one plain sentence. */
function Statement({ s }: { s: Summary }) {
  const net = Number(s.net_cash_flow);
  const range = `${formatDate(s.period.start)} to ${formatDate(s.period.end)}`;
  return (
    <section className="pt-1">
      <p className="text-sm text-muted">{range}</p>
      <h1 className="mt-1 max-w-3xl text-[1.7rem] sm:text-4xl font-extrabold leading-[1.18] tracking-tight">
        {s.period.label}: you spent {formatINR(s.net_expenses, { whole: true })}{Number(s.total_refunds) > 0 ? " after refunds" : ""} and took in {formatINR(s.total_income, { whole: true })}
        {s.transaction_count === 0 ? "." : net >= 0
          ? `, leaving ${formatINR(net, { whole: true })} to spare.`
          : `, which is ${formatINR(Math.abs(net), { whole: true })} more going out than coming in.`}
      </h1>
    </section>
  );
}

function Figure({ label, value, hint, tone }: { label: string; value: string; hint: string; tone?: "spend" | "earn" }) {
  return (
    <div className="bg-surface p-4 sm:p-5">
      <p className="text-sm font-semibold text-muted">{label}</p>
      <p className={`mt-1 text-xl sm:text-2xl font-bold ${tone === "spend" ? "text-spend" : tone === "earn" ? "text-earn" : ""}`}>{value}</p>
      <p className="mt-1 text-xs text-muted leading-snug">{hint}</p>
    </div>
  );
}
