import { useState, type FormEvent } from "react";
import { forgetHints, loadHints, saveHints, type PdfHints } from "../lib/pdfPasswords";

/** Save or forget the name and date of birth used to open locked statements, on this device only. */
export function PdfHintsForm({ onSaved, compact }: { onSaved?: (h: PdfHints) => void; compact?: boolean }) {
  const [saved, setSaved] = useState<PdfHints | null>(loadHints);
  const [name, setName] = useState(saved?.name ?? "");
  const [dob, setDob] = useState(saved?.dob ?? "");
  const [editing, setEditing] = useState(!saved && !compact);

  function save(e: FormEvent) {
    e.preventDefault();
    const h = { name: name.trim(), dob };
    saveHints(h); setSaved(h); setEditing(false); onSaved?.(h);
  }

  if (saved && !editing) return (
    <div className="space-y-2 text-sm">
      <p>Saved on this device for <span className="font-semibold">{saved.name}</span>. Locked statements open automatically when they use the usual patterns.</p>
      <div className="flex gap-3 font-semibold">
        <button type="button" className="text-muted hover:text-ink" onClick={() => setEditing(true)}>Change</button>
        <button type="button" className="text-muted hover:text-spend" onClick={() => { forgetHints(); setSaved(null); setName(""); setDob(""); }}>
          Forget on this device
        </button>
      </div>
    </div>
  );
  if (!editing) return (
    <button type="button" className="text-sm font-semibold underline" onClick={() => setEditing(true)}>
      Open my statements automatically next time
    </button>
  );
  return (
    <form onSubmit={save} className="space-y-3">
      <p className="text-sm text-muted max-w-prose">
        Card statement passwords are usually built from the name on the card and your date of birth
        (Axis and HDFC: first 4 letters of the name + DDMM; SBI Card: DDMMYYYY + the card's last 4 digits).
        Save them here and Koshio tries those patterns for you. They're kept only in this browser, never in
        Koshio's database. Anyone using this browser could open your statements, so only save them on your own device.
      </p>
      <div className="grid sm:grid-cols-2 gap-3">
        <div>
          <label className="label" htmlFor="hname">Name as printed on your cards</label>
          <input id="hname" className="field" autoComplete="off" required value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="hdob">Date of birth</label>
          <input id="hdob" type="date" className="field" required value={dob} onChange={(e) => setDob(e.target.value)} />
        </div>
      </div>
      <p className="text-xs text-muted">For SBI Card, add the card's last 4 digits under Accounts.</p>
      <div className="flex gap-3">
        <button className="btn-primary" disabled={!name.trim() || !dob}>Save on this device</button>
        {(saved || compact) && <button type="button" className="btn-quiet" onClick={() => setEditing(false)}>Cancel</button>}
      </div>
    </form>
  );
}
