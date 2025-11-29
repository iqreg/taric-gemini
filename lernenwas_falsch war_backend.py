import os
import json
import sqlite3
import mimetypes
import time
import traceback

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import google.generativeai as genai


# =====================================================
# WICHTIG FÜR MOBIL + LOKAL:
# Dieses Backend ist so ausgelegt, dass es von:
#   - index.html (Bildklassifikation)
#   - evaluation.html (Nachkontrolle / Bewertung)
#   - bulk_evaluate.py (Bulk-Client)
# genutzt werden kann.
#
# Zentrale Tabellen in taric_live.db:
#   - taric_live:   automatische Klassifikation
#   - taric_evaluation: menschliche Bewertung
# =====================================================

IMAGE_DIR = "bilder_uploads"
DB_PATH = "taric_live.db"

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
     (z. B. medizinische Produkte, Chemikalien, Waffen, kritische Güter etc.).

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
- Wenn du sehr unsicher bist, gib trotzdem den bestmöglichen TARIC-Code an
  und reduziere die Confidence entsprechend.
- confidence ist eine Zahl zwischen 0.0 und 1.0.
"""


# -------------------------------------------------
# Gemini-Konfiguration
# -------------------------------------------------


def configure_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY ist nicht gesetzt. Bitte Umgebungsvariable setzen.")

    print(">>> configure_gemini(): initialisiere Gemini-Client")
    genai.configure(api_key=api_key)

    # Modellname ggf. anpassen
    model_name = "gemini-2.5-flash-lite"  # oder "gemini-2.5-flash"
    print(">>> configure_gemini(): verwende Modell:", model_name)

    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=SYSTEM_PROMPT,
    )
    return model


def detect_mime_type(filename: str, content_type: str | None) -> str:
    """
    Versucht, einen sinnvollen MIME-Typ für das Bild herzuleiten.

    Strategie:
      1. Content-Type vom Upload (Browser) verwenden, falls vorhanden
      2. Sonst Dateiendung raten
      3. Fallback: image/jpeg
    """
    if content_type:
        return content_type
    mime, _ = mimetypes.guess_type(filename)
    if mime is None:
        return "image/jpeg"
    return mime


def extract_json_from_text(raw: str) -> str:
    """
    Entfernt Markdown-Codeblöcke (```json ... ```), einzelne Backticks
    und extrahiert den JSON-Teil zwischen erstem '{' und letztem '}'.
    """
    if not raw:
        raise ValueError("Leere Antwort vom Modell")

    # Whitespace trimmen
    txt = raw.strip()

    # Falls als Markdown-Codeblock zurückgekommen (```json ... ```)
    if txt.startswith("```"):
        lines = txt.splitlines()
        # erste Zeile (``` oder ```json) entfernen
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        # letzte Zeile entfernen, wenn sie wieder ``` ist
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        txt = "\n".join(lines).strip()

    # Einzelne Backticks am Anfang/Ende entfernen
    txt = txt.strip("` \n")

    # Sicherheit: nur den Teil zwischen erstem '{' und letztem '}' nehmen
    start = txt.find("{")
    end = txt.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Konnte keine JSON-Klammern in der Antwort finden")

    json_str = txt[start : end + 1]
    return json_str





def classify_image_bytes(model, data: bytes, filename: str, content_type: str | None) -> dict:
    """
    Ruft das Gemini-Modell mit Bildbytes auf und erwartet eine JSON-Antwort passend zum SYSTEM_PROMPT.
    """
    mime_type = detect_mime_type(filename, content_type)
    print(f">>> classify_image_bytes(): Aufruf Modell mit mime_type={mime_type}")

    try:
        response = model.generate_content(
            [
                {
                    "mime_type": mime_type,
                    "data": data,
                },
                {
                    "text": "Bestimme den TARIC-Code für dieses Produktbild gemäß der Systeminstruktion."
                },
            ]
        )
    except Exception as e:
        print(">>> classify_image_bytes(): FEHLER beim Modellaufruf:", repr(e))
        traceback.print_exc()
        raise

    try:
        if hasattr(response, "text"):
            raw = response.text
        elif isinstance(response, dict) and "text" in response:
            raw = response["text"]
        else:
            raw = str(response)
        print(">>> classify_image_bytes(): Rohantwort des Modells (gekürzt):", raw[:500])
    except Exception:
        raw = ""
        print(">>> classify_image_bytes(): Konnte Rohantwort nicht extrahieren.")
        traceback.print_exc()

    try:
        parsed = json.loads(raw)
    except Exception:
        print(">>> classify_image_bytes(): FEHLER beim JSON-Parsing der Modell-Antwort")
        traceback.print_exc()
        raise RuntimeError("Antwort des Modells war kein gültiges JSON.")

    return parsed


def ensure_db():
    """
    Legt (falls noch nicht vorhanden) die SQLite-Tabellen für die Ergebnisse
    der automatischen Klassifikation (taric_live) und die nachträgliche
    Bewertung (taric_evaluation) an.

    Die DB-Datei liegt im Projektordner unter:
        taric_live.db
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Tabelle für automatische Klassifikation
    cur.execute(
        """
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
        """
    )

    # Tabelle für nachträgliche Bewertung
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS taric_evaluation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            taric_live_id INTEGER NOT NULL UNIQUE,
            correct_digits INTEGER,
            reviewer TEXT,
            comment TEXT,
            superviser_bewertung INTEGER,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (taric_live_id) REFERENCES taric_live(id)
        );
        """
    )

    conn.commit()
    conn.close()
    print(">>> ensure_db(): Tabellen taric_live und taric_evaluation geprüft/angelegt.")


def store_result(filename: str, result: dict) -> None:
    """
    Speichert das Ergebnis der automatischen Klassifikation in der SQLite-DB (Tabelle taric_live).

    - filename: unter welchem Dateinamen das Bild lokal gespeichert wurde
    - result: das JSON, das vom Modell kam
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO taric_live
        (created_at, filename, taric_code, cn_code, hs_chapter,
         confidence, short_reason, alternatives_json, raw_response_json)
        VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            filename,
            result.get("taric_code"),
            result.get("cn_code"),
            result.get("hs_chapter"),
            result.get("confidence"),
            result.get("short_reason"),
            json.dumps(result.get("possible_alternatives", []), ensure_ascii=False),
            json.dumps(result, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()
    print(">>> store_result(): Ergebnis gespeichert für", filename)


# -----------------------
# FastAPI App
# -----------------------

app = FastAPI()

# Modell + DB beim Start initialisieren
model = configure_gemini()
ensure_db()

# -------------------------------------------------
# CORS-Konfiguration
# -------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # alle Origins (Dev)
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------
# API-Endpunkte
# -----------------------


@app.post("/classify")
async def classify(file: UploadFile = File(...)):
    """
    Nimmt ein Bild als Datei-Upload entgegen, ruft das Gemini-Modell auf,
    speichert Ergebnis + Rohantwort in der DB und gibt das JSON an den Client zurück.

    Typischer Aufruf von der Web-App:
        fetch(`${API_BASE}/classify`, { method: "POST", body: FormData, ... })
    """
    print(">>> /classify: Request erhalten, filename=", file.filename, "content_type=", file.content_type)
    try:
        data = await file.read()
        print(">>> /classify: Bildbytes erhalten, size=", len(data))

        # Bild lokal speichern (für Nachvollziehbarkeit)
        os.makedirs(IMAGE_DIR, exist_ok=True)
        safe_name = f"{int(time.time())}_{file.filename}"
        save_path = os.path.join(IMAGE_DIR, safe_name)
        with open(save_path, "wb") as f:
            f.write(data)
        print(">>> /classify: Bild gespeichert unter", save_path)

        # Bild klassifizieren
        result = classify_image_bytes(
            model=model,
            data=data,
            filename=file.filename,
            content_type=file.content_type,
        )

        # Ergebnis in DB persistieren
        store_result(safe_name, result)

        # Ergebnis direkt an Frontend zurückgeben
        print(">>> /classify: Erfolg, TARIC =", result.get("taric_code"))
        return JSONResponse(content=result)

    except Exception as e:
        print(">>> /classify: FEHLER:", repr(e))
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


@app.get("/api/evaluation/items")
async def get_evaluation_items(
    limit: int = 100,
    only_unreviewed: bool = False,
    only_reviewed: bool = False,
):
    """
    Liefert TARIC-Klassifikationsdatensätze inkl. optionaler Bewertungsinformationen.

    Parameter:
        limit           – max. Anzahl Datensätze
        only_unreviewed – nur Datensätze ohne Bewertung (taric_evaluation)
        only_reviewed   – nur Datensätze mit Bewertung

    Rückgabe:
        Liste von Objekten mit Feldern:
            id, created_at, filename, taric_code, cn_code, hs_chapter,
            confidence, short_reason, alternatives_json,
            evaluation_id, correct_digits, reviewer, comment, superviser_bewertung
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    base_sql = """
        SELECT
            t.id,
            t.created_at,
            t.filename,
            t.taric_code,
            t.cn_code,
            t.hs_chapter,
            t.confidence,
            t.short_reason,
            t.alternatives_json,
            e.id AS evaluation_id,
            e.correct_digits,
            e.reviewer,
            e.comment,
            e.superviser_bewertung
        FROM taric_live t
        LEFT JOIN taric_evaluation e
          ON e.taric_live_id = t.id
    """

    where_clauses = []
    params: list = []

    if only_unreviewed and not only_reviewed:
        where_clauses.append("e.id IS NULL")
    elif only_reviewed and not only_unreviewed:
        where_clauses.append("e.id IS NOT NULL")

    if where_clauses:
        base_sql += " WHERE " + " AND ".join(where_clauses)

    base_sql += " ORDER BY t.id DESC LIMIT ?"
    params.append(limit)

    cur.execute(base_sql, params)
    rows = cur.fetchall()
    conn.close()

    items = []
    for row in rows:
        items.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "filename": row["filename"],
                "taric_code": row["taric_code"],
                "cn_code": row["cn_code"],
                "hs_chapter": row["hs_chapter"],
                "confidence": row["confidence"],
                "short_reason": row["short_reason"],
                "alternatives_json": row["alternatives_json"],
                "evaluation_id": row["evaluation_id"],
                "correct_digits": row["correct_digits"],
                "reviewer": row["reviewer"],
                "comment": row["comment"],
                "superviser_bewertung": row["superviser_bewertung"],
            }
        )

    return JSONResponse(content=items)


from pydantic import BaseModel
from typing import Optional


class EvaluationSaveRequest(BaseModel):
    taric_live_id: int
    correct_digits: int
    reviewer: Optional[str] = None
    comment: Optional[str] = None
    superviser_bewertung: Optional[int] = None


@app.post("/api/evaluation/save")
async def save_evaluation(payload: EvaluationSaveRequest):
    """
    Speichert oder aktualisiert eine Bewertung für einen Datensatz aus taric_live.

    Upsert-Logik:
        - existiert noch keine Bewertung für taric_live_id → INSERT
        - existiert bereits eine Bewertung → UPDATE

    Rückgabe:
        { "status": "ok", "evaluation_id": <id> }
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Prüfen, ob zugehöriger taric_live-Datensatz existiert
    cur.execute("SELECT id FROM taric_live WHERE id = ?", (payload.taric_live_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return JSONResponse(
            status_code=400,
            content={"error": f"taric_live_id {payload.taric_live_id} nicht gefunden"},
        )

    # Prüfen, ob bereits eine Bewertung existiert
    cur.execute(
        "SELECT id FROM taric_evaluation WHERE taric_live_id = ?",
        (payload.taric_live_id,),
    )
    existing = cur.fetchone()

    now_expr = "datetime('now')"

    if existing:
        eval_id = existing[0]
        cur.execute(
            f"""
            UPDATE taric_evaluation
               SET correct_digits = ?,
                   reviewer = ?,
                   comment = ?,
                   superviser_bewertung = ?,
                   updated_at = {now_expr}
             WHERE id = ?
            """,
            (
                payload.correct_digits,
                payload.reviewer,
                payload.comment,
                payload.superviser_bewertung,
                eval_id,
            ),
        )
    else:
        cur.execute(
            f"""
            INSERT INTO taric_evaluation
            (taric_live_id, correct_digits, reviewer, comment,
             superviser_bewertung, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, {now_expr}, {now_expr})
            """,
            (
                payload.taric_live_id,
                payload.correct_digits,
                payload.reviewer,
                payload.comment,
                payload.superviser_bewertung,
            ),
        )
        eval_id = cur.lastrowid

    conn.commit()
    conn.close()

    return JSONResponse(content={"status": "ok", "evaluation_id": eval_id})


@app.get("/health")
async def health():
    """
    Einfache Health-Check-Route.

    Test:
        http://localhost:8000/health   (am Mac)
        http://192.168.7.124:8000/health (vom Handy)
    """
    return {"status": "ok"}
