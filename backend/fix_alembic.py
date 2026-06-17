import sqlite3
 
conn = sqlite3.connect("invoiceai.db")
cur = conn.cursor()
 
# Show current state
print("Before:", cur.execute("SELECT * FROM alembic_version").fetchall())
 
# Remove the orphaned row
cur.execute("DELETE FROM alembic_version WHERE version_num = '001_add_payment_tracking'")
conn.commit()
 
print("After:", cur.execute("SELECT * FROM alembic_version").fetchall())
conn.close()
 