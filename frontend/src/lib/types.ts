export type TxnType = "expense" | "income" | "refund" | "transfer" | "card_payment" | "fee" | "interest" | "reimbursement" | "adjustment";
export type PaymentMethod = "upi" | "credit_card" | "debit_card" | "bank_transfer" | "cash" | "other";
export type AccountType = "bank" | "credit_card" | "debit_card" | "upi" | "wallet" | "cash" | "other";

export interface Account { id: number; name: string; account_type: AccountType; institution: string | null; last4: string | null }
export interface Category { id: number; name: string; kind: "expense" | "income" | "transfer"; parent_id: number | null }

export interface Transaction {
  id: number; transaction_date: string; amount: string; currency: string;
  direction: "debit" | "credit"; transaction_type: TxnType; payment_method: PaymentMethod;
  source_provider: string; origin: "manual" | "import";
  merchant_name: string | null; original_merchant_name: string | null;
  description: string | null; raw_description: string | null;
  category_id: number | null; category_name: string | null;
  account_id: number | null; account_name: string | null; counterparty_account_id: number | null;
  funding_source: string | null;
  notes: string | null; is_transfer: boolean; is_refund: boolean; is_reviewed: boolean;
  import_batch_id: number | null; created_at: string; updated_at: string;
}
export interface TransactionPage { items: Transaction[]; total: number; page: number; page_size: number }

export interface Summary {
  period: { preset: string; start: string; end: string; label: string };
  total_expenses: string; total_refunds: string; net_expenses: string;
  total_income: string; net_cash_flow: string;
  transaction_count: number; unreviewed_count: number;
  credit_card_outstanding: { amount: string | null; is_estimate: boolean; note: string };
}
export interface MonthPoint { month: string; expenses: string; income: string }
export interface CategoryPoint { category_id: number | null; name: string; amount: string }

export const TYPE_LABELS: Record<TxnType, string> = {
  expense: "Spent", income: "Income", refund: "Refund", transfer: "Transfer",
  card_payment: "Card bill payment", fee: "Fee or charge", interest: "Interest charged",
  reimbursement: "Reimbursement", adjustment: "Adjustment",
};
export const METHOD_LABELS: Record<PaymentMethod, string> = {
  upi: "UPI", credit_card: "Credit card", debit_card: "Debit card",
  bank_transfer: "Bank transfer", cash: "Cash", other: "Other",
};
export const ACCOUNT_LABELS: Record<AccountType, string> = {
  bank: "Bank account", credit_card: "Credit card", debit_card: "Debit card",
  upi: "UPI app", wallet: "Wallet", cash: "Cash", other: "Other",
};
/** Types that count as money going out / in, for colouring the list. */
export const OUTFLOW: TxnType[] = ["expense", "fee", "interest"];
export const INFLOW: TxnType[] = ["income", "refund", "reimbursement"];

export type Field = "date" | "time" | "description" | "merchant" | "reference" | "debit" | "credit" | "amount" | "dr_cr" | "balance";
export type Source = "phonepe" | "bhim" | "other_upi" | "bank" | "credit_card" | "debit_card" | "cash_ledger" | "other";
export const SOURCE_LABELS: Record<Source, string> = {
  bank: "Bank account statement", credit_card: "Credit card statement", debit_card: "Debit card statement",
  phonepe: "PhonePe", bhim: "BHIM", other_upi: "Other UPI app", cash_ledger: "Cash ledger", other: "Other",
};

export interface PreviewRow {
  row_number: number; status: "ready" | "duplicate" | "invalid" | "unrecognised"; message: string | null;
  transaction_date: string | null; time: string | null; description: string | null; merchant_name: string | null;
  amount: string | null; direction: "debit" | "credit" | null; transaction_type: TxnType | null;
  category_id: number | null; reference: string | null; upi_reference: string | null; funding_source: string | null; raw: string[];
}
export interface Preview {
  header_row: number | null; columns: string[]; mapping: Record<Field, number | null>;
  date_format: string | null; date_format_options: string[]; date_format_ambiguous: boolean;
  amount_sign: "negative_is_debit" | "positive_is_debit" | null; needs_amount_sign: boolean;
  suggested_source: Source; problems: string[]; rows: PreviewRow[];
  counts: { detected: number; ready: number; duplicate: number; invalid: number; unrecognised: number };
  date_from: string | null; date_to: string | null; top_rows: string[][];
  previous_import: { id: number; created_at: string; records_imported: number } | null;
}
export interface ImportBatch {
  id: number; filename: string; source_provider: Source; status: "completed" | "completed_with_issues" | "nothing_new";
  account_id: number | null; account_name: string | null; records_detected: number; records_imported: number;
  records_duplicate: number; records_failed: number; records_unrecognised: number; records_skipped: number;
  date_from: string | null; date_to: string | null; created_at: string; open_issues?: number;
}
export interface ImportIssue { id: number; row_number: number; kind: "invalid" | "unrecognised"; message: string; raw: string[]; resolved: boolean }
