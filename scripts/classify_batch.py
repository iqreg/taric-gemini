#!/usr/bin/env python3
"""Batch classification for TARIC images with SQLite + text exports.

Default paths are CodeSandbox-friendly and persistent under /project/workspace.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import os
import sqlite3
import time
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import google.generativeai as genai

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif"}
DEFAULT_IMAGE_DIR = "/project/workspace/data/raw/taric_bulk_avif_backup"
DEFAULT_DB_PATH = "/project/workspace/db/taric_dataset.db"
DEFAULT_RESULTS_DIR = "/project/workspace/results"
DEFAULT_MODEL = "gemini-2.5-flash-lite"
SYSTEM_PROMPT = """
Du bist ein erfahrener EU-Zoll- und TARIC-Experte.
Bestimme aus einem Produktbild den wahrscheinlichsten TARIC-Code.
Antworte ausschließlich als valides JSON mit den Feldern:
- taric_code
- cn_code
- hs_chapter
- confidence
- short_reason
- possible_alternatives (Liste)
""".strip()
USER_PROMPT = "Bestimme TARIC/CN/HS für dieses Produktbild und gib nur JSON aus."


@dataclass
class Settings:
    api_key: str | None
    model_name: str
    image_dir: Path
    db_path: Path
    results_dir: Path
    skip_existing: bool
    request_delay_seconds: float


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS classifications (
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


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    return Settings(
        api_key=os.getenv("GEMINI_API_KEY"),
        model_name=os.getenv("GEMINI_MODEL_NAME", DEFAULT_MODEL),
        image_dir=Path(os.getenv("IMAGE_DIR", DEFAULT_IMAGE_DIR)),
        db_path=Path(os.getenv("DB_PATH", DEFAULT_DB_PATH)),
        results_dir=Path(os.getenv("RESULTS_DIR", DEFAULT_RESULTS_DIR)),
        skip_existing=_env_bool("SKIP_EXISTING", True),
        request_delay_seconds=float(os.getenv("REQUEST_DELAY_SECONDS", "0.4")),
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dirs(settings: Settings) -> None:
    settings.image_dir.mkdir(parents=True, exist_ok=True)
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.results_dir.mkdir(parents=True, exist_ok=True)


def connect_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def iter_image_files(image_dir: Path) -> Iterable[Path]:
    if not image_dir.exists():
        return []
    files: list[Path] = []
    for p in image_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(p)
    return sorted(files)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def already_processed(conn: sqlite3.Connection, filename: str, file_hash: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM classifications WHERE filename = ? AND file_hash = ? AND status = 'ok' LIMIT 1",
        (filename, file_hash),
    ).fetchone()
    return row is not None


def configure_model(settings: Settings):
    if not settings.api_key:
        raise RuntimeError("GEMINI_API_KEY ist nicht gesetzt.")
    genai.configure(api_key=settings.api_key)
    return genai.GenerativeModel(
        model_name=settings.model_name,
        system_instruction=SYSTEM_PROMPT,
    )


def parse_json_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: erstes JSON-Objekt im Text extrahieren
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def extract_response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text

    # Fallback für SDK-Varianten ohne .text
    chunks: list[str] = []
    for cand in getattr(response, "candidates", []) or []:
        content = getattr(cand, "content", None)
        parts = getattr(content, "parts", None) if content else None
        for part in parts or []:
            t = getattr(part, "text", None)
            if isinstance(t, str) and t.strip():
                chunks.append(t)
    return "\n".join(chunks).strip()


def classify_file(model: Any, path: Path) -> tuple[dict[str, Any] | None, str | None]:
    mime_type, _ = mimetypes.guess_type(path.name)
    mime_type = mime_type or "image/jpeg"
    with path.open("rb") as f:
        img_bytes = f.read()

    payload = [USER_PROMPT, {"mime_type": mime_type, "data": img_bytes}]
    attempts: list[tuple[str, dict[str, Any]]] = [
        ("json_mode", {"generation_config": {"response_mime_type": "application/json"}}),
        ("plain_mode", {}),
    ]

    last_err = "Unbekannter Fehler"
    for mode, kwargs in attempts:
        try:
            response = model.generate_content(payload, **kwargs)
            text = extract_response_text(response)
            if not text:
                last_err = f"Leere Modellantwort ({mode})"
                continue
            return parse_json_response(text), None
        except Exception as exc:  # noqa: BLE001 - robust batch processing
            last_err = f"{mode}: {exc}"
            continue

    return None, last_err


def upsert_record(
    conn: sqlite3.Connection,
    *,
    filename: str,
    file_path: str,
    file_hash: str,
    payload: dict[str, Any] | None,
    status: str,
    error_message: str | None,
) -> dict[str, Any]:
    now = utc_now_iso()
    payload = payload or {}
    confidence_val = payload.get("confidence")
    try:
        confidence = float(confidence_val) if confidence_val is not None else None
    except (TypeError, ValueError):
        confidence = None

    record = {
        "filename": filename,
        "file_path": file_path,
        "file_hash": file_hash,
        "taric_code": payload.get("taric_code"),
        "cn_code": payload.get("cn_code"),
        "hs_chapter": payload.get("hs_chapter"),
        "confidence": confidence,
        "short_reason": payload.get("short_reason"),
        "alternatives_json": json.dumps(payload.get("possible_alternatives", []), ensure_ascii=False),
        "raw_response_json": json.dumps(payload, ensure_ascii=False),
        "status": status,
        "error_message": error_message,
        "created_at": now,
        "updated_at": now,
    }

    conn.execute(
        """
        INSERT INTO classifications (
            filename, file_path, file_hash, taric_code, cn_code, hs_chapter,
            confidence, short_reason, alternatives_json, raw_response_json,
            status, error_message, created_at, updated_at
        ) VALUES (
            :filename, :file_path, :file_hash, :taric_code, :cn_code, :hs_chapter,
            :confidence, :short_reason, :alternatives_json, :raw_response_json,
            :status, :error_message, :created_at, :updated_at
        )
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
        record,
    )
    conn.commit()
    return record


def ensure_export_files(results_dir: Path) -> tuple[Path, Path, Path, Path]:
    jsonl_path = results_dir / "classifications.jsonl"
    csv_path = results_dir / "classifications.csv"
    failed_path = results_dir / "failed_files.jsonl"
    manifest_path = results_dir / "run_manifest.json"

    if not csv_path.exists():
        with csv_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "filename",
                    "file_path",
                    "file_hash",
                    "taric_code",
                    "cn_code",
                    "hs_chapter",
                    "confidence",
                    "short_reason",
                    "alternatives_json",
                    "raw_response_json",
                    "status",
                    "error_message",
                    "created_at",
                    "updated_at",
                ],
            )
            writer.writeheader()

    return jsonl_path, csv_path, failed_path, manifest_path


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_csv(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
        writer.writerow(row)


def run_batch(settings: Settings, force: bool) -> int:
    ensure_dirs(settings)
    conn = connect_db(settings.db_path)
    files = list(iter_image_files(settings.image_dir))
    jsonl_path, csv_path, failed_path, manifest_path = ensure_export_files(settings.results_dir)

    if not files:
        print(f"Keine Bilder gefunden in {settings.image_dir}")

    model = configure_model(settings) if files else None

    counts = {"total": len(files), "processed": 0, "skipped": 0, "ok": 0, "failed": 0}

    for idx, file_path in enumerate(files, start=1):
        file_hash = sha256_file(file_path)
        filename = file_path.name
        should_skip = settings.skip_existing and not force and already_processed(conn, filename, file_hash)
        if should_skip:
            counts["skipped"] += 1
            print(f"[{idx}/{len(files)}] SKIP {file_path}")
            continue

        print(f"[{idx}/{len(files)}] CLASSIFY {file_path}")
        payload, err = classify_file(model, file_path)
        status = "ok" if err is None else "failed"
        record = upsert_record(
            conn,
            filename=filename,
            file_path=str(file_path),
            file_hash=file_hash,
            payload=payload,
            status=status,
            error_message=err,
        )
        append_jsonl(jsonl_path, record)
        append_csv(csv_path, record)
        if status == "failed":
            append_jsonl(failed_path, record)
            counts["failed"] += 1
        else:
            counts["ok"] += 1

        counts["processed"] += 1
        if settings.request_delay_seconds > 0:
            time.sleep(settings.request_delay_seconds)

    manifest = {
        "run_at": utc_now_iso(),
        "image_dir": str(settings.image_dir),
        "db_path": str(settings.db_path),
        "results_dir": str(settings.results_dir),
        "skip_existing": settings.skip_existing,
        "force": force,
        "counts": counts,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    conn.close()
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch image classification for TARIC dataset.")
    parser.add_argument("--force", action="store_true", help="Reprocess files even if already processed.")
    parser.add_argument(
        "--init-db-only",
        action="store_true",
        help="Create directories and DB schema only, without classifying images.",
    )
    args = parser.parse_args()

    settings = load_settings()
    ensure_dirs(settings)
    conn = connect_db(settings.db_path)
    conn.close()

    if args.init_db_only:
        print(f"DB initialisiert: {settings.db_path}")
        return 0

    return run_batch(settings, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
