# Personal Expense Tracker & Budget Analytics (Streamlit)

A Streamlit front-end for the expense tracker, backed by SQLite so it runs
anywhere with zero setup.

## Run it

On Windows, use a fresh virtual environment to avoid native DLL issues:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app.py
```

If you prefer, run the bundled helper script:

```powershell
.\install.ps1
```

On first run it creates `expense_tracker.db` in the same folder, seeds it
with your user, three accounts, all categories, some merchants, and a
handful of sample transactions so the dashboard isn't empty.

## Pages

- **Dashboard** — income vs. expenses by month, top 5 expense categories,
  top merchants, and live budget-overrun progress bars.
- **Add Transaction** — form to log income/expense, plus a table of recent
  transactions with delete support.
- **Accounts** — add accounts, view balances, and inspect a running-balance
  chart per account (equivalent to the SQL window-function query).
- **Budgets** — set/update a monthly limit per category (upsert), view all
  budgets.
- **Reports** — category spending trend over time, month-over-month change
  per category, merchant breakdown.
- **Manage** — add new categories/merchants.

## Notes on the MySQL → SQLite translation

- The `add_transaction` stored procedure became a Python function
  (`add_transaction()`) that validates input and updates the account
  balance inside a single DB transaction — same guarantee, no stored
  procedure needed.
- The balance-update `AFTER INSERT` trigger became inline balance math in
  that same function; `delete_transaction()` reverses it, mirroring the
  `AFTER DELETE` trigger from the MySQL version.
- The running-balance window function became a `cumsum()` over a
  chronologically sorted pandas DataFrame — same result, computed in
  Python since it's cheap at this data volume and keeps the app
  dependency-light (no need for SQLite's window-function support).
- Multi-user ready: the sidebar has a user switcher, though the seed data
  only creates one user by default.

## Extending it

- Swap `sqlite3` for `mysql.connector` / `SQLAlchemy` + the original MySQL
  schema if you want to point this at the MySQL version instead — the
  query layer is isolated in the "DATABASE LAYER" section of `app.py`.
- Add authentication (e.g. `streamlit-authenticator`) before deploying
  anywhere multi-user.
