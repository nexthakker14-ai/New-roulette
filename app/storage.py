
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = os.getenv("DATABASE_PATH", "roulette.db")


def connect():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number INTEGER NOT NULL CHECK(number BETWEEN 0 AND 36),
                created_at TEXT NOT NULL
            )
        """)


def add_result(number):
    stamp = datetime.now(timezone.utc).isoformat()

    with connect() as con:
        cur = con.execute(
            "INSERT INTO results(number, created_at) VALUES (?, ?)",
            (number, stamp)
        )

        return {
            "id": cur.lastrowid,
            "number": number,
            "created_at": stamp
        }


def get_results(limit=100):
    with connect() as con:
        rows = con.execute(
            "SELECT id, number, created_at FROM results ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()

    return [dict(row) for row in rows]


def get_all_numbers(limit=500):
    return [row["number"] for row in get_results(limit)]
