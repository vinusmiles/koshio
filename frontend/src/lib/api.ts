const BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");
const TOKEN_KEY = "koshio.token";

export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string) { super(message); }
}

export const tokenStore = {
  get: () => { try { return localStorage.getItem(TOKEN_KEY); } catch { return null; } },
  set: (t: string) => { try { localStorage.setItem(TOKEN_KEY, t); } catch { /* private mode */ } },
  clear: () => { try { localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ } },
};

// The free server sleeps when idle; tell the UI when a request is taking a while.
type SlowListener = (slow: boolean) => void;
const slowListeners = new Set<SlowListener>();
let pending = 0;
export function onSlow(fn: SlowListener) { slowListeners.add(fn); return () => { slowListeners.delete(fn); }; }

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) { onUnauthorized = fn; }

function messageFrom(body: unknown, status: number): string {
  const d = (body as { detail?: unknown })?.detail;
  if (typeof d === "string") return d;
  if (d && typeof d === "object" && "message" in d) return String((d as { message: unknown }).message);
  if (Array.isArray(d) && d.length) {
    return d.map((e: { msg?: string }) => (e.msg || "").replace(/^Value error, /, "")).filter(Boolean).join(" ");
  }
  return status >= 500 ? "The server had a problem. Try again in a moment." : `Request failed (${status}).`;
}

export async function api<T>(path: string, init: RequestInit & { query?: Record<string, unknown> } = {}): Promise<T> {
  const url = new URL(BASE + path);
  for (const [k, v] of Object.entries(init.query ?? {})) {
    if (v === undefined || v === null || v === "") continue;
    (Array.isArray(v) ? v : [v]).forEach((x) => url.searchParams.append(k, String(x)));
  }
  const isForm = init.body instanceof FormData;  // the browser sets the multipart boundary itself
  const headers: Record<string, string> = isForm ? {} : { "Content-Type": "application/json" };
  const token = tokenStore.get();
  if (token) headers.Authorization = `Bearer ${token}`;

  pending++;
  const timer = setTimeout(() => slowListeners.forEach((f) => f(true)), 4000);
  let res: Response;
  try {
    res = await fetch(url, { ...init, headers, cache: "no-store" });
  } catch {
    throw new ApiError(0, "Couldn't reach the Koshio server. Check your connection and try again.");
  } finally {
    clearTimeout(timer);
    if (--pending === 0) slowListeners.forEach((f) => f(false));
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401 && token) { tokenStore.clear(); onUnauthorized(); }
    const d = (body as { detail?: { code?: string } } | null)?.detail;
    throw new ApiError(res.status, messageFrom(body, res.status), typeof d === "object" && d ? d.code : undefined);
  }
  return body as T;
}

export const json = (data: unknown) => JSON.stringify(data);
