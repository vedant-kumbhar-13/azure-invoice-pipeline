import sqlite3

conn = sqlite3.connect("invoiceai.db")
tables = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
).fetchall()]

print("Tables in database:")
for t in sorted(tables):
    print(" -", t)

# Check new payment tables specifically
expected_new = [
    "payment_records",
    "payment_transactions",
    "reminder_settings",
    "reminder_logs",
    "in_app_notifications",
]
print("\nPayment feature tables check:")
for t in expected_new:
    print(f" - {t}: {'OK' if t in tables else 'MISSING'}")

# Check new columns on users / invoices
print("\nusers columns:")
for row in conn.execute("PRAGMA table_info(users)").fetchall():
    print(" -", row[1])

print("\ninvoices columns (payment-related):")
for row in conn.execute("PRAGMA table_info(invoices)").fetchall():
    if "payment" in row[1] or "counterparty" in row[1]:
        print(" -", row[1])

conn.close()"""  """