"""
Personal Expense Tracker & Budget Analytics
--------------------------------------------
A Streamlit front-end for the expense tracker database.

Storage: SQLite (expense_tracker.db, created automatically on first run).
The schema mirrors the MySQL version (users / accounts / categories /
merchants / transactions / budgets) but is adapted to SQLite so the whole
thing runs with zero external setup - just `streamlit run app.py`.

Run:
    pip install -r requirements.txt
    streamlit run app.py
"""

import sqlite3
from datetime import date, datetime
from contextlib import closing

import pandas as pd
import streamlit as st

DB_PATH = "expense_tracker.db"

st.set_page_config(
    page_title="Expense Tracker & Budget Analytics",
    page_icon="💰",
    layout="wide",
)

# ============================================================
# DATABASE LAYER
# ============================================================

@st.cache_resource
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            email       TEXT NOT NULL UNIQUE,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS accounts (
            account_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            account_name    TEXT NOT NULL,
            account_type    TEXT NOT NULL CHECK (account_type IN ('cash','bank','credit_card')),
            balance         REAL NOT NULL DEFAULT 0,
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS categories (
            category_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name   TEXT NOT NULL,
            category_type   TEXT NOT NULL CHECK (category_type IN ('income','expense')),
            UNIQUE (category_name, category_type)
        );

        CREATE TABLE IF NOT EXISTS merchants (
            merchant_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_name   TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id              INTEGER NOT NULL,
            account_id           INTEGER NOT NULL,
            category_id          INTEGER NOT NULL,
            merchant_id          INTEGER,
            amount               REAL NOT NULL CHECK (amount > 0),
            transaction_type     TEXT NOT NULL CHECK (transaction_type IN ('income','expense')),
            transaction_date    TEXT NOT NULL,
            notes                TEXT,
            created_at           TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(category_id),
            FOREIGN KEY (merchant_id) REFERENCES merchants(merchant_id)
        );

        CREATE TABLE IF NOT EXISTS budgets (
            budget_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            category_id     INTEGER NOT NULL,
            budget_month    INTEGER NOT NULL CHECK (budget_month BETWEEN 1 AND 12),
            budget_year     INTEGER NOT NULL,
            budget_limit    REAL NOT NULL CHECK (budget_limit >= 0),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(category_id),
            UNIQUE (user_id, category_id, budget_month, budget_year)
        );
        """
    )
    conn.commit()
    seed_if_empty()


def seed_if_empty():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM users")
    if cur.fetchone()["c"] > 0:
        return  # already seeded

    cur.execute("INSERT INTO users (name, email) VALUES ('Muhammad Junaid', 'junaid@example.com')")
    user_id = cur.lastrowid

    cur.executemany(
        "INSERT INTO accounts (user_id, account_name, account_type, balance) VALUES (?,?,?,0)",
        [
            (user_id, "Meezan Bank", "bank"),
            (user_id, "Cash Wallet", "cash"),
            (user_id, "HBL Credit Card", "credit_card"),
        ],
    )

    cur.executemany(
        "INSERT INTO categories (category_name, category_type) VALUES (?,?)",
        [
            ("Salary", "income"),
            ("Freelance Income", "income"),
            ("Food & Dining", "expense"),
            ("Transport", "expense"),
            ("Bills & Utilities", "expense"),
            ("Entertainment", "expense"),
            ("Shopping", "expense"),
            ("Health", "expense"),
            ("Education", "expense"),
        ],
    )

    cur.executemany(
        "INSERT INTO merchants (merchant_name) VALUES (?)",
        [("Foodpanda",), ("Careem",), ("K-Electric",), ("Daraz",),
         ("Cinepax",), ("Chase Up",), ("Local Pharmacy",), ("Coursera",)],
    )
    conn.commit()

    # a couple of sample transactions so the dashboard isn't empty on first run
    accounts = {r["account_name"]: r["account_id"] for r in cur.execute("SELECT * FROM accounts")}
    categories = {r["category_name"]: r["category_id"] for r in cur.execute("SELECT * FROM categories")}
    merchants = {r["merchant_name"]: r["merchant_id"] for r in cur.execute("SELECT * FROM merchants")}

    sample = [
        (user_id, accounts["Meezan Bank"], categories["Salary"], None, 150000, "income", "2026-07-01", "July salary"),
        (user_id, accounts["Cash Wallet"], categories["Food & Dining"], merchants["Foodpanda"], 2200, "expense", "2026-07-02", "Dinner order"),
        (user_id, accounts["Cash Wallet"], categories["Transport"], merchants["Careem"], 1500, "expense", "2026-07-05", "Ride to office"),
        (user_id, accounts["Meezan Bank"], categories["Bills & Utilities"], merchants["K-Electric"], 8500, "expense", "2026-07-07", "Electricity bill"),
        (user_id, accounts["HBL Credit Card"], categories["Shopping"], merchants["Daraz"], 18000, "expense", "2026-07-11", "Shopping spree"),
    ]
    for txn in sample:
        add_transaction(*txn, seeding=True)


def add_transaction(user_id, account_id, category_id, merchant_id, amount,
                     transaction_type, transaction_date, notes, seeding=False):
    """Equivalent of the MySQL add_transaction stored procedure:
    validates input, inserts the row, and updates the account balance
    atomically."""
    conn = get_connection()
    cur = conn.cursor()

    if amount is None or amount <= 0:
        raise ValueError("Transaction amount must be greater than zero.")

    owner = cur.execute("SELECT user_id FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
    if owner is None:
        raise ValueError("Account does not exist.")
    if owner["user_id"] != user_id:
        raise ValueError("Account does not belong to this user.")

    try:
        cur.execute("BEGIN")
        cur.execute(
            """INSERT INTO transactions
               (user_id, account_id, category_id, merchant_id, amount,
                transaction_type, transaction_date, notes)
               VALUES (?,?,?,?,?,?,?,?)""",
            (user_id, account_id, category_id, merchant_id, amount,
             transaction_type, transaction_date, notes),
        )
        delta = amount if transaction_type == "income" else -amount
        cur.execute(
            "UPDATE accounts SET balance = balance + ? WHERE account_id = ?",
            (delta, account_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    if not seeding:
        st.cache_data.clear()

    return cur.lastrowid


def delete_transaction(transaction_id):
    """Removes a transaction and reverses its effect on the account balance
    (mirrors the AFTER DELETE trigger in the MySQL version)."""
    conn = get_connection()
    cur = conn.cursor()
    txn = cur.execute("SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,)).fetchone()
    if txn is None:
        return
    try:
        cur.execute("BEGIN")
        reverse_delta = -txn["amount"] if txn["transaction_type"] == "income" else txn["amount"]
        cur.execute("UPDATE accounts SET balance = balance + ? WHERE account_id = ?",
                    (reverse_delta, txn["account_id"]))
        cur.execute("DELETE FROM transactions WHERE transaction_id = ?", (transaction_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    st.cache_data.clear()


# ---------- read helpers (cached, cleared whenever data changes) ----------

@st.cache_data
def df(query, params=()):
    conn = get_connection()
    return pd.read_sql_query(query, conn, params=params)


def users_df():
    return df("SELECT * FROM users")


def accounts_df(user_id):
    return df("SELECT * FROM accounts WHERE user_id = ? ORDER BY account_name", (user_id,))


def categories_df(category_type=None):
    if category_type:
        return df("SELECT * FROM categories WHERE category_type = ? ORDER BY category_name", (category_type,))
    return df("SELECT * FROM categories ORDER BY category_type, category_name")


def merchants_df():
    return df("SELECT * FROM merchants ORDER BY merchant_name")


def transactions_df(user_id):
    return df(
        """
        SELECT t.transaction_id, t.transaction_date, t.transaction_type,
               t.amount, a.account_name, c.category_name,
               m.merchant_name, t.notes
        FROM transactions t
        JOIN accounts a ON a.account_id = t.account_id
        JOIN categories c ON c.category_id = t.category_id
        LEFT JOIN merchants m ON m.merchant_id = t.merchant_id
        WHERE t.user_id = ?
        ORDER BY t.transaction_date DESC, t.transaction_id DESC
        """,
        (user_id,),
    )


def monthly_dashboard_df(user_id):
    return df(
        """
        SELECT strftime('%Y', transaction_date) AS txn_year,
               strftime('%m', transaction_date) AS txn_month,
               SUM(CASE WHEN transaction_type='income' THEN amount ELSE 0 END) AS total_income,
               SUM(CASE WHEN transaction_type='expense' THEN amount ELSE 0 END) AS total_expense
        FROM transactions
        WHERE user_id = ?
        GROUP BY txn_year, txn_month
        ORDER BY txn_year, txn_month
        """,
        (user_id,),
    )


def category_spending_df(user_id, year=None, month=None):
    query = """
        SELECT strftime('%Y', t.transaction_date) AS txn_year,
               strftime('%m', t.transaction_date) AS txn_month,
               c.category_id, c.category_name,
               SUM(t.amount) AS total_spent,
               COUNT(*) AS txn_count
        FROM transactions t
        JOIN categories c ON c.category_id = t.category_id
        WHERE t.user_id = ? AND t.transaction_type = 'expense'
    """
    params = [user_id]
    if year:
        query += " AND strftime('%Y', t.transaction_date) = ?"
        params.append(str(year))
    if month:
        query += " AND strftime('%m', t.transaction_date) = ?"
        params.append(f"{month:02d}")
    query += " GROUP BY txn_year, txn_month, c.category_id, c.category_name"
    return df(query, tuple(params))


def merchant_spending_df(user_id):
    return df(
        """
        SELECT m.merchant_name, SUM(t.amount) AS total_spent, COUNT(*) AS txn_count,
               MAX(t.transaction_date) AS last_purchase
        FROM transactions t
        JOIN merchants m ON m.merchant_id = t.merchant_id
        WHERE t.user_id = ? AND t.transaction_type = 'expense'
        GROUP BY m.merchant_name
        ORDER BY total_spent DESC
        """,
        (user_id,),
    )


def budgets_df(user_id):
    return df(
        """
        SELECT b.budget_id, c.category_name, b.category_id, b.budget_month, b.budget_year, b.budget_limit
        FROM budgets b
        JOIN categories c ON c.category_id = b.category_id
        WHERE b.user_id = ?
        ORDER BY b.budget_year DESC, b.budget_month DESC, c.category_name
        """,
        (user_id,),
    )


def budget_status_df(user_id, year, month):
    b = df(
        """
        SELECT b.budget_id, c.category_id, c.category_name, b.budget_limit
        FROM budgets b
        JOIN categories c ON c.category_id = b.category_id
        WHERE b.user_id = ? AND b.budget_year = ? AND b.budget_month = ?
        """,
        (user_id, year, month),
    )
    spend = category_spending_df(user_id, year, month)
    merged = b.merge(spend[["category_id", "total_spent"]], on="category_id", how="left")
    merged["total_spent"] = merged["total_spent"].fillna(0)
    merged["overrun_amount"] = merged["total_spent"] - merged["budget_limit"]

    def status(row):
        if row["budget_limit"] == 0:
            return "OK"
        pct = row["total_spent"] / row["budget_limit"]
        if pct > 1:
            return "OVER BUDGET"
        if pct >= 0.9:
            return "NEAR LIMIT"
        return "OK"

    merged["status"] = merged.apply(status, axis=1)
    return merged


def running_balance_df(user_id, account_id):
    data = df(
        """
        SELECT transaction_date, transaction_id, transaction_type, amount
        FROM transactions
        WHERE user_id = ? AND account_id = ?
        ORDER BY transaction_date, transaction_id
        """,
        (user_id, account_id),
    )
    if data.empty:
        return data
    data["signed_amount"] = data.apply(
        lambda r: r["amount"] if r["transaction_type"] == "income" else -r["amount"], axis=1
    )
    data["running_balance"] = data["signed_amount"].cumsum()
    return data


def add_category(name, category_type):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO categories (category_name, category_type) VALUES (?, ?)",
        (name, category_type),
    )
    conn.commit()
    st.cache_data.clear()


def add_merchant(name):
    conn = get_connection()
    conn.execute("INSERT OR IGNORE INTO merchants (merchant_name) VALUES (?)", (name,))
    conn.commit()
    st.cache_data.clear()


def add_budget(user_id, category_id, month, year, limit_):
    conn = get_connection()
    conn.execute(
        """INSERT INTO budgets (user_id, category_id, budget_month, budget_year, budget_limit)
           VALUES (?,?,?,?,?)
           ON CONFLICT(user_id, category_id, budget_month, budget_year)
           DO UPDATE SET budget_limit = excluded.budget_limit""",
        (user_id, category_id, month, year, limit_),
    )
    conn.commit()
    st.cache_data.clear()


def add_account(user_id, name, acc_type):
    conn = get_connection()
    conn.execute(
        "INSERT INTO accounts (user_id, account_name, account_type, balance) VALUES (?,?,?,0)",
        (user_id, name, acc_type),
    )
    conn.commit()
    st.cache_data.clear()


# ============================================================
# UI
# ============================================================

MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]


def money(x):
    return f"Rs {x:,.0f}"


def sidebar_user_select():
    users = users_df()
    if users.empty:
        st.error("No users found.")
        st.stop()
    labels = users["name"] + " (" + users["email"] + ")"
    idx = st.sidebar.selectbox("User", range(len(users)), format_func=lambda i: labels.iloc[i])
    return int(users.iloc[idx]["user_id"])


def dashboard_page(user_id):
    st.title("📊 Dashboard")

    md = monthly_dashboard_df(user_id)
    if md.empty:
        st.info("No transactions yet — add one from the 'Add Transaction' page.")
        return

    latest = md.iloc[-1]
    year, month = int(latest["txn_year"]), int(latest["txn_month"])

    col1, col2, col3 = st.columns(3)
    col1.metric(f"Income — {MONTH_NAMES[month]} {year}", money(latest["total_income"]))
    col2.metric(f"Expenses — {MONTH_NAMES[month]} {year}", money(latest["total_expense"]))
    net = latest["total_income"] - latest["total_expense"]
    col3.metric("Net Savings", money(net), delta=f"{(net/latest['total_income']*100):.1f}% of income" if latest["total_income"] else None)

    st.subheader("Income vs Expenses by Month")
    chart_df = md.copy()
    chart_df["period"] = chart_df["txn_year"] + "-" + chart_df["txn_month"]
    chart_df = chart_df.set_index("period")[["total_income", "total_expense"]]
    chart_df.columns = ["Income", "Expense"]
    st.bar_chart(chart_df)

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader(f"Top 5 Expense Categories — {MONTH_NAMES[month]} {year}")
        cat = category_spending_df(user_id, year, month).sort_values("total_spent", ascending=False).head(5)
        if cat.empty:
            st.write("No expenses recorded this month.")
        else:
            st.bar_chart(cat.set_index("category_name")["total_spent"])

    with col_b:
        st.subheader("Spending by Merchant")
        merch = merchant_spending_df(user_id).head(5)
        if merch.empty:
            st.write("No merchant data yet.")
        else:
            st.bar_chart(merch.set_index("merchant_name")["total_spent"])

    st.subheader(f"Budget Alerts — {MONTH_NAMES[month]} {year}")
    status = budget_status_df(user_id, year, month)
    if status.empty:
        st.write("No budgets set for this month. Set some on the Budgets page.")
    else:
        for _, row in status.iterrows():
            pct = min(row["total_spent"] / row["budget_limit"], 1.5) if row["budget_limit"] else 0
            label = f"{row['category_name']}: {money(row['total_spent'])} / {money(row['budget_limit'])}"
            if row["status"] == "OVER BUDGET":
                st.progress(min(pct, 1.0), text=f"🔴 {label} — over by {money(row['overrun_amount'])}")
            elif row["status"] == "NEAR LIMIT":
                st.progress(min(pct, 1.0), text=f"🟠 {label} — near limit")
            else:
                st.progress(min(pct, 1.0), text=f"🟢 {label}")


def add_transaction_page(user_id):
    st.title("➕ Add Transaction")

    accounts = accounts_df(user_id)
    merchants = merchants_df()

    if accounts.empty:
        st.warning("Add an account first (see the Accounts page).")
        return

    txn_type = st.radio("Type", ["expense", "income"], horizontal=True)
    categories = categories_df(txn_type)
    if categories.empty:
        st.warning(f"No {txn_type} categories yet. Add one on the Manage page.")
        return

    with st.form("add_transaction_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            account_label = st.selectbox("Account", accounts["account_name"])
            category_label = st.selectbox("Category", categories["category_name"])
            amount = st.number_input("Amount", min_value=0.0, step=100.0, format="%.2f")
        with c2:
            txn_date = st.date_input("Date", value=date.today())
            merchant_label = st.selectbox("Merchant (optional)", ["— none —"] + list(merchants["merchant_name"]))
            notes = st.text_input("Notes")

        submitted = st.form_submit_button("Save Transaction", use_container_width=True)

        if submitted:
            account_id = int(accounts.loc[accounts["account_name"] == account_label, "account_id"].iloc[0])
            category_id = int(categories.loc[categories["category_name"] == category_label, "category_id"].iloc[0])
            merchant_id = None
            if merchant_label != "— none —":
                merchant_id = int(merchants.loc[merchants["merchant_name"] == merchant_label, "merchant_id"].iloc[0])
            try:
                add_transaction(user_id, account_id, category_id, merchant_id, amount,
                                 txn_type, txn_date.isoformat(), notes)
                st.success("Transaction saved.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    st.subheader("Recent Transactions")
    tdf = transactions_df(user_id).head(15)
    st.dataframe(tdf, use_container_width=True, hide_index=True)

    if not tdf.empty:
        del_id = st.selectbox(
            "Delete a transaction",
            tdf["transaction_id"],
            format_func=lambda i: f"#{i} — " + tdf.loc[tdf['transaction_id'] == i, 'notes'].fillna('').iloc[0],
        )
        if st.button("Delete selected transaction"):
            delete_transaction(int(del_id))
            st.success("Deleted.")
            st.rerun()


def accounts_page(user_id):
    st.title("🏦 Accounts")

    accts = accounts_df(user_id)
    if not accts.empty:
        display = accts[["account_name", "account_type", "balance"]].copy()
        display["balance"] = display["balance"].map(money)
        st.dataframe(display, use_container_width=True, hide_index=True)

    st.subheader("Add Account")
    with st.form("add_account_form", clear_on_submit=True):
        name = st.text_input("Account name")
        acc_type = st.selectbox("Type", ["cash", "bank", "credit_card"])
        if st.form_submit_button("Add Account"):
            if name.strip():
                add_account(user_id, name.strip(), acc_type)
                st.success("Account added.")
                st.rerun()
            else:
                st.error("Enter an account name.")

    st.subheader("Running Balance (audit view)")
    if not accts.empty:
        acc_label = st.selectbox("Choose account", accts["account_name"], key="running_balance_acc")
        acc_id = int(accts.loc[accts["account_name"] == acc_label, "account_id"].iloc[0])
        rb = running_balance_df(user_id, acc_id)
        if rb.empty:
            st.write("No transactions on this account yet.")
        else:
            st.line_chart(rb.set_index("transaction_date")["running_balance"])
            st.dataframe(rb[["transaction_date", "transaction_type", "amount", "running_balance"]],
                         use_container_width=True, hide_index=True)


def budgets_page(user_id):
    st.title("🎯 Budgets")

    st.subheader("Set / Update a Budget")
    exp_categories = categories_df("expense")
    with st.form("budget_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            cat_label = st.selectbox("Category", exp_categories["category_name"])
        with c2:
            month = st.selectbox("Month", range(1, 13), format_func=lambda m: MONTH_NAMES[m],
                                  index=date.today().month - 1)
        with c3:
            year = st.number_input("Year", min_value=2020, max_value=2100, value=date.today().year, step=1)
        limit_ = st.number_input("Monthly limit", min_value=0.0, step=500.0, format="%.2f")
        if st.form_submit_button("Save Budget"):
            cat_id = int(exp_categories.loc[exp_categories["category_name"] == cat_label, "category_id"].iloc[0])
            add_budget(user_id, cat_id, month, year, limit_)
            st.success("Budget saved.")
            st.rerun()

    st.subheader("All Budgets")
    b = budgets_df(user_id)
    if b.empty:
        st.write("No budgets set yet.")
    else:
        b_display = b.copy()
        b_display["month"] = b_display["budget_month"].map(lambda m: MONTH_NAMES[m])
        st.dataframe(
            b_display[["category_name", "month", "budget_year", "budget_limit"]]
            .rename(columns={"category_name": "Category", "budget_year": "Year", "budget_limit": "Limit"}),
            use_container_width=True, hide_index=True,
        )


def reports_page(user_id):
    st.title("📈 Reports")

    st.subheader("Category Spending Trend (month over month)")
    md = monthly_dashboard_df(user_id)
    if md.empty:
        st.info("No data yet.")
        return

    cat_all = category_spending_df(user_id)
    if cat_all.empty:
        st.write("No expense data yet.")
    else:
        cat_all["period"] = cat_all["txn_year"] + "-" + cat_all["txn_month"]
        pivot = cat_all.pivot_table(index="period", columns="category_name", values="total_spent", fill_value=0)
        st.line_chart(pivot)

        st.subheader("Change vs Previous Month")
        trend = cat_all.sort_values(["category_name", "period"]).copy()
        trend["prev_month_spent"] = trend.groupby("category_name")["total_spent"].shift(1)
        trend["change_vs_prev_month"] = trend["total_spent"] - trend["prev_month_spent"]
        st.dataframe(
            trend[["period", "category_name", "total_spent", "prev_month_spent", "change_vs_prev_month"]]
            .rename(columns={"period": "Period", "category_name": "Category", "total_spent": "Spent",
                              "prev_month_spent": "Prev Month", "change_vs_prev_month": "Change"}),
            use_container_width=True, hide_index=True,
        )

    st.subheader("Merchant Breakdown")
    merch = merchant_spending_df(user_id)
    st.dataframe(merch, use_container_width=True, hide_index=True)


def manage_page(user_id):
    st.title("⚙️ Manage Categories & Merchants")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Add Category")
        with st.form("add_cat_form", clear_on_submit=True):
            name = st.text_input("Category name")
            ctype = st.selectbox("Type", ["expense", "income"])
            if st.form_submit_button("Add"):
                if name.strip():
                    add_category(name.strip(), ctype)
                    st.success("Category added.")
                    st.rerun()
        st.dataframe(categories_df(), use_container_width=True, hide_index=True)

    with c2:
        st.subheader("Add Merchant")
        with st.form("add_merchant_form", clear_on_submit=True):
            name = st.text_input("Merchant name")
            if st.form_submit_button("Add"):
                if name.strip():
                    add_merchant(name.strip())
                    st.success("Merchant added.")
                    st.rerun()
        st.dataframe(merchants_df(), use_container_width=True, hide_index=True)


def main():
    init_db()
    st.sidebar.title("💰 Expense Tracker")
    user_id = sidebar_user_select()
    page = st.sidebar.radio(
        "Go to",
        ["Dashboard", "Add Transaction", "Accounts", "Budgets", "Reports", "Manage"],
    )

    if page == "Dashboard":
        dashboard_page(user_id)
    elif page == "Add Transaction":
        add_transaction_page(user_id)
    elif page == "Accounts":
        accounts_page(user_id)
    elif page == "Budgets":
        budgets_page(user_id)
    elif page == "Reports":
        reports_page(user_id)
    elif page == "Manage":
        manage_page(user_id)


if __name__ == "__main__":
    main()
