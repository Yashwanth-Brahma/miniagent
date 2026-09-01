import sqlite3
from pathlib import Path

Path("workspace").mkdir(exist_ok=True)
conn = sqlite3.connect("workspace/data.db")   # read-WRITE, just for setup
conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER, name TEXT, role TEXT)")
conn.execute("DELETE FROM users")
conn.executemany("INSERT INTO users VALUES (?, ?, ?)",
                 [(1, "brahma", "admin"), (2, "alex", "user"), (3, "sam", "user")])
conn.commit()
conn.close()
print("DB ready")