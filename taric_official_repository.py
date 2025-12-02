"""
taric_official_repository.py

Verantwortung:
- Zugriff auf taric_official_cache in taric_live.db
- Caching-Strategie für offizielle TARIC-Beschreibungen
- Öffentliche Funktion: get_official_description(taric_code, lang, max_age_hours)
"""

from typing import Optional, Dict
import os
import sqlite3
import datetime
import logging

from taric_wsdl_client import fetch_from_wsdl, TaricWsdlError

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("TARIC_DB_PATH", "taric_live.db")


def _get_db_connection() -> sqlite3.Connection:
    # Wenn du bereits ein `db.py` mit get_db_connection hast, kannst du das hier ersetzen:
    # from db import get_db_connection
    # return get_db_connection()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row: sqlite3.Row) -> Dict:
    return {
        "taric_code": row["taric_code"],
        "language": row["language"],
        "description": row["description"],
        "source": row["source"],
        "fetched_at": row["fetched_at"],
        "raw": row["raw_payload"],
    }


def _load_from_cache(taric_code: str, lang: str) -> Optional[Dict]:
    with _get_db_connection() as conn:
        cur = conn.execute(
            """
            SELECT taric_code, language, description, source, fetched_at, raw_payload
              FROM taric_official_cache
             WHERE taric_code = ?
               AND language   = ?
            """,
            (taric_code, lang),
        )
        row = cur.fetchone()
        return _row_to_dict(row) if row else None


def _is_fresh(entry: Dict, max_age_hours: Optional[int]) -> bool:
    if max_age_hours is None:
        return True
    try:
        fetched_at = datetime.datetime.fromisoformat(entry["fetched_at"].replace("Z", "+00:00"))
    except Exception:
        return False
    age = datetime.datetime.now(datetime.timezone.utc) - fetched_at
    return age <= datetime.timedelta(hours=max_age_hours)


def _save_to_cache(data: Dict) -> None:
    with _get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO taric_official_cache (taric_code, language, description, source, fetched_at, raw_payload)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(taric_code, language)
            DO UPDATE SET
              description = excluded.description,
              source      = excluded.source,
              fetched_at  = excluded.fetched_at,
              raw_payload = excluded.raw_payload;
            """,
            (
                data["taric_code"],
                data["language"],
                data["description"],
                data["source"],
                data["fetched_at"],
                data.get("raw"),
            ),
        )
        conn.commit()


def get_official_description(taric_code: str,
                             lang: str = "DE",
                             max_age_hours: Optional[int] = 24) -> Optional[Dict]:
    """
    High-Level-Funktion für Backend und Evaluation-Endpoints.

    Ablauf:
    1. Cache prüfen (taric_official_cache)
    2. Wenn Eintrag existiert und (optional) nicht zu alt -> zurückgeben.
    3. Sonst via WSDL holen, in Cache schreiben, zurückgeben.

    :param taric_code: TARIC / Goods Code (10-stellig bevorzugt).
    :param lang: Sprachcode ('DE', 'EN', ...)
    :param max_age_hours: maximale "Alter" des Cache-Eintrags; None = immer verwenden.
    :return: Dict mit offizieller Beschreibung oder None, wenn nichts gefunden.
    """

    taric_code = (taric_code or "").strip()
    if not taric_code:
        logger.warning("get_official_description: leerer TARIC-Code")
        return None

    lang = (lang or "DE").upper()

    # 1. Cache prüfen
    cached = _load_from_cache(taric_code, lang)
    if cached and _is_fresh(cached, max_age_hours):
        logger.info("TARIC official aus Cache: code=%s lang=%s", taric_code, lang)
        return cached

    # 2. WSDL-Aufruf
    try:
        wsdl_result = fetch_from_wsdl(taric_code, lang)
    except TaricWsdlError as exc:
        logger.error("Fehler beim TARIC-WSDL-Aufruf: %s", exc)
        # Falls es einen veralteten Cache gibt, kannst du den optional trotzdem zurückgeben:
        return cached

    if wsdl_result is None:
        # Nichts gefunden
        logger.info("Keine offizielle TARIC-Beschreibung gefunden: code=%s lang=%s", taric_code, lang)
        return None

    # 3. Im Cache speichern
    _save_to_cache(wsdl_result)

    return _load_from_cache(taric_code, lang)
