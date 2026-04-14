#!/usr/bin/env python3
"""Rebuild SQLite DB from classifications JSONL export."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = "/project/workspace/db/taric_dataset.db"
DEFAULT_RESULTS_DIR = "/project/workspace/results"

SCHEMA_SQL = """
DROP TABLE IF EXISTS classifications;
CREATE TABLE classifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    taric_code TEXT,
    cn_code TEXT,
    hs_chapter TEXT,
    confidence REAL,
    short_reason TEXT,
    alternatives_json TEXT,
    raw_response_json TEXT,
    status TEXT NOT NULL,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(filename, file_hash)
);
CREATE INDEX IF NOT EXISTS idx_classifications_filename ON classifications(filename);
CREATE INDEX IF NOT EXISTS idx_classifications_file_hash ON classifications(file_hash);
CREATE INDEX IF NOT EXISTS idx_classifications_taric_code ON classifications(taric_code);
CREATE INDEX IF NOT EXISTS idx_classifications_status ON classifications(status);
"""


def main() -> int:
    db_path = Path(os.getenv("DB_PATH", DEFAULT_DB_PATH))
    results_dir = Path(os.getenv("RESULTS_DIR", DEFAULT_RESULTS_DIR))
    jsonl_path = results_dir / "classifications.jsonl"

    if not jsonl_path.exists():
        raise SystemExit(f"JSONL nicht gefunden: {jsonl_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_SQL)

    inserted = 0
    with jsonl_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            conn.execute(
                """
                INSERT INTO classifications (
                    filename, file_path, file_hash, taric_code, cn_code, hs_chapter,
                    confidence, short_reason, alternatives_json, raw_response_json,
                    status, error_message, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(filename, file_hash) DO UPDATE SET
                    file_path = excluded.file_path,
                    taric_code = excluded.taric_code,
                    cn_code = excluded.cn_code,
                    hs_chapter = excluded.hs_chapter,
                    confidence = excluded.confidence,
                    short_reason = excluded.short_reason,
                    alternatives_json = excluded.alternatives_json,
                    raw_response_json = excluded.raw_response_json,
                    status = excluded.status,
                    error_message = excluded.error_message,
                    updated_at = excluded.updated_at
                """,
                (
                    row.get("filename"),
                    row.get("file_path"),
                    row.get("file_hash"),
                    row.get("taric_code"),
                    row.get("cn_code"),
                    row.get("hs_chapter"),
                    row.get("confidence"),
                    row.get("short_reason"),
                    row.get("alternatives_json"),
                    row.get("raw_response_json"),
                    row.get("status", "failed"),
                    row.get("error_message"),
                    row.get("created_at"),
                    row.get("updated_at"),
                ),
            )
            inserted += 1

    conn.commit()
    conn.close()
    print(f"DB rebuilt: {db_path} (rows read: {inserted})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
