import os
import json
import sqlite3
import time
import traceback
from datetime import date
from pathlib import Path
from typing import Optional, List, Dict, Any
from io import BytesIO

from PIL import Image
from fastapi import FastAPI, File, UploadFile, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

#VERSION für codesandbox eingeführt Beschreibung 1-Port-Setup (empfohlen): Frontend + Bilder-Uploads über FastAPI ausliefern
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Mount static files from the root directory for HTML pages
app.mount("/", StaticFiles(directory=".", html=True), name="static")


#VERSION für codesandbox eingeführt Beschreibung 1-Port-Setup (empfohlen): Frontend + Bilder-Uploads über FastAPI ausliefern ende


import httpx
from bs4 import BeautifulSoup

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
# GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-lite")

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
# Offizielle TARIC-Referenz (EU) – Cache & Fetch
# --------------------------------------------------


def _extract_official_description_from_html(html: str, taric_prefix: str, digits: int) -> str | None:
    """
    Extrahiert aus der TARIC-Consultation-HTML den Beschreibungstext
    für den angegebenen Präfix (z.B. '8517' bei digits=4).

    Strategie:
    - Anker-ID = Präfix auf 10 Stellen mit Nullen aufgefüllt (z.B. '8517000000')
    - Passende Zeile / Container um diesen Anker herum suchen.
    """
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    anchor_id = taric_prefix.ljust(10, "0")
    anchor = soup.find(id=anchor_id) or soup.find("a", attrs={"name": anchor_id})

    if anchor:
        container = anchor.find_parent("tr") or anchor.find_parent("div") or anchor.parent
        if container:
            text = " ".join(container.stripped_strings)
            text = text.replace("\xa0", " ").strip()
            if text:
                return text

    texts = soup.find_all(string=lambda s: s and taric_prefix in s)
    collected = []
    for t in texts:
        parent = t.parent
        if parent:
            snippet = " ".join(parent.stripped_strings)
            collected.append(snippet)

    if collected:
        unique = list(dict.fromkeys(collected))
        combined = " | ".join(unique)
        return combined[:4000]

    return None


def _get_cached_official_description(
    taric_prefix: str,
    digits: int,
    sim_date: str,
    lang: str = "de",
) -> tuple[str | None, str | None]:
    """
    Liest vorhandene Daten aus taric_official_cache.
    Rückgabe: (official_description, source_url) oder (None, None), wenn nichts gefunden.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT official_description, source_url
        FROM taric_official_cache
        WHERE taric_prefix = ?
          AND digits = ?
          AND sim_date = ?
          AND lang = ?
        LIMIT 1
        """,
        (taric_prefix, digits, sim_date, lang),
    )
    row = cur.fetchone()
    conn.close()

    if row:
        return row[0], row[1]
    return None, None


def _store_official_description_in_cache(
    taric_prefix: str,
    digits: int,
    sim_date: str,
    lang: str,
    official_html: str,
    official_description: str | None,
    source_url: str,
) -> None:
    """Speichert das Ergebnis im Cache."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO taric_official_cache (
            taric_prefix, digits, sim_date, lang,
            official_html, official_description, source_url, created_at, last_used_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """,
        (taric_prefix, digits, sim_date, lang, official_html, official_description, source_url),
    )
    conn.commit()
    conn.close()


async def fetch_official_taric_description(
    full_code: str,
    digits: int = 4,
    lang: str = "de",
    sim_date: str | None = None,
) -> dict:
    """
    Holt die offizielle Beschreibung von der EU-TARIC-Seite:
    https://ec.europa.eu/taxation_customs/dds2/taric/taric_consultation.jsp

    - full_code: 10-stelliger TARIC-Code aus deiner Klassifikation
    - digits: wie viele Stellen als Präfix verwendet werden (z.B. 4 -> '8517')
    - lang: 'de' (oder 'en' etc.)
    - sim_date: Simulationsdatum YYYYMMDD; falls None -> heutiges Datum.
    """

    if not full_code.isdigit() or len(full_code) != 10:
        return {
            "error": "TARIC-Code muss 10-stellig und numerisch sein.",
            "input_code": full_code,
        }

    if digits not in (4, 6, 8, 10):
        digits = 4

    taric_prefix = full_code[:digits]

    if sim_date is None:
        sim_date = date.today().strftime("%Y%m%d")

    cached_desc, cached_url = _get_cached_official_description(
        taric_prefix=taric_prefix,
        digits=digits,
        sim_date=sim_date,
        lang=lang,
    )
    if cached_desc is not None:
        return {
            "input_code": full_code,
            "used_prefix": taric_prefix,
            "digits": digits,
            "sim_date": sim_date,
            "lang": lang,
            "official_description": cached_desc,
            "source_url": cached_url,
            "from_cache": True,
        }

    base_url = "https://ec.europa.eu/taxation_customs/dds2/taric/taric_consultation.jsp"
    params = {
        "Lang": lang,
        "Taric": taric_prefix,
        "Expand": "true",
        "SimDate": sim_date,
    }

    requested_url = None
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(base_url, params=params)
        requested_url = str(resp.request.url)
        resp.raise_for_status()
        html = resp.text

    official_description = _extract_official_description_from_html(html, taric_prefix, digits)
    final_url = str(resp.url)

    _store_official_description_in_cache(
        taric_prefix=taric_prefix,
        digits=digits,
        sim_date=sim_date,
        lang=lang,
        official_html=html,
        official_description=official_description,
        source_url=final_url,
    )

    return {
        "input_code": full_code,
        "used_prefix": taric_prefix,
        "digits": digits,
        "sim_date": sim_date,
        "lang": lang,
        "official_description": official_description,
        "source_url": final_url,
        "requested_url": requested_url or final_url,
        "from_cache": False,
    }


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

#VERSION für codesandbox eingeführt Beschreibung 1-Port-Setup (empfohlen): Frontend + Bilder-Uploads über FastAPI ausliefern
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# ...

app = FastAPI(title="TARIC-Gemini-Backend")

# --- Frontend & Static Files (1-Port-Setup) ---
# Alle Dateien im Repo-Root als /static verfügbar machen (index.html, evaluation.html, auswertung.html, ...)
app.mount("/static", StaticFiles(directory=str(BASE_DIR)), name="static")

# Upload-Bilder (für Evaluation UI) direkt ausliefern
app.mount("/bilder_uploads", StaticFiles(directory=str(IMAGE_DIR)), name="bilder_uploads")

# Root-Seite: Frontend
@app.get("/")
async def frontend_root():
    return FileResponse(str(BASE_DIR / "index.html"))

# Komfort-Routen (optional, aber praktisch)
@app.get("/evaluation")
async def frontend_evaluation():
    return FileResponse(str(BASE_DIR / "evaluation.html"))

@app.get("/auswertung")
async def frontend_auswertung():
    return FileResponse(str(BASE_DIR / "auswertung.html"))
#VERSION für codesandbox eingeführt Beschreibung 1-Port-Setup (empfohlen): Frontend + Bilder-Uploads über FastAPI ausliefern ende


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

        # Bild in WebP konvertieren und speichern (zur Speicherersparnis)
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{ts}_{int(time.time() * 1000)}.webp"
        img_path = IMAGE_DIR / filename
        
        try:
            # Konvertiere zu WebP
            img = Image.open(BytesIO(data))
            # Auto-Rotation basierend auf EXIF-Daten
            try:
                from PIL import ImageOps
                img = ImageOps.exif_transpose(img)
            except:
                pass
            img.save(img_path, 'WEBP', quality=85, method=6)
            print(f"✅ Bild gespeichert als WebP: {filename}")
        except Exception as e:
            # Fallback: Speichere Original (falls WebP-Konvertierung fehlschlägt)
            print(f"⚠️  WebP-Konvertierung fehlgeschlagen: {e}. Speichere Original...")
            filename = f"{ts}_{int(time.time() * 1000)}{Path(original_name).suffix}"
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


@app.get("/api/taric_official_description/{taric_code}")
async def get_official_description(taric_code: str):
    """
    EU-API-TEST: Liefert die offizielle Beschreibung eines 10-stelligen TARIC-Codes
    aus der lokalen Referenztabelle 'taric_reference'. Tabelle muss vorab mit EU-Daten
    befüllt sein.
    """
    print(f"LOG: [EU-API-TEST] Versuch, offizielle Beschreibung für TARIC-Code: {taric_code} abzurufen.")

    # 1) Eingabe validieren
    if not taric_code or len(taric_code) != 10 or not taric_code.isdigit():
        print(
            f"LOG: [EU-API-TEST] ERROR - Ungültiger Code '{taric_code}'. "
            "Muss 10-stellig und numerisch sein (400 Bad Request)."
        )
        return JSONResponse(
            status_code=400,
            content={"error": "Ungültiger TARIC-Code. Muss 10-stellig sein."},
        )

    conn = get_conn()
    cur = conn.cursor()

    try:
        # 2) Lookup in lokaler Referenz-DB
        cur.execute(
            """
            SELECT description_de
            FROM taric_reference
            WHERE taric_code = ?
            LIMIT 1
            """,
            (taric_code,),
        )
        row = cur.fetchone()

        if row:
            description = row["description_de"]
            print(f"LOG: [EU-API-TEST] SUCCESS - Beschreibung für {taric_code} erfolgreich gefunden.")
            return JSONResponse(
                content={
                    "taricCode": taric_code,
                    "officialDescription": description,
                    "source": "Local TARIC Reference DB (EU Data)",
                }
            )

        print(
            f"LOG: [EU-API-TEST] WARNING - Code {taric_code} NICHT in 'taric_reference' gefunden (404 Not Found)."
        )
        return JSONResponse(
            status_code=404,
            content={
                "error": "Code nicht in lokaler TARIC-Referenztabelle gefunden.",
                "details": "Referenztabelle (taric_reference) muss mit EU-Daten befüllt werden. "
                "API-Call kam an, aber der Code fehlt in der DB.",
            },
        )

    except sqlite3.OperationalError as e:
        print(
            f"LOG: [EU-API-TEST] CRITICAL ERROR - Tabelle 'taric_reference' fehlt in DB. "
            f"(500 Internal Server Error). Fehler: {e}"
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Datenbankfehler: Tabelle 'taric_reference' fehlt.",
                "details": f"Bitte DB-Schema prüfen. Originalfehler: {e}",
            },
        )
    except Exception as e:
        print(
            f"LOG: [EU-API-TEST] UNKNOWN ERROR - Unerwarteter Fehler im Endpoint. "
            f"(500 Internal Server Error). Fehler: {e}"
        )
        return JSONResponse(
            status_code=500,
            content={"error": "Unerwarteter Serverfehler", "details": str(e)},
        )
    finally:
        conn.close()


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


@app.get("/api/taric_official_compare")
async def taric_official_compare(
    code: str = Query(..., description="10-stelliger TARIC-Code, z.B. 8517120000"),
    digits: int = Query(4, description="Präfix-Länge: 4, 6, 8 oder 10"),
    lang: str = Query("de", description="Sprachcode, z.B. 'de' oder 'en'"),
    sim_date: str | None = Query(
        None,
        description="Simulationsdatum YYYYMMDD; wenn nicht gesetzt, wird das heutige Datum verwendet.",
    ),
):
    """
    API-Endpoint, der fetch_official_taric_description() aufruft und
    die offizielle EU-Beschreibung plus Metadaten zurückgibt.
    """

    try:
        result = await fetch_official_taric_description(
            full_code=code,
            digits=digits,
            lang=lang,
            sim_date=sim_date,
        )

        if "error" in result:
            return JSONResponse(content=result, status_code=400)

        return JSONResponse(content=result)

    except httpx.HTTPStatusError as e:
        requested_url = str(e.request.url) if e.request else None
        return JSONResponse(
            content={
                "error": f"HTTP-Fehler beim Abruf der EU-TARIC-Seite: {e.response.status_code} {e.response.reason_phrase}",
                "input_code": code,
                "requested_url": requested_url,
            },
            status_code=502,
        )
    except httpx.HTTPError as e:
        requested_url = str(e.request.url) if getattr(e, "request", None) else None
        return JSONResponse(
            content={
                "error": f"Netzwerkfehler beim Abruf der EU-TARIC-Seite: {str(e)}",
                "input_code": code,
                "requested_url": requested_url,
            },
            status_code=502,
        )
    except Exception as e:
        return JSONResponse(
            content={
                "error": f"Interner Fehler beim TARIC-Vergleich: {str(e)}",
                "input_code": code,
            },
            status_code=500,
        )
