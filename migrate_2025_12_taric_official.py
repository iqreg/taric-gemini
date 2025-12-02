#!/usr/bin/env python3
"""
Migration: TARIC-Official-Cache + Review-Felder in taric_live.db

- Legt Tabelle taric_official_cache an (falls nicht vorhanden)
- Fügt Spalten in taric_live hinzu (falls nicht vorhanden)
"""

import sqlite3
import os
from contextlib import closing

DB_PATH = os.getenv("TARIC_DB_PATH", "taric_live.db")


def column_exists(cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table_name})")
    cols = [row[1] for row in cursor.fetchall()]  # row[1] = name
    return column_name in cols


def ensure_taric_official_cache(conn: sqlite3.Connection) -> None:
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS taric_official_cache (
              id           INTEGER PRIMARY KEY AUTOINCREMENT,
              taric_code   TEXT NOT NULL,
              language     TEXT NOT NULL,
              description  TEXT NOT NULL,
              source       TEXT NOT NULL,
              fetched_at   TEXT NOT NULL,
              raw_payload  TEXT
            );
        """)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_taric_official_unique
              ON taric_official_cache(taric_code, language);
        """)


def ensure_taric_live_review_columns(conn: sqlite3.Connection) -> None:
    with closing(conn.cursor()) as cur:
        # official_match_score
        if not column_exists(cur, "taric_live", "official_match_score"):
            conn.execute("ALTER TABLE taric_live ADD COLUMN official_match_score REAL;")

        # official_match_label
        if not column_exists(cur, "taric_live", "official_match_label"):
            conn.execute("ALTER TABLE taric_live ADD COLUMN official_match_label TEXT;")

        # official_reviewed_by
        if not column_exists(cur, "taric_live", "official_reviewed_by"):
            conn.execute("ALTER TABLE taric_live ADD COLUMN official_reviewed_by TEXT;")

        # official_reviewed_at
        if not column_exists(cur, "taric_live", "official_reviewed_at"):
            conn.execute("ALTER TABLE taric_live ADD COLUMN official_reviewed_at TEXT;")


def main() -> None:
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"DB '{DB_PATH}' nicht gefunden – bitte Pfad prüfen.")

    print(f"[INFO] Verbinde mit DB: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)

    try:
        ensure_taric_official_cache(conn)
        ensure_taric_live_review_columns(conn)
        conn.commit()
        print("[INFO] Migration erfolgreich abgeschlossen.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
