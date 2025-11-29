#!/usr/bin/env python3
"""
TARIC Bulk Evaluation

Funktion:
- Nimmt Bilder aus data/taric_bulk_input
- Schickt sie sequenziell an das FastAPI-Backend (/classify)
- Wartet nach jedem Bild eine konfigurierbare Pause
- Verschiebt erfolgreiche Bilder nach data/taric_bulk_done
- Verschiebt dauerhafte Fehler nach data/taric_bulk_error
- Beobachtet optional Token-Nutzung aus der Backend-Antwort

Das Script ist bewusst defensiv:
- Kein Parallelismus
- Bricht bei Rate-Limits oder Backend-Ausfällen sauber ab
"""

import csv
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import requests


# ---------------------------------------------------------------------------
# Basis-Konfiguration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
INPUT_DIR = DATA_DIR / "taric_bulk_input"
DONE_DIR = DATA_DIR / "taric_bulk_done"
ERROR_DIR = DATA_DIR / "taric_bulk_error"
LOG_FILE = DATA_DIR / "taric_bulk_log.csv"

# Standard-Backend-Adresse kann per ENV überschrieben werden
BACKEND_URL = os.getenv("TARIC_BACKEND_URL", "http://127.0.0.1:8000/classify")

# Maximalanzahl Bilder pro Lauf
MAX_PER_RUN = int(os.getenv("TARIC_BULK_MAX_PER_RUN", "40"))

# Pause nach jedem Bild (Sekunden)
SLEEP_SECONDS = float(os.getenv("TARIC_BULK_SLEEP_SECONDS", "10"))

# Optionales Soft-Limit für Tokens pro Run (0 = deaktiviert)
MAX_TOTAL_TOKENS_PER_RUN = int(os.getenv("TARIC_BULK_MAX_TOKENS", "0"))

# Erlaubte Dateiendungen (inkl. WEBP)
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Mapping von Endung → MIME-Type für den Upload
EXT_TO_MIME: Dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def ensure_dirs() -> None:
    """Stellt sicher, dass alle benötigten Verzeichnisse existieren."""
    for d in (DATA_DIR, INPUT_DIR, DONE_DIR, ERROR_DIR):
        d.mkdir(parents=True, exist_ok=True)


def iter_input_files(limit: int) -> List[Path]:
    """
    Liefert bis zu `limit` Dateien aus INPUT_DIR mit erlaubter Endung,
    alphabetisch sortiert.
    """
    files: List[Path] = []
    if not INPUT_DIR.exists():
        return files

    for p in sorted(INPUT_DIR.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() not in ALLOWED_EXTENSIONS:
            # Unbekannte Endung ignorieren – bleibt im Ordner liegen
            continue
        files.append(p)
        if len(files) >= limit:
            break
    return files


def open_log_writer():
    """
    Öffnet die LOG_FILE und liefert ein Objekt zurück,
    das sowohl den csv.writer als auch den zugrundeliegenden File-Handle enthält.
    """

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    file_exists = LOG_FILE.exists()

    f = LOG_FILE.open("a", newline="", encoding="utf-8")
    writer = csv.writer(f, delimiter='|')

    # Header schreiben, falls Datei neu angelegt wird
    if not file_exists:
        writer.writerow(
            [
                "timestamp",
                "filename",
                "status",
                "taric_code",
                "cn_code",
                "hs_chapter",
                "confidence",
                "error_code",
                "error_message",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
            ]
        )

    class WriterWrapper:
        def __init__(self, file_obj, csv_writer):
            self.file = file_obj
            self.writer = csv_writer

        def write(self, row: List[Any]) -> None:
            self.writer.writerow(row)
            self.file.flush()

        def close(self) -> None:
            self.file.close()

    return WriterWrapper(f, writer)


def log_result(
    writer: Any,
    filename: str,
    status: str,
    response_json: Optional[dict],
    error_code: Optional[str],
    error_message: Optional[str],
) -> int:
    """
    Schreibt einen Log-Eintrag und gibt total_tokens (falls vorhanden) zurück.
    """
    ts = time.strftime("%Y-%m-%d %H:%M:%S")

    taric_code = None
    cn_code = None
    hs_chapter = None
    confidence = None
    prompt_tokens = None
    completion_tokens = None
    total_tokens = None

    if response_json:
        taric_code = response_json.get("taric_code")
        cn_code = response_json.get("cn_code")
        hs_chapter = response_json.get("hs_chapter")
        confidence = response_json.get("confidence")
        usage = response_json.get("usage") or {}
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        total_tokens = usage.get("total_tokens")

    writer.write(
        [
            ts,
            filename,
            status,
            taric_code,
            cn_code,
            hs_chapter,
            confidence,
            error_code,
            error_message,
            prompt_tokens,
            completion_tokens,
            total_tokens,
        ]
    )

    return int(total_tokens or 0)


def classify_file(path: Path) -> Tuple[str, Optional[dict], Optional[str], Optional[str]]:
    """
    Schickt eine Datei an das Backend und gibt zurück:
    - status: "done" / "rate_limited" / "http_error" / "backend_error"
    - response_json (bei Erfolg oder fachlichem Fehler)
    - error_code / error_message (falls vorhanden)
    """
    ext = path.suffix.lower()
    mime = EXT_TO_MIME.get(ext, "application/octet-stream")

    try:
        with path.open("rb") as f:
            files = {"file": (path.name, f, mime)}
            resp = requests.post(BACKEND_URL, files=files, timeout=60)
    except Exception as e:
        return "backend_error", None, "REQUEST_FAILED", str(e)

    # Rate-Limit oder Server-Überlastung
    if resp.status_code == 429:
        try:
            data = resp.json()
        except Exception:
            data = None
        msg = data.get("error") if isinstance(data, dict) else resp.text
        return "rate_limited", data, "RATE_LIMIT", msg

    # Generischer HTTP-Fehler
    if not resp.ok:
        try:
            data = resp.json()
        except Exception:
            data = None
        msg = None
        if isinstance(data, dict):
            msg = data.get("error") or data.get("detail")
        return "http_error", data, f"HTTP_{resp.status_code}", msg or resp.text

    # Erfolg (HTTP-Ebene)
    try:
        data = resp.json()
    except Exception as e:
        return "backend_error", None, "INVALID_JSON", f"Antwort kein JSON: {e}"

    # Fachliche Fehler könnten später mit ok=false markiert werden;
    # aktuell gehen wir von Erfolg aus.
    return "done", data, None, None


def move_file(src: Path, dst_dir: Path) -> None:
    """Verschiebt eine Datei in das Zielverzeichnis (Zielverzeichnis wird angelegt)."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    src.replace(dst)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    ensure_dirs()

    files = iter_input_files(MAX_PER_RUN)
    if not files:
        print("Keine passenden Dateien in data/taric_bulk_input gefunden.")
        return

    print(f"Starte Bulk-Evaluation mit {len(files)} Datei(en).")
    print(f"Backend: {BACKEND_URL}")
    print(f"Pause zwischen Bildern: {SLEEP_SECONDS} Sekunden")

    writer = open_log_writer()
    total_tokens_used = 0

    try:
        for idx, path in enumerate(files, start=1):
            print(f"[{idx}/{len(files)}] Sende {path.name} ...", flush=True)

            status, data, err_code, err_msg = classify_file(path)

            # Logging
            tokens = log_result(writer, path.name, status, data, err_code, err_msg)
            total_tokens_used += tokens

            # Token-Softlimit prüfen
            if MAX_TOTAL_TOKENS_PER_RUN > 0 and total_tokens_used > MAX_TOTAL_TOKENS_PER_RUN:
                print(
                    f"Token-Softlimit erreicht ({total_tokens_used} > "
                    f"{MAX_TOTAL_TOKENS_PER_RUN}). Breche ab."
                )
                # Datei noch nicht verschieben, damit sie beim nächsten Lauf erneut drankommt
                break

            # Reaktion auf Status
            if status == "done":
                move_file(path, DONE_DIR)
                print(f"  -> OK, verschoben nach {DONE_DIR.name}")
            elif status == "rate_limited":
                print("  -> Rate-Limit erkannt, breche Bulk-Run ab.")
                # Datei im INPUT lassen, damit sie beim nächsten Run dran kommt
                break
            elif status in ("http_error", "backend_error"):
                move_file(path, ERROR_DIR)
                print(f"  -> Fehler ({err_code}), verschoben nach {ERROR_DIR.name}")
            else:
                # Unbekannter Status – sicherheitshalber in ERROR
                move_file(path, ERROR_DIR)
                print(f"  -> Unbekannter Status '{status}', verschoben nach {ERROR_DIR.name}")

            # Pause zwischen den Bildern
            if idx < len(files):
                time.sleep(SLEEP_SECONDS)

    finally:
        writer.close()
        print(f"Fertig. Insgesamt geschätzte Tokens in diesem Lauf: {total_tokens_used}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAbgebrochen durch Benutzer.")
        sys.exit(1)
