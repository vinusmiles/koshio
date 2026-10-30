import { useEffect, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { onSlow } from "../lib/api";
import { useSession } from "../lib/session";
import { applyTheme, getTheme, type ThemePref } from "../lib/theme";
import { Wordmark } from "./Wordmark";

const NAV = [
  { to: "/", label: "Overview", icon: "M3 13h4v8H3zM10 8h4v13h-4zM17 3h4v18h-4z" },
  { to: "/transactions", label: "Transactions", icon: "M4 6h16M4 12h16M4 18h10" },
  { to: "/import", label: "Import", icon: "M12 3v12M7 10l5 5 5-5M4 19h16" },
  { to: "/accounts", label: "Accounts", icon: "M3 7h18v12H3zM3 11h18M7 15h4" },
];

function Icon({ d }: { d: string }) {
  return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d} /></svg>;
}

export function Layout({ children, onAdd }: { children: ReactNode; onAdd: () => void }) {
  const { email, signOut } = useSession();
  const [slow, setSlow] = useState(false);
  const [theme, setTheme] = useState<ThemePref>(getTheme);
  useEffect(() => onSlow(setSlow), []);
  const nextTheme: Record<ThemePref, ThemePref> = { system: "light", light: "dark", dark: "system" };

  return (
    <div className="min-h-screen pb-24 sm:pb-10">
      <header className="sticky top-0 z-30 border-b border-line bg-paper/90 backdrop-blur pt-[env(safe-area-inset-top)]">
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
          <NavLink to="/" aria-label="Koshio home"><Wordmark /></NavLink>
          <nav className="hidden sm:flex gap-1" aria-label="Main">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end
                className={({ isActive }) => `rounded-lg px-3 py-2 text-[15px] font-semibold ${isActive ? "bg-surface border border-line" : "text-muted hover:text-ink"}`}>
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <button className="btn-primary hidden sm:inline-flex" onClick={onAdd}>Add transaction</button>
            <button className="btn-quiet px-3" title={`Theme: ${theme}`}
              onClick={() => { const t = nextTheme[theme]; setTheme(t); applyTheme(t); }}>
              {theme === "light" ? "Light" : theme === "dark" ? "Dark" : "Auto"}
            </button>
            <button className="btn-quiet px-3" onClick={signOut} title={email ?? undefined}>Sign out</button>
          </div>
        </div>
        {slow && (
          <p role="status" className="border-t border-line bg-brass/10 px-4 py-2 text-center text-sm">
            Waking up the server. The first load after a quiet spell can take up to a minute.
          </p>
        )}
      </header>

      <main className="mx-auto max-w-6xl px-4 py-5">{children}</main>

      {/* Phone navigation */}
      <nav aria-label="Main" className="sm:hidden fixed bottom-0 inset-x-0 z-30 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)]">
        <div className="grid grid-cols-5">
          {NAV.slice(0, 2).map((n) => <Tab key={n.to} {...n} />)}
          <button onClick={onAdd} className="flex flex-col items-center justify-center py-2 text-xs font-semibold" aria-label="Add transaction">
            <span className="grid h-9 w-9 place-items-center rounded-full bg-ink text-paper text-2xl leading-none">+</span>
          </button>
          <Tab {...NAV[2]} />
          <Tab {...NAV[3]} />
        </div>
      </nav>
    </div>
  );
}

function Tab({ to, label, icon }: { to: string; label: string; icon: string }) {
  return (
    <NavLink to={to} end className={({ isActive }) => `flex flex-col items-center gap-0.5 py-2 text-xs font-semibold ${isActive ? "text-ink" : "text-muted"}`}>
      <Icon d={icon} />{label}
    </NavLink>
  );
}
