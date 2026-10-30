import { useEffect, useState, type FormEvent } from "react";
import { api, json } from "../lib/api";
import { useSession } from "../lib/session";
import { ErrorNote } from "../components/Sheet";
import { Wordmark } from "../components/Wordmark";

export function Login() {
  const { signIn } = useSession();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [canRegister, setCanRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<{ registration_open: boolean }>("/auth/status")
      .then((s) => { setCanRegister(s.registration_open); if (s.registration_open) setMode("register"); })
      .catch((e) => setError(e.message));
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const { access_token } = await api<{ access_token: string }>(`/auth/${mode}`, {
        method: "POST", body: json({ email: email.trim(), password }),
      });
      await signIn(access_token);
    } catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  }

  return (
    <main className="min-h-screen grid place-items-center px-4 py-10">
      <div className="w-full max-w-sm">
        <Wordmark size="lg" />
        <p className="mt-3 mb-8 text-lg text-muted">All your spending. One smart view.</p>
        <form onSubmit={submit} className="card p-5 space-y-4">
          <h1 className="text-xl font-bold">{mode === "register" ? "Create your account" : "Sign in"}</h1>
          {mode === "register" && (
            <p className="text-sm text-muted">This Koshio has no account yet. The first account created becomes the only one, and sign-up then closes.</p>
          )}
          <div>
            <label className="label" htmlFor="email">Email</label>
            <input id="email" type="email" className="field" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="pw">Password</label>
            <input id="pw" type="password" className="field" required minLength={mode === "register" ? 10 : undefined}
              autoComplete={mode === "register" ? "new-password" : "current-password"} value={password} onChange={(e) => setPassword(e.target.value)} />
            {mode === "register" && <p className="mt-1 text-xs text-muted">At least 10 characters. A short phrase works well.</p>}
          </div>
          <ErrorNote message={error} />
          <button className="btn-primary w-full" disabled={busy}>
            {busy ? "Please wait…" : mode === "register" ? "Create account" : "Sign in"}
          </button>
          {canRegister && (
            <button type="button" className="w-full text-sm font-semibold text-muted hover:text-ink"
              onClick={() => setMode(mode === "login" ? "register" : "login")}>
              {mode === "login" ? "Create an account instead" : "I already have an account"}
            </button>
          )}
        </form>
        <p className="mt-6 text-xs text-muted leading-relaxed">
          Koshio never asks for bank passwords, UPI PINs, OTPs or card CVVs. Your transactions are stored in your own private database.
        </p>
      </div>
    </main>
  );
}
