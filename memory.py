import sqlite3, json
from pathlib import Path

DB_PATH = Path("patterns.db")

def connect():
    return sqlite3.connect(DB_PATH)

def init_db():
    with connect() as db:
        db.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            pair TEXT, timeframe TEXT, pattern TEXT, behaviour TEXT,
            direction TEXT, confidence REAL, payload TEXT
        )
        """)

def save_analysis(pair, timeframe, pattern, behaviour, direction, confidence, payload):
    with connect() as db:
        db.execute(
            """INSERT INTO analyses
            (pair,timeframe,pattern,behaviour,direction,confidence,payload)
            VALUES (?,?,?,?,?,?,?)""",
            (pair, timeframe, pattern, behaviour, direction, confidence, json.dumps(payload, ensure_ascii=False))
        )

def get_similar_count(pattern, behaviour):
    # Count previous observations, not wins. Repeated observations alone do not prove edge.
    with connect() as db:
        row = db.execute(
            "SELECT COUNT(*) FROM analyses WHERE pattern=? AND behaviour=?",
            (pattern, behaviour)
        ).fetchone()
    return int(row[0]) if row else 0
