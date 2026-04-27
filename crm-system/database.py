import sqlite3

def connect_db():
    return sqlite3.connect("crm.db", check_same_thread=False)

def create_table():
    conn = connect_db()
    cur = conn.cursor()

    # ตารางลูกค้า
    cur.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id TEXT PRIMARY KEY,
        name TEXT,
        phone TEXT,
        job_interest TEXT,
        status TEXT,
        last_contact TEXT
    )
    """)

    # ตารางข้อความ
    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        sender TEXT,
        text TEXT,
        time TEXT
    )
    """)

    conn.commit()
    conn.close()