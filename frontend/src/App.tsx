import { useState } from "react";
import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { TransactionForm } from "./components/TransactionForm";
import { useSession } from "./lib/session";
import type { Transaction } from "./lib/types";
import { Accounts } from "./pages/Accounts";
import { Dashboard } from "./pages/Dashboard";
import { Import } from "./pages/Import";
import { Login } from "./pages/Login";
import { Transactions } from "./pages/Transactions";
import { Welcome } from "./pages/Welcome";
import { Sort } from "./pages/Sort";
import { needsHintsSetup } from "./lib/pdfPasswords";

export default function App() {
  const { signedIn, touchData } = useSession();
  const [editing, setEditing] = useState<Transaction | "new" | null>(null);
  const [setup, setSetup] = useState(needsHintsSetup);
  if (!signedIn) return <Login />;
  if (setup) return <Welcome onDone={() => setSetup(false)} />;

  const add = () => setEditing("new");
  return (
    <HashRouter>
      <Layout onAdd={add}>
        <Routes>
          <Route path="/" element={<Dashboard onAdd={add} />} />
          <Route path="/transactions" element={<Transactions onEdit={setEditing} />} />
          <Route path="/accounts" element={<Accounts />} />
          <Route path="/import" element={<Import />} />
          <Route path="/sort" element={<Sort />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
      {editing && (
        <TransactionForm existing={editing === "new" ? undefined : editing}
          onClose={() => setEditing(null)} onSaved={() => { setEditing(null); touchData(); }} />
      )}
    </HashRouter>
  );
}
