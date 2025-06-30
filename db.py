# db.py
import sqlite3
from datetime import datetime, timedelta

def init_db():
    conn = sqlite3.connect('db.sqlite3')
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS keys (
            key TEXT PRIMARY KEY,
            name TEXT,
            expires_at TEXT,
            used INTEGER DEFAULT 0
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            name TEXT,
            expires_at TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
