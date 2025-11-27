import os
import json
import sqlite3
import mimetypes
import time

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import google.generativeai as genai


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
    if content_type:
        return content_type
    mime, _ = mimetypes.guess_type(filename)
    if mime is None:
        return "image/jpeg"
    return mime


def classify_image_bytes(model, data: bytes, filename: str, content_type: str | None) -> dict:
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
model = configure_gemini()
ensure_db()

# CORS für lokale Web-App erlauben (Entwicklung)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # für Produktion enger machen
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/classify")
async def classify(file: UploadFile = File(...)):
    try:
        data = await file.read()

        # optional: Upload lokal speichern
        os.makedirs(IMAGE_DIR, exist_ok=True)
        safe_name = f"{int(time.time())}_{file.filename}"
        save_path = os.path.join(IMAGE_DIR, safe_name)
        with open(save_path, "wb") as f:
            f.write(data)

        result = classify_image_bytes(
            model=model,
            data=data,
            filename=file.filename,
            content_type=file.content_type,
        )

        store_result(safe_name, result)

        return JSONResponse(content=result)

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


@app.get("/health")
async def health():
    return {"status": "ok"}
