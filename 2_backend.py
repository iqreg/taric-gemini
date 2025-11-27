import os
import json
import sqlite3
import mimetypes
import time

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import google.generativeai as genai


# =====================================================
# WICHTIG FÜR MOBIL + LOKAL:
#
# Backend muss so gestartet werden, damit Handy + Mac
# beide zugreifen können:
#
#   cd ~/projects/taric-gemini
#   source .venv_taric/bin/activate
#   uvicorn backend:app --reload --host 0.0.0.0 --port 8000
#
# Frontend (index.html) z. B.:
#
#   python3 -m http.server 8080 --bind 0.0.0.0
#
# Im JS der index.html wird dann die Backend-URL
# dynamisch aus window.location.hostname gebaut.
# =====================================================


# -----------------------
# Konfiguration
# -----------------------

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
"""

USER_TEXT = "Bestimme für dieses Produktfoto den TARIC-Code und gib nur das JSON aus."


def configure_gemini():
    """
    Konfiguriert das Gemini-Modell über die Umgebungsvariable GEMINI_API_KEY.

    WICHTIG:
    - Vor dem Start des Backends im Terminal:
        export GEMINI_API_KEY='DEIN_API_KEY'
    - Oder dauerhaft in deiner Shell-Konfiguration setzen.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Bitte Umgebungsvariable GEMINI_API_KEY setzen.")
    genai.configure(api_key=api_key)

    # Modell aus deiner list_models-Ausgabe
    model = genai.GenerativeModel(
        model_name="gemini-flash-latest",
        system_instruction=SYSTEM_PROMPT,
    )
    return model


def ensure_db():
    """
    Legt (falls noch nicht vorhanden) die SQLite-Tabelle für die Ergebnisse an.

    Die DB-Datei liegt im Projektordner unter:
        taric_live.db
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
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
    conn.commit()
    conn.close()


def guess_mime_type(filename: str, content_type: str | None) -> str:
    """
    Versucht, den MIME-Type zu bestimmen.

    Reihenfolge:
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


def classify_image_bytes(model, data: bytes, filename: str, content_type: str | None) -> dict:
    """
    Ruft das Gemini-Modell mit Bildbytes auf und erwartet JSON-Output gemäß SYSTEM_PROMPT.
    """
    mime_type = guess_mime_type(filename, content_type)

    response = model.generate_content(
        [
            USER_TEXT,
            {
                "mime_type": mime_type,
                "data": data,
            },
        ],
        generation_config={
            "response_mime_type": "application/json",
        },
    )

    return json.loads(response.text)


def store_result(filename: str, result: dict) -> None:
    """
    Speichert das Ergebnis in der SQLite-DB.

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
            float(result.get("confidence", 0.0)),
            result.get("short_reason"),
            json.dumps(result.get("possible_alternatives", []), ensure_ascii=False),
            json.dumps(result, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()


# -----------------------
# FastAPI App
# -----------------------

app = FastAPI()

# Modell + DB beim Start initialisieren
model = configure_gemini()
ensure_db()

# -------------------------------------------------
# CORS-Konfiguration
#
# Hier definierst du, von welchen Origins (URLs) aus
# dein Backend im Browser aufgerufen werden darf.
#
# Für dein Setup:
# - Lokal am Mac:      http://localhost:8080
# - Lokal (127.0.0.1): http://127.0.0.1:8080
# - Handy im WLAN:     http://192.168.7.124:8080
#
# WICHTIG:
# - 192.168.7.124 ist ein Beispiel (aktuelle IP deines Mac).
#   Falls sich deine IP ändert, muss der Eintrag angepasst werden.
# - Für "schnell egal von wo" könntest du theoretisch allow_origins=["*"]
#   verwenden, in Produktion aber unbedingt einschränken.
# -------------------------------------------------

ALLOWED_ORIGINS = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://192.168.7.124:8080",  # IP deines Mac im WLAN (anpassen, falls sich ändert)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
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
    try:
        data = await file.read()

        # Bild optional lokal speichern (für Nachvollziehbarkeit)
        os.makedirs(IMAGE_DIR, exist_ok=True)
        safe_name = f"{int(time.time())}_{file.filename}"
        save_path = os.path.join(IMAGE_DIR, safe_name)
        with open(save_path, "wb") as f:
            f.write(data)

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
        return JSONResponse(content=result)

    except Exception as e:
        # Fängt alle Fehler ab (Gemini, DB, Datei, ...)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


@app.get("/health")
async def health():
    """
    Einfache Health-Check-Route.

    Test:
        http://localhost:8000/health   (am Mac)
        http://192.168.7.124:8000/health (vom Handy)
    """
    return {"status": "ok"}
