import os
import json
import sqlite3
import time
import traceback
from pathlib import Path
from typing import Optional, List

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
IMAGE_DIR = BASE_DIR / "bilder_uploads"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
#GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("WARNUNG: GEMINI_API_KEY ist nicht gesetzt. /classify wird nicht funktionieren.")

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
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Stellt sicher:
    - taric_live existiert (falls nicht, wird angelegt)
    - taric_evaluation existiert (falls nicht, wird angelegt)
    - Spalte superviser_bewertung in taric_evaluation existiert
    """
    conn = get_conn()
    cur = conn.cursor()

    # taric_live
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='taric_live';"
    )
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
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                taric_live_id   INTEGER NOT NULL,
                correct_digits  INTEGER NOT NULL,
                reviewer        TEXT,
                comment         TEXT,
                reviewed_at     TEXT DEFAULT CURRENT_TIMESTAMP,
                superviser_bewertung INTEGER,
                UNIQUE (taric_live_id)
            );
            """
        )
    else:
        # Spalte superviser_bewertung bei Bedarf nachziehen
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

    start = txt.find("{")
    end = txt.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Keine JSON-Klammern in Modell-Antwort gefunden")

    json_str = txt[start : end + 1]
    return json.loads(json_str)


def classify_with_gemini(image_bytes: bytes, filename: str, content_type: Optional[str]) -> dict:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY ist nicht gesetzt")

    model = genai.GenerativeModel(GEMINI_MODEL_NAME)
    mime = content_type or "image/jpeg"

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
    """
    conn = get_conn()
    cur = conn.cursor()

    confidence = data.get("confidence")
    try:
        confidence_val = float(confidence)
    except Exception:
        confidence_val = 0.0

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
    """
    try:
        data = await file.read()
        if not data:
            return JSONResponse(
                status_code=400, content={"error": "Leere Datei erhalten."}
            )

        # Bild speichern (für Evaluation)
        suffix = Path(file.filename or "upload.jpg").suffix or ".jpg"
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{ts}_{int(time.time()*1000)}{suffix}"
        img_path = IMAGE_DIR / filename
        with img_path.open("wb") as f:
            f.write(data)

        # Modell
        try:
            model_result = classify_with_gemini(
                data, filename=file.filename or filename, content_type=file.content_type
            )
        except Exception as e:
            traceback.print_exc()
            return JSONResponse(
                status_code=500, content={"error": f"Fehler bei Modellaufruf: {e}"}
            )

        # DB
        new_id = store_classification(filename, model_result)

        response = {
            "id": new_id,
            "filename": filename,
            "taric_code": model_result.get("taric_code"),
            "cn_code": model_result.get("cn_code"),
            "hs_chapter": model_result.get("hs_chapter"),
            "confidence": model_result.get("confidence"),
            "short_reason": model_result.get("short_reason"),
            "possible_alternatives": model_result.get("possible_alternatives"),
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
    """
    conn = get_conn()
    cur = conn.cursor()

    base_sql = """
        SELECT
            l.id AS taric_live_id,
            l.filename,
            l.created_at,
            l.taric_code,
            l.cn_code,
            l.hs_chapter,
            l.confidence,
            l.short_reason,
            l.alternatives_json,
            e.id AS evaluation_id,
            e.correct_digits,
            e.reviewer,
            e.comment,
            e.superviser_bewertung
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

    items = []
    for r in rows:
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
                "alternatives_json": r["alternatives_json"],
                "evaluation_id": r["evaluation_id"],
                "correct_digits": r["correct_digits"],
                "reviewer": r["reviewer"],
                "comment": r["comment"],
                "superviser_bewertung": r["superviser_bewertung"],
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
        WHERE taric_code IS NOT NULL
        GROUP BY taric_code
        ORDER BY cnt DESC, taric_code ASC
        """
    )
    rows = cur.fetchall()
    conn.close()

    result = []
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
    return {"status": "ok"}
