import sqlite3

conn = sqlite3.connect("users.db")
c = conn.cursor()

# USERS TABLE
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT UNIQUE,
    password TEXT
)
""")

# BOOKINGS TABLE (NEW)
c.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location TEXT,
    slot_id TEXT,
    user TEXT,
    time TEXT
)
""")

conn.commit()
conn.close()

print("✅ Database Ready!")