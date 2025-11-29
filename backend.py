import os
import json
import sqlite3
import time
import traceback
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import google.generativeai as genai

# --------------------------------------------------
# Basis-Konfiguration
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "taric_live.db"

# Hier speichert das Backend alle hochgeladenen Bilder,
# damit sie später im Evaluationsmodul genutzt werden können.
IMAGE_DIR = BASE_DIR / "bilder_uploads"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")

# Erlaubte Bildformate (inkl. WEBP)
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("WARNUNG: GEMINI_API_KEY ist nicht gesetzt. /classify wird nicht funktionieren.")

# Systemprompt für das Modell (unverändert aus deiner Version)
SYSTEM_PROMPT = """
Du bist ein erfahrener EU-Zoll- und TARIC-Experte.
Deine Aufgabe ist es, anhand eines Produktfotos den wahrscheinlichsten TARIC-Code
für die Ware zu bestimmen.

Rahmenbedingungen:
- Verwende die Struktur der EU TARIC-Datenbank.
- Gehe schrittweise vor:
  1. Beschreibe kurz, was auf dem Bild zu sehen ist (Art der Ware, Material,
     Verwendungszweck, besondere Merkmale).
  2. Bestimme erst die wahrscheinliche HS-Position (4-stellig),
     dann die 6-stellige Unterposition, anschließend die 8-stellige KN-Position
     und zuletzt den 10-stelligen TARIC-Code.
  3. Prüfe, ob besondere zollrechtliche Regelungen greifen könnten
     (Medizinprodukt, Lebensmittel, Elektronik, Textil usw.).

Ausgabeformat (immer als gültiges JSON, ohne zusätzlichen Text):

{
  "taric_code": "XXXXXXXXXX",
  "cn_code": "XXXXXXXX",
  "hs_chapter": "XX",
  "confidence": 0.0,
  "short_reason": "kurze Begründung in 2–4 Sätzen",
  "possible_alternatives": [
    {
      "taric_code": "YYYYYYYYYY",
      "short_reason": "warum dieser Code ebenfalls in Frage kommt"
    }
  ]
}

Regeln:
- Antworte ausschließlich in diesem JSON-Format.
- Wenn du sehr unsicher bist, gib trotzdem den besten Schätzwert und senke 'confidence'.
- Verwende nur plausible TARIC-Codes, die formal zur beschriebenen Ware passen.

Wichtig:
- Nur das JSON-Objekt zurückgeben, keine zusätzliche Erklärung, kein Markdown,
  keine Codeblöcke.
"""

USER_TEXT = "Bestimme für dieses Produktfoto den TARIC-Code und gib nur das JSON aus."


# --------------------------------------------------
# DB-Helfer
# --------------------------------------------------


def get_conn() -> sqlite3.Connection:
    """Öffnet eine SQLite-Connection mit Row-Access per Spaltennamen."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Stellt sicher:
    - taric_live existiert
    - taric_evaluation existiert
    - Spalte superviser_bewertung in taric_evaluation existiert
    """
    conn = get_conn()
    cur = conn.cursor()

    # taric_live
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='taric_live';")
    if not cur.fetchone():
        cur.execute(
            """
            CREATE TABLE taric_live (
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
            """
        )

    # taric_evaluation
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='taric_evaluation';"
    )
    if not cur.fetchone():
        cur.execute(
            """
            CREATE TABLE taric_evaluation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                taric_live_id INTEGER NOT NULL,
                correct_digits INTEGER,
                reviewer TEXT,
                comment TEXT,
                superviser_bewertung INTEGER,
                reviewed_at TEXT,
                UNIQUE (taric_live_id)
            );
            """
        )
    else:
        # Spalte superviser_bewertung bei Bedarf nachziehen (Migration)
        cur.execute("PRAGMA table_info(taric_evaluation);")
        cols = [row["name"] for row in cur.fetchall()]
        if "superviser_bewertung" not in cols:
            cur.execute(
                "ALTER TABLE taric_evaluation ADD COLUMN superviser_bewertung INTEGER;"
            )

    conn.commit()
    conn.close()
    print("DB initialisiert / geprüft.")


init_db()


# --------------------------------------------------
# Modell-Helfer
# --------------------------------------------------


def extract_json_from_text(raw: str) -> dict:
    """
    Extrahiert ein JSON-Objekt aus einer generierten Text-Antwort.
    Entfernt ggf. Markdown-Codeblöcke (```json ... ```).
    """
    if not raw:
        raise ValueError("Leere Modell-Antwort")

    txt = raw.strip()

    # Markdown-Codeblock entfernen
    if txt.startswith("```"):
        lines = txt.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        txt = "\n".join(lines).strip()

    # Versuchen, das JSON anhand der äußeren Klammern zu finden
    start = txt.find("{")
    end = txt.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Keine JSON-Klammern in Modell-Antwort gefunden")

    json_str = txt[start : end + 1]
    return json.loads(json_str)


def classify_with_gemini(
    image_bytes: bytes, filename: str, content_type: Optional[str]
) -> dict:
    """
    Ruft das Gemini-Modell mit Bild + Systemprompt auf und gibt ein
    JSON-ähnliches Dict mit Standardfeldern + optionalem 'usage'-Block zurück.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY ist nicht gesetzt")

    model = genai.GenerativeModel(GEMINI_MODEL_NAME)

    # MIME-Type bestimmen; WEBP explizit zulassen. Bei unbekanntem oder
    # leerem Typ wird defensiv image/jpeg verwendet.
    mime = content_type or "image/jpeg"
    if mime not in ALLOWED_MIME_TYPES:
        mime = "image/jpeg"

    result = model.generate_content(
        [
            SYSTEM_PROMPT,
            {
                "mime_type": mime,
                "data": image_bytes,
            },
        ]
    )

    raw_text = getattr(result, "text", None)
    if not raw_text:
        raise RuntimeError("Modell-Antwort war leer")

    parsed = extract_json_from_text(raw_text)

    # Token-Nutzung (usage_metadata) nach Möglichkeit übernehmen.
    usage = getattr(result, "usage_metadata", None)
    if usage is not None:
        parsed["usage"] = {
            "prompt_tokens": getattr(usage, "prompt_token_count", None),
            "completion_tokens": getattr(usage, "candidates_token_count", None),
            "total_tokens": getattr(usage, "total_token_count", None),
        }

    # Standardfelder absichern
    parsed.setdefault("taric_code", None)
    parsed.setdefault("cn_code", None)
    parsed.setdefault("hs_chapter", None)
    parsed.setdefault("confidence", 0.0)
    parsed.setdefault("short_reason", "")
    parsed.setdefault("possible_alternatives", [])

    return parsed


def store_classification(filename: str, data: dict) -> int:
    """
    Speichert das Klassifikationsergebnis in taric_live und gibt die neue ID zurück.
    Die komplette Modellantwort (inkl. usage) wird als JSON im Feld raw_response_json abgelegt.
    """
    conn = get_conn()
    cur = conn.cursor()

    confidence = data.get("confidence")
    try:
        confidence_val = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence_val = None

    cur.execute(
        """
        INSERT INTO taric_live (
            created_at,
            filename,
            taric_code,
            cn_code,
            hs_chapter,
            confidence,
            short_reason,
            alternatives_json,
            raw_response_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            time.strftime("%Y-%m-%d %H:%M:%S"),
            filename,
            data.get("taric_code"),
            data.get("cn_code"),
            data.get("hs_chapter"),
            confidence_val,
            data.get("short_reason"),
            json.dumps(data.get("possible_alternatives") or [], ensure_ascii=False),
            json.dumps(data, ensure_ascii=False),
        ),
    )
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return new_id


# --------------------------------------------------
# FastAPI-App
# --------------------------------------------------

app = FastAPI(title="TARIC-Gemini-Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class EvaluationIn(BaseModel):
    """Payload für das Speichern/Korrigieren einer Bewertung."""

    taric_live_id: int
    correct_digits: int
    reviewer: Optional[str] = None
    comment: Optional[str] = None
    superviser_bewertung: Optional[int] = None


@app.post("/classify")
async def classify(file: UploadFile = File(...)):
    """
    Nimmt ein Bild entgegen, ruft Gemini auf, speichert das Ergebnis
    in taric_live und gibt das Ergebnis zurück.

    Diese Route wird sowohl von der Web-UI (Einzelbild) als auch vom
    bulk-evaluation-Script verwendet.
    """
    try:
        if not GEMINI_API_KEY:
            return JSONResponse(
                status_code=503,
                content={"error": "GEMINI_API_KEY ist nicht gesetzt."},
            )

        data = await file.read()
        if not data:
            return JSONResponse(
                status_code=400, content={"error": "Leere Datei erhalten."}
            )

        # Dateiendung ermitteln und gegen Whitelist prüfen
        original_name = file.filename or "upload.jpg"
        suffix = Path(original_name).suffix.lower() or ".jpg"
        if suffix not in ALLOWED_EXTENSIONS:
            return JSONResponse(
                status_code=400,
                content={
                    "error": f"Dateiformat {suffix} wird nicht unterstützt. "
                    f"Erlaubt sind: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
                },
            )

        # Bild speichern (für Evaluation)
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{ts}_{int(time.time() * 1000)}{suffix}"
        img_path = IMAGE_DIR / filename
        with img_path.open("wb") as f:
            f.write(data)

        # Modell aufrufen
        try:
            model_result = classify_with_gemini(
                data, filename=original_name, content_type=file.content_type
            )
        except Exception as e:
            traceback.print_exc()
            return JSONResponse(
                status_code=500, content={"error": f"Fehler bei Modellaufruf: {e}"}
            )

        # Ergebnis in DB speichern
        new_id = store_classification(filename, model_result)

        response: Dict[str, Any] = {
            "id": new_id,
            "filename": filename,
            "taric_code": model_result.get("taric_code"),
            "cn_code": model_result.get("cn_code"),
            "hs_chapter": model_result.get("hs_chapter"),
            "confidence": model_result.get("confidence"),
            "short_reason": model_result.get("short_reason"),
            "possible_alternatives": model_result.get("possible_alternatives"),
            "usage": model_result.get("usage"),
        }
        return JSONResponse(content=response)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": f"Unerwarteter Fehler in /classify: {e}"},
        )


@app.get("/api/evaluation/items")
async def get_evaluation_items(
    limit: int = 100,
    only_unreviewed: bool = False,
    only_reviewed: bool = False,
):
    """
    Liefert Klassifikationen inklusive (optional vorhandener) Bewertung
    aus taric_live + taric_evaluation.

    Parameter:
    - limit: max. Anzahl Datensätze
    - only_unreviewed: nur Fälle ohne Bewertung
    - only_reviewed: nur bereits bewertete Fälle
    """
    conn = get_conn()
    cur = conn.cursor()

    base_sql = """
        SELECT
            l.id              AS taric_live_id,
            l.filename        AS filename,
            l.created_at      AS created_at,
            l.taric_code      AS taric_code,
            l.cn_code         AS cn_code,
            l.hs_chapter      AS hs_chapter,
            l.confidence      AS confidence,
            l.short_reason    AS short_reason,
            l.alternatives_json AS alternatives_json,
            l.raw_response_json AS raw_response_json,
            e.id              AS evaluation_id,
            e.correct_digits  AS correct_digits,
            e.reviewer        AS reviewer,
            e.comment         AS comment,
            e.superviser_bewertung AS superviser_bewertung,
            e.reviewed_at     AS reviewed_at
        FROM taric_live l
        LEFT JOIN taric_evaluation e
          ON e.taric_live_id = l.id
    """


    where: List[str] = []
    params: List[object] = []

    if only_unreviewed and not only_reviewed:
        where.append("e.id IS NULL")
    elif only_reviewed and not only_unreviewed:
        where.append("e.id IS NOT NULL")

    if where:
        base_sql += " WHERE " + " AND ".join(where)

    base_sql += " ORDER BY l.created_at DESC, l.id DESC LIMIT ?"
    params.append(limit)

    cur.execute(base_sql, params)
    rows = cur.fetchall()
    conn.close()

    items: List[dict] = []
    for r in rows:
        alternatives_json = r["alternatives_json"] or "[]"
        raw_response_json = r["raw_response_json"] or "{}"

        try:
            alternatives = json.loads(alternatives_json)
        except Exception:
            alternatives = []

        try:
            raw_response = json.loads(raw_response_json)
        except Exception:
            raw_response = {}

        eval_block = None
        if r["evaluation_id"] is not None:
            eval_block = {
                "id": r["evaluation_id"],
                "correct_digits": r["correct_digits"],
                "reviewer": r["reviewer"],
                "comment": r["comment"],
                "superviser_bewertung": r["superviser_bewertung"],
                "reviewed_at": r["reviewed_at"],
            }

        items.append(
            {
                "taric_live_id": r["taric_live_id"],
                "filename": r["filename"],
                "created_at": r["created_at"],
                "taric_code": r["taric_code"],
                "cn_code": r["cn_code"],
                "hs_chapter": r["hs_chapter"],
                "confidence": r["confidence"],
                "short_reason": r["short_reason"],
                "alternatives": alternatives,
                "raw_response": raw_response,
                "evaluation": eval_block,
            }
        )

    return JSONResponse(content=items)


@app.post("/api/evaluation/save")
async def save_evaluation(payload: EvaluationIn):
    """
    Upsert in taric_evaluation:
    - existiert für taric_live_id noch kein Eintrag → INSERT
    - sonst UPDATE
    """
    conn = get_conn()
    cur = conn.cursor()

    now = time.strftime("%Y-%m-%d %H:%M:%S")

    cur.execute(
        "SELECT id FROM taric_evaluation WHERE taric_live_id = ?",
        (payload.taric_live_id,),
    )
    row = cur.fetchone()

    if row:
        eval_id = row["id"]
        cur.execute(
            """
            UPDATE taric_evaluation
               SET correct_digits = ?,
                   reviewer = ?,
                   comment = ?,
                   superviser_bewertung = ?,
                   reviewed_at = ?
             WHERE id = ?
            """,
            (
                payload.correct_digits,
                payload.reviewer,
                payload.comment,
                payload.superviser_bewertung,
                now,
                eval_id,
            ),
        )
    else:
        cur.execute(
            """
            INSERT INTO taric_evaluation (
                taric_live_id,
                correct_digits,
                reviewer,
                comment,
                superviser_bewertung,
                reviewed_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload.taric_live_id,
                payload.correct_digits,
                payload.reviewer,
                payload.comment,
                payload.superviser_bewertung,
                now,
            ),
        )
        eval_id = cur.lastrowid

    conn.commit()
    conn.close()

    return JSONResponse(content={"status": "ok", "evaluation_id": eval_id})


@app.get("/summary")
async def summary():
    """
    Aggregat-Sicht für auswertung.html:
    Gruppiert nach TARIC-Code und liefert Anzahl + Beispiel-Begründung.
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            taric_code,
            COUNT(*) AS cnt,
            MIN(short_reason) AS any_reason
        FROM taric_live
        WHERE taric_code IS NOT NULL AND taric_code <> ''
        GROUP BY taric_code
        ORDER BY cnt DESC
        """
    )
    rows = cur.fetchall()
    conn.close()

    result: List[dict] = []
    for r in rows:
        result.append(
            {
                "taricCode": r["taric_code"],
                "productGroup": f"{r['cnt']} Fälle",
                "description": r["any_reason"] or "",
            }
        )

    return JSONResponse(content=result)


@app.get("/health")
async def health():
    """Einfache Health-Check-Route für Monitoring und Tests."""
    return {"status": "ok"}
