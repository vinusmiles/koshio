# Koshio

**All your spending. One smart view.**

Koshio brings PhonePe, BHIM, bank, card and cash transactions together in one place, without counting anything twice. This repository holds the website (`frontend/`) and the server (`backend/`).

## Status: Phase 2 of 6 complete

| Phase | What | Status |
|---|---|---|
| 1. Foundation | Database, sign-in, accounts, manual transactions, dashboard | Done |
| 2. Statement import | PDF (UPI apps, cards, banks), CSV, XLS, XLSX; preview, column mapping, history, duplicate blocking | Done |
| 3. Analysis | Automatic categories and Quick sort (done); month-on-month, payment-method and merchant charts, bulk edits | In progress |
| 4. Reconciliation | Cross-source duplicate matching, linking transfers and card payments | |
| 5. Advanced | Credit cards page, recurring payments, budgets, reports and exports | |
| 6. Hardening | Final security review, backups, deployment polish | |

### What works now

**Statement import (Phase 2)**
- Upload one or several statements (drag and drop on a computer, file picker on a phone): PDF up to 15 MB, CSV, XLS or XLSX up to 5 MB.
- PDF statements from PhonePe, BHIM, Google Pay and Paytm, credit card statements, and bank statements. Each style has its own reader:
  - UPI apps: date, time, "Paid to" / "Payment to" / "Requested by" / "Received from" name (including names that wrap onto a second line), amount, DEBIT/CREDIT, the UTR, and what paid for it ("Paid by" a bank account, a RuPay credit card, or UPI Lite). Failed or pending payments are set aside. Topping up UPI Lite and "Transfer to" your own account count as transfers, not spending.
  - BHIM: one row per payment with the paying bank account or RuPay card, the receiver's UPI ID, the reference and the status. Payments to your own UPI ID are transfers; failed payments are set aside. A payment from a bank account where BHIM hides the receiver is a credit card bill payment (not spending); the same from a card is treated as an ordinary bill or purchase.
  - Credit cards: one transaction per line, "Cr" marks credits, the amount is the first Dr/Cr number (so Axis's "Cashback earned" column is ignored), reward points are stripped, and summary lines (statement date, due date, total due, minimum due, credit limit) are never taken as transactions.
  - Banks: works out money in or out from the running balance, and joins narrations that wrap onto several lines.
- Password-protected PDFs (most card statements) open automatically when they follow the usual patterns. Right after you sign in on a device, an opening step asks for your full name (as on your cards) and date of birth, or you can skip it. These are saved only in that browser, never in Koshio's database, and can be changed or forgotten under Accounts. When a locked PDF arrives, the browser builds the likely passwords (first 4 letters of the name + DDMM for Axis and HDFC, in capitals and lower case; DDMMYYYY + each card's last 4 digits for SBI Card; DDMMYYYY) and sends them with that upload. The server tries them in memory, reports which one worked, and keeps none of them. If none work, or you skipped the step, Koshio asks you to type the password.
- Scanned image PDFs get a clear message; they can't be read yet.
- The same UPI payment in two statements (for example PhonePe and your bank) is spotted by its 12-digit UPI reference and counted once.
- Every UPI app transaction keeps what actually paid for it (for example "Axis a/c ••0922" or "AU card ••19"), shown in the transactions list. Payment method is set to credit card when a RuPay credit card paid over UPI.
- Koshio finds the heading row even when the bank puts account details above it, works out which column is the date, narration, debit, credit, amount, Dr/Cr flag or reference, and lets you change any of it.
- Reads Indian amounts (1,23,456.78, ₹, Rs., 500.00 Dr, (250.00)) and most date styles (15/10/2026, 15-Oct-26, 2026-10-15, with or without a time). When dates could be read either way, like 04/05/2026, Koshio asks rather than guessing, unless one reading would put transactions in the future.
- Preview before saving: rows found, ready to import, already in Koshio, couldn't be read, and not transactions (opening balances, totals, footers), plus the date range. Untick rows or change their type and category before importing.
- Suggests what each row means: ATM withdrawals and self-transfers as transfers, card bill payments as card payments (so they never count as spending), refunds and reversals, fees and interest, salary. Pulls the merchant or person's name and the 12-digit UPI reference out of HDFC, SBI and ICICI style UPI narrations. Suggests a category from built-in keywords (Swiggy, Zepto, HPCL, TSSPDCL, Netflix and so on), and your own earlier choice for that merchant wins.
- Never imports the same transaction twice: re-importing a file, or overlapping statements, only adds rows that are new. Several identical purchases on the same day (three ₹20 teas) are all kept.
- Rows that couldn't be read are saved with the import so nothing is lost silently, and you can mark them as handled.
- Import history with counts for every file. "Delete import" removes it and every transaction it added, so a bad import is easy to undo.
- The statement file is read in memory and thrown away. Only the transactions are stored.
- Imported transactions start as "To review"; the Transactions page has a To review filter.

**Automatic categories (Phase 3, part 1)**
Every import categorises payments in this order, and each step only handles what the earlier ones couldn't:
1. Your saved rule for that payee (from Quick sort or "use for every payment to this payee").
2. The category you gave that payee or merchant before.
3. Built-in keywords and the merchant category printed on card statements: Groceries, Food, Fuel, Travel, Shopping, Clothing and accessories, Electronics, Utilities, Healthcare, Insurance, Education and more.
4. Optional AI suggestions: names nothing else recognised (for example "KPN FARM FRESH") are sent to Claude, names only, never amounts, dates, account numbers or UPI IDs. Each name is asked about once and cached. It needs `ANTHROPIC_API_KEY` on the server and can be turned off under Accounts. Suggestions are marked "AI suggestion" in the preview.
5. Quick sort for what's left: payments are grouped by payee (the UPI ID when there is one), showing how often and how much you paid. One tap categorises the whole group, saves a rule, and applies it to future statements. The overview shows how many payments still need a category.

Koshio also tells shops from people where the UPI ID shows it (`@fbpe`, `paytm.…@pty`, `vyapar.…@hdfcbank` are shop QR codes; `@okicici`, `@oksbi` and phone-number IDs are personal). Payments where BHIM hides the receiver are never grouped together, since they may be different payees.

**Foundation (Phase 1)**
- Sign-in with email and password. Sign-up closes automatically after the first account, so only you can use your Koshio. Five wrong passwords lock that email for 15 minutes.
- Accounts: bank, credit card, debit card, UPI app, wallet, cash. Only the last four digits of a card are ever accepted.
- Add, edit and delete transactions by hand: spending, income, refunds, transfers between your accounts, credit card bill payments, fees, interest and reimbursements.
- Overview: a plain-language summary of the period, six key figures, last 12 months of spending against income, and spending by category. Periods: this month, last month, last 3 and 6 months, this financial year, last financial year (April to March), or custom dates.
- Transactions list: search, filter by type and category, grouped by date, load more.
- Light, dark and automatic themes. Indian number formatting (₹1,25,000) and dates as 05 Oct 2026, in Indian time.

## How Koshio counts money

Every transaction stores a positive `amount`, a `direction` (debit = money out of or charged to that account, credit = money in), and a `transaction_type` that says what it means. Reports use only the type:

| Type | Counted as |
|---|---|
| expense, fee, interest | Spending |
| refund | Taken off spending (and off its category) |
| income, reimbursement | Income |
| transfer, card_payment | Neither. It's your own money moving |
| adjustment | Ignored by reports |

So a ₹10,000 card purchase plus a ₹10,000 card bill payment is ₹10,000 of spending, not ₹20,000. Rows marked as duplicates of another row are never counted. Net cash flow = income − (spending − refunds).

The card outstanding figure is always labelled an estimate: it's built only from transactions Koshio has seen, not from your card statement (that arrives in Phase 5).

## Architecture

```
Phone / laptop browser
        │  HTTPS
        ▼
GitHub Pages ── static website (React, TypeScript, Vite, Tailwind, Recharts)
        │  HTTPS + sign-in token
        ▼
Render (free) ── API server (Python, FastAPI, SQLAlchemy, Pydantic)
        │  TLS
        ▼
Neon (free) ── Postgres database
```

Your statements and transactions never touch GitHub. The website only holds code; data lives in your Neon database and is only reachable through the API with your sign-in.

### Database tables (Phase 1)
- `users`: email and bcrypt password hash.
- `accounts`: your bank accounts, cards, wallets and cash, with optional last 4 digits.
- `categories`: 17 spending, 3 income and 2 transfer categories, created for you at sign-up.
- `transactions`: the unified record. Keeps your edits (`merchant_name`, `category_id`) separate from what a statement originally said (`raw_description`, `original_merchant_name`). Has slots ready for later phases: `fingerprint` (unique per user, for blocking repeat imports), `duplicate_of_id`, `linked_transaction_id`, `counterparty_account_id`, `import_batch_id`.
- `import_batches`: one row per imported file: account, source, a fingerprint of the file (to warn about re-imports), counts, date range and the column choices used. The file itself is not stored.
- `import_issues`: statement rows that weren't imported, with the row's original cells and the reason.

Repeat imports are blocked by a fingerprint on each imported transaction: account, date, amount, direction, the bank's reference number (or the narration when there's none), and which occurrence it is among identical rows in that file. A database rule makes a fingerprint unique per user, and each import is saved all at once or not at all.

Money is stored as `NUMERIC(14,2)`, never floating point. Database rules enforce positive amounts, valid types and 4-digit card endings. Changes to the tables are made through Alembic migrations in `backend/migrations/`.

## Run it on your computer

You need Python 3.12 and Node 22.

```bash
# Server
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload                         # http://localhost:8000

# Website (second terminal)
cd frontend
npm install
npm run dev                                           # http://localhost:5173
```

## Tests

```bash
cd backend && pytest -q          # 113 tests on SQLite
TEST_DATABASE_URL=postgresql://user:pass@localhost/koshio_test pytest -q   # same tests on Postgres
cd frontend && npm test          # 12 tests (formatting, password patterns, opening step)
```

Tests from the brief covered so far: 1 (100 rows imported), 2 (same statement twice adds nothing), 4 (card purchase plus repayment counts once), 5 (refund nets off), 6 (own transfers aren't spending or income), 7 (date formats, and ambiguous dates must be chosen), 8 (invalid rows reported and kept), 9 (your category choice for a merchant is used on later imports), 11 (identical same-day purchases all kept, also across re-imports), 12 (no access to another user's data or imports), 13 (clear message for unsupported files), 14 (card outstanding always labelled an estimate). Also covered: PhonePe, BHIM, Google Pay, card (with password) and bank PDFs (the PhonePe and BHIM test files copy real layouts with invented details), scanned and fake PDFs, the same UPI payment in PhonePe and bank statements, HDFC, SBI, ICICI and card CSV/Excel shapes, .xls files that are really HTML, semicolon CSVs, overlapping statements, column remapping, row overrides, deleting an import, Indian amount formats, UPI narration parsing, and migrations on Postgres. Still to come: test 3 (PhonePe and card records of the same purchase) with reconciliation in Phase 4, and test 10 with month-on-month analysis in Phase 3.

## Supported statement formats

| Format | Status |
|---|---|
| PDF from PhonePe and BHIM | Supported, checked against real statements |
| PDF from Google Pay, Paytm | Supported (built from the usual layout, not yet checked against a real file) |
| Axis Bank credit card PDF (password-protected) | Supported, checked against a real statement (EMI, GST, BBPS payments, cashback column) |
| Other credit card PDF statements | Supported (one transaction per line, the usual layout) |
| Bank PDF statements with a balance column | Supported |
| PDFs with no text (scanned, or copies made by printing to remove a password) | Not supported; Koshio explains and asks for the original file |
| CSV (comma, semicolon, tab) | Supported |
| Excel .xlsx, .xls, and banks' HTML-table ".xls" downloads | Supported |
| OFX / QFX | Not yet |

PDF layouts differ between banks and apps and change over time. The readers were built for the common layouts and tested on made-up statements in `backend/tests/fixtures/`, which were generated by `backend/tests/make_pdf_fixtures.py`. Real statements may need small adjustments: if one reads wrongly, the preview shows exactly what Koshio understood before anything is saved.

## Put it online

Do these in order. None needs a credit card.

**1. Database (Neon)**
1. Sign up at neon.com and create a project called `koshio`. Pick the Singapore region (closest to India).
2. Copy the connection string (it starts with `postgresql://` and ends with `?sslmode=require`).

**2. Code (GitHub)**
1. Create a new repository called `koshio` and upload everything in this folder.
2. The repository can be public: it holds only code, no data or secrets. (GitHub Pages on a private repository needs a paid plan.)

**3. Server (Render)**
1. Sign up at render.com with your GitHub account.
2. New → Blueprint → choose the `koshio` repository. Render reads `render.yaml`.
3. When asked, set `DATABASE_URL` to the Neon string and `CORS_ORIGINS` to `https://vinusmiles.github.io`.
4. Wait for the deploy, then open `https://<your-service>.onrender.com/health`. It should say `{"status":"ok"}`.

**4. Website (GitHub Pages)**
1. In the repository: Settings → Secrets and variables → Actions → Variables → New variable. Name `KOSHIO_API_URL`, value your Render address, e.g. `https://koshio-api.onrender.com`.
2. Settings → Pages → Source: GitHub Actions.
3. Actions → "Deploy website to GitHub Pages" → Run workflow.
4. Open `https://vinusmiles.github.io/koshio/`.

**5. Create your account straight away.** Sign-up is open until the first account exists. Once you've signed up, go to Render → Environment and set `ALLOW_REGISTRATION=false` to close it completely.

The free Render server sleeps after 15 minutes without use, and the first visit after that takes about a minute; Koshio shows a "Waking up the server" note while it waits. Upgrading the Render service to the $7/month instance keeps it awake. Neon's free database also pauses when idle but wakes in about a second.

## Backups

- Neon keeps a short restore window on the free plan (a few hours), which helps with accidental deletes but isn't a long-term backup.
- For a real backup, run this from any computer with Postgres tools installed:
  `pg_dump "<neon connection string>" --format=custom --file=koshio-$(date +%F).dump`
- To restore into a fresh Neon database: `pg_restore --no-owner --dbname="<new connection string>" koshio-YYYY-MM-DD.dump`
- Keep backup files somewhere private. They contain all your transactions.
- Phase 5 adds a one-click export of everything to CSV and Excel.
- Keep your original statement downloads too. Koshio doesn't store them, and re-importing them later is safe.

## Security in Phase 1
- Passwords hashed with bcrypt. Sign-in tokens expire after 12 hours.
- Every request checks that the data belongs to the signed-in user. Other users' records behave exactly like missing ones (404).
- The API only accepts requests from the address in `CORS_ORIGINS`, sends `Cache-Control: no-store`, hides its interactive docs in production, and refuses to start in production without a strong `JWT_SECRET`.
- Errors are logged by type and path only, never with transaction details.
- The website asks search engines not to index it.

### Known limitations
- The sign-in token is kept in the browser's local storage, because the website and server are on different domains and phones block cross-site cookies. This is standard for this setup, but it means a malicious script on the page could read it. The website loads no third-party scripts apart from Google Fonts.
- The wrong-password lockout is held in server memory, so it resets when the free server restarts.
- No password reset yet. If you forget your password, it can be reset directly in the database (ask for the steps).
- Scanned PDFs can't be read. PDF readers cover the common layouts; an unusual layout may need adjusting.
- Each import belongs to one account. UPI app statements mix several paying accounts and cards; Koshio records which one paid, but assigning those payments to the matching bank or card account comes with reconciliation (Phase 4).
- A UPI payment made with a RuPay credit card also appears on that card's statement. Until reconciliation (Phase 4), importing both the UPI app statement and that card statement for the same period counts those payments twice.
- Category suggestions use built-in keywords plus your past choices; editable rules arrive in Phase 3.
- Reconciliation across sources (PhonePe vs bank vs card), bulk review, budgets, recurring payments and exports are not built yet (Phases 3–5).
