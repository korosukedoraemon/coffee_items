# init_db.py
import sqlite3

conn = sqlite3.connect('inventory.db')
c = conn.cursor()

c.execute('''
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        unit TEXT NOT NULL,
        stock INTEGER NOT NULL DEFAULT 0
    )
''')

conn.commit()
conn.close()
print("itemsテーブルを作成しました。")
