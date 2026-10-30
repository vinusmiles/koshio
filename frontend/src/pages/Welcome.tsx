import { useState, type FormEvent } from "react";
import { saveHints, skipHintsSetup } from "../lib/pdfPasswords";
import { Wordmark } from "../components/Wordmark";

/** Opening step after signing in on a device: the details that unlock statement PDFs. */
export function Welcome({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const [dob, setDob] = useState("");

  function save(e: FormEvent) {
    e.preventDefault();
    saveHints({ name: name.trim(), dob });
    onDone();
  }

  return (
    <main className="min-h-screen grid place-items-center px-4 py-10">
      <div className="w-full max-w-md">
        <Wordmark size="lg" />
        <p className="mt-3 mb-8 text-lg text-muted">All your spending. One smart view.</p>
        <form onSubmit={save} className="card p-5 space-y-4">
          <h1 className="text-xl font-bold">Unlock your statements automatically</h1>
          <p className="text-[15px] text-muted">
            Card statement PDFs are locked with passwords made from your name and date of birth. Axis and HDFC
            use the first 4 letters of your name and your birthday (DDMM); SBI Card uses your date of birth and
            the card's last 4 digits. Enter them once and Koshio opens these PDFs for you.
          </p>
          <div>
            <label className="label" htmlFor="wname">Full name, as printed on your cards</label>
            <input id="wname" className="field" autoComplete="name" required value={name}
              onChange={(e) => setName(e.target.value)} placeholder="e.g. ASHA RANI VERMA" />
          </div>
          <div>
            <label className="label" htmlFor="wdob">Date of birth</label>
            <input id="wdob" type="date" className="field" required value={dob} max={new Date().toISOString().slice(0, 10)}
              onChange={(e) => setDob(e.target.value)} />
          </div>
          <p className="rounded-lg bg-paper px-3 py-2 text-sm text-muted">
            Saved only on this device, never in Koshio's database. You'll be asked once on each phone or computer
            you use. Only do this on your own device. You can change or forget them any time under Accounts.
          </p>
          <button className="btn-primary w-full" disabled={!name.trim() || !dob}>Save and continue</button>
          <button type="button" className="w-full text-sm font-semibold text-muted hover:text-ink"
            onClick={() => { skipHintsSetup(); onDone(); }}>
            Skip for now (I'll type passwords when needed)
          </button>
        </form>
      </div>
    </main>
  );
}
