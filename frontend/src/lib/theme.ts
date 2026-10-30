export type ThemePref = "light" | "dark" | "system";
const KEY = "koshio.theme";

export function getTheme(): ThemePref {
  try { return (localStorage.getItem(KEY) as ThemePref) || "system"; } catch { return "system"; }
}

export function applyTheme(pref: ThemePref) {
  try { localStorage.setItem(KEY, pref); } catch { /* ignore */ }
  const dark = pref === "dark" || (pref === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
}
