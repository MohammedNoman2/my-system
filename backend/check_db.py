import sqlite3
conn = sqlite3.connect("arp.db")
cur = conn.cursor()

cols_to_add = [
    ("shift_id", "INTEGER"),
    ("is_void", "INTEGER NOT NULL DEFAULT 0"),
    ("voided_at", "DATETIME"),
    ("voided_by_id", "INTEGER"),
    ("void_reason", "TEXT"),
    ("reversal_je_number", "VARCHAR(100)"),
]

for col_name, col_def in cols_to_add:
    try:
        cur.execute(f"ALTER TABLE financial_transactions ADD COLUMN {col_name} {col_def}")
        print(f"Added: {col_name}")
    except Exception as e:
        print(f"Skip {col_name}: {e}")

try:
    cur.execute("CREATE INDEX IF NOT EXISTS ix_ft_is_void ON financial_transactions(is_void)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_ft_shift_id ON financial_transactions(shift_id)")
    print("Indexes created")
except Exception as e:
    print(f"Index: {e}")

# Update alembic version to the new migration
new_version = "655210f0992f"
cur.execute("UPDATE alembic_version SET version_num = ?", (new_version,))
print(f"Alembic version updated to {new_version}")

conn.commit()

# Verify
cur.execute("PRAGMA table_info(financial_transactions)")
cols = [r[1] for r in cur.fetchall()]
print("Final cols:", cols)
cur.execute("SELECT version_num FROM alembic_version")
print("Alembic version:", cur.fetchone())

conn.close()
print("Done!")
