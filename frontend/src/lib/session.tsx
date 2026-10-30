import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, setUnauthorizedHandler, tokenStore } from "./api";
import type { Account, Category } from "./types";

interface Session {
  signedIn: boolean;
  email: string | null;
  accounts: Account[];
  categories: Category[];
  signIn: (token: string) => Promise<void>;
  signOut: () => void;
  reloadAccounts: () => Promise<void>;
  /** Bumped whenever transactions change, so pages know to refetch. */
  dataVersion: number;
  touchData: () => void;
}

const Ctx = createContext<Session | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [signedIn, setSignedIn] = useState(() => !!tokenStore.get());
  const [email, setEmail] = useState<string | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [dataVersion, setDataVersion] = useState(0);

  const signOut = useCallback(() => {
    tokenStore.clear();
    setSignedIn(false); setEmail(null); setAccounts([]); setCategories([]);
  }, []);

  const reloadAccounts = useCallback(async () => {
    setAccounts(await api<Account[]>("/accounts"));
  }, []);

  const load = useCallback(async () => {
    const [me, accs, cats] = await Promise.all([
      api<{ email: string }>("/auth/me"), api<Account[]>("/accounts"), api<Category[]>("/categories"),
    ]);
    setEmail(me.email); setAccounts(accs); setCategories(cats);
  }, []);

  useEffect(() => { setUnauthorizedHandler(signOut); }, [signOut]);
  useEffect(() => { if (signedIn) load().catch(() => {}); }, [signedIn, load]);

  const signIn = useCallback(async (token: string) => {
    tokenStore.set(token);
    setSignedIn(true);
  }, []);

  return (
    <Ctx.Provider value={{ signedIn, email, accounts, categories, signIn, signOut, reloadAccounts,
      dataVersion, touchData: () => setDataVersion((v) => v + 1) }}>
      {children}
    </Ctx.Provider>
  );
}

export function useSession() {
  const s = useContext(Ctx);
  if (!s) throw new Error("useSession outside SessionProvider");
  return s;
}
