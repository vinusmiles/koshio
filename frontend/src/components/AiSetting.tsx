import { useState } from "react";
import { api, json } from "../lib/api";
import { useSession } from "../lib/session";
import type { Me } from "../lib/types";

/** Turn AI category suggestions on or off, with exactly what gets sent. */
export function AiSetting() {
  const { me, setMe } = useSession();
  const [saving, setSaving] = useState(false);
  if (!me) return null;
  if (!me.ai_available) return (
    <p className="text-sm text-muted">
      AI suggestions are off because the server has no AI key. Koshio still uses card merchant categories,
      built-in keywords and your own choices.
    </p>
  );
  async function toggle() {
    setSaving(true);
    try { setMe(await api<Me>("/auth/me", { method: "PATCH", body: json({ ai_categorise: !me!.ai_categorise }) })); }
    finally { setSaving(false); }
  }
  return (
    <div className="space-y-2">
      <label className="flex items-start gap-3">
        <input type="checkbox" className="mt-1 h-5 w-5" checked={me.ai_categorise} disabled={saving} onChange={toggle} />
        <span>
          <span className="font-semibold">Suggest categories with AI</span>
          <span className="block text-sm text-muted">
            When nothing else recognises a payee, Koshio sends only its name (for example "KPN FARM FRESH") to
            Anthropic's Claude to suggest a category. Amounts, dates, account numbers and UPI IDs are never sent,
            and each name is asked about only once.
          </span>
        </span>
      </label>
    </div>
  );
}
