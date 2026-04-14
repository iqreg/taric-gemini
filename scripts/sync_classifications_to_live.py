#!/usr/bin/env python3
from __future__ import annotations
import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = "/project/workspace/db/taric_dataset.db"
DEFAULT_LIVE_DB_PATH = "/project/workspace/taric_live.db"

def ensure_live_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS taric_live (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            filename TEXT,
            taric_code TEXT,
            cn_code TEXT,
            hs_chapter TEXT,
            confidence REAL,
            short_reason TEXT,
            alternatives_json TEXT,
            raw_response_json TEXT
        );
    """)
    conn.commit()

def main() -> int:
    src_db = Path(os.getenv("DB_PATH", DEFAULT_DB_PATH))
    live_db = Path(os.getenv("TARIC_LIVE_DB_PATH", DEFAULT_LIVE_DB_PATH))

    if not src_db.exists():
        raise SystemExit(f"Source DB nicht gefunden: {src_db}")

    src = sqlite3.connect(str(src_db))
    src.row_factory = sqlite3.Row

    live_db.parent.mkdir(parents=True, exist_ok=True)
    dst = sqlite3.connect(str(live_db))
    ensure_live_schema(dst)

    rows = src.execute("""
        SELECT created_at, filename, taric_code, cn_code, hs_chapter,
               confidence, short_reason, alternatives_json, raw_response_json
          FROM classifications
         WHERE status = 'ok'
         ORDER BY created_at ASC, id ASC
    """).fetchall()

    inserted = 0
    skipped = 0
    for r in rows:
        exists = dst.execute("""
            SELECT 1
              FROM taric_live
             WHERE filename = ?
               AND taric_code IS ?
               AND raw_response_json IS ?
             LIMIT 1
        """, (r["filename"], r["taric_code"], r["raw_response_json"])).fetchone()

        if exists:
            skipped += 1
            continue

        dst.execute("""
            INSERT INTO taric_live (
                created_at, filename, taric_code, cn_code, hs_chapter,
                confidence, short_reason, alternatives_json, raw_response_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r["created_at"], r["filename"], r["taric_code"], r["cn_code"], r["hs_chapter"],
            r["confidence"], r["short_reason"], r["alternatives_json"], r["raw_response_json"]
        ))
        inserted += 1

    dst.commit()
    src.close()
    dst.close()

    print(f"Sync finished. inserted={inserted}, skipped_existing={skipped}, source_ok_rows={len(rows)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
