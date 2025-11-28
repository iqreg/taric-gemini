#!/usr/bin/env python3
"""
Bulk-Auswertung von Produktbildern gegen das bestehende TARIC-Backend.

Funktion:
- Liest alle Bilder aus data/taric_bulk_input/
- Schickt maximal `batch_size` Bilder pro Schleife (jeweils EIN Request pro Bild)
- Erwartet einen bestehenden Single-Image-Endpunkt (z. B. POST /predict mit Multipart "file")
- Schreibt Ergebnisse in eine CSV-Datei unter logs/bulk_runs/
- Verschiebt erfolgreiche Bilder nach data/taric_bulk_done/
- Verschiebt fehlerhafte Bilder nach data/taric_bulk_error/
"""

import argparse
import csv
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Iterable, Tuple

import requests


# =========================
# Konfiguration (anpassen)
# =========================

# Standard-Backend-URL (lokal)
DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"

# Standard-Endpunkt-Pfad für die Bildklassifikation
# Falls dein Backend z. B. /classify oder /taric_predict nutzt, hier anpassen.
DEFAULT_ENDPOINT_PATH = "/classify"

# Name des Form-Felds für die Bilddatei im Request (FastAPI: file: UploadFile = File(...))
DEFAULT_FILE_FIELD_NAME = "file"

# Max. Dateigröße (Bytes), einfache Schutzmaßnahme (z. B. 20 MB)
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024


# =========================
# Hilfsfunktionen
# =========================

def setup_logging(log_dir: Path) -> Tuple[logging.Logger, Path]:
    """Initialisiert Logging und gibt Logger + Logdateipfad zurück."""
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"bulk_run_{timestamp}.log"

    logger = logging.getLogger("bulk_evaluate")
    logger.setLevel(logging.INFO)

    # File-Handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh.setFormatter(fh_formatter)
    logger.addHandler(fh)

    # Console-Handler (kurz)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch_formatter = logging.Formatter("[%(levelname)s] %(message)s")
    ch.setFormatter(ch_formatter)
    logger.addHandler(ch)

    logger.info("Bulk-Evaluationslauf gestartet.")
    logger.info("Log-Datei: %s", log_file)
    return logger, log_file


def chunked(iterable: List[Path], size: int) -> Iterable[List[Path]]:
    """Teilt eine Liste in Chunks der Größe 'size' auf."""
    for i in range(0, len(iterable), size):
        yield iterable[i:i + size]


def is_image_file(path: Path) -> bool:
    """Einfache Filterfunktion für Bilddateien nach Dateiendung."""
    return path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}


def send_single_image(
    image_path: Path,
    backend_url: str,
    endpoint_path: str,
    file_field_name: str,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    """
    Sendet ein einzelnes Bild an den bestehenden Backend-Endpunkt.

    Erwartet:
      - POST <backend_url><endpoint_path>
      - multipart/form-data mit {file_field_name: (filename, file, mimetype)}
    """
    url = backend_url.rstrip("/") + endpoint_path

    if not image_path.is_file():
        raise FileNotFoundError(f"Datei nicht gefunden: {image_path}")

    file_size = image_path.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"Datei {image_path.name} ist zu groß ({file_size} Bytes). "
            f"Limit: {MAX_FILE_SIZE_BYTES} Bytes."
        )

    # MIME-Typ grob anhand der Endung
    ext = image_path.suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    elif ext == ".png":
        mime = "image/png"
    else:
        mime = "application/octet-stream"

    with image_path.open("rb") as f:
        files = {file_field_name: (image_path.name, f, mime)}
        response = requests.post(url, files=files, timeout=timeout)

    # Fehler bei HTTP-Status
    if not response.ok:
        raise RuntimeError(
            f"Backend-Fehler für {image_path.name}: "
            f"Status {response.status_code} - {response.text[:500]}"
        )

    try:
        data = response.json()
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Antwort ist kein gültiges JSON für {image_path.name}: {e}"
        ) from e

    return data


def extract_fields_from_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Versucht, wichtige Felder aus der Backend-Response zu lesen.
    Wenn die Keys anders heißen, hier anpassen.

    Erwartete mögliche Keys:
      - taric_code / taric / prediction
      - confidence
      - model_version
      - status
    """
    taric_code = (
        data.get("taric_code")
        or data.get("taric")
        or data.get("prediction")
        or ""
    )
    confidence = data.get("confidence", "")
    model_version = data.get("model_version", "")
    status = data.get("status", "ok")

    return {
        "taric_code": taric_code,
        "confidence": confidence,
        "model_version": model_version,
        "status": status,
    }


# =========================
# Hauptlogik
# =========================

def main():
    parser = argparse.ArgumentParser(
        description="Bulk-Auswertung von Produktbildern gegen TARIC-Backend (Variante A)."
    )
    parser.add_argument(
        "--backend-url",
        default=DEFAULT_BACKEND_URL,
        help=f"Basis-URL des Backends (default: {DEFAULT_BACKEND_URL})",
    )
    parser.add_argument(
        "--endpoint-path",
        default=DEFAULT_ENDPOINT_PATH,
        help=f"Pfad des Klassifikationsendpunkts (default: {DEFAULT_ENDPOINT_PATH})",
    )
    parser.add_argument(
        "--input-dir",
        default="data/taric_bulk_input",
        help="Ordner mit Eingabebildern (default: data/taric_bulk_input)",
    )
    parser.add_argument(
        "--done-dir",
        default="data/taric_bulk_done",
        help="Ordner für erfolgreich verarbeitete Bilder (default: data/taric_bulk_done)",
    )
    parser.add_argument(
        "--error-dir",
        default="data/taric_bulk_error",
        help="Ordner für fehlerhafte Bilder (default: data/taric_bulk_error)",
    )
    parser.add_argument(
        "--logs-dir",
        default="logs/bulk_runs",
        help="Ordner für Logs und Ergebnis-CSV (default: logs/bulk_runs)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=30,
        help="Maximale Anzahl Bilder pro Schleife (default: 30)",
    )
    parser.add_argument(
        "--sleep-between-batches",
        type=float,
        default=1.0,
        help="Pause (Sekunden) zwischen Batches (default: 1.0)",
    )
    parser.add_argument(
        "--file-field-name",
        default=DEFAULT_FILE_FIELD_NAME,
        help=f"Form-Feldname für Bild im Request (default: {DEFAULT_FILE_FIELD_NAME})",
    )

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    done_dir = Path(args.done_dir)
    error_dir = Path(args.error_dir)
    logs_dir = Path(args.logs_dir)

    # Ordner anlegen
    input_dir.mkdir(parents=True, exist_ok=True)
    done_dir.mkdir(parents=True, exist_ok=True)
    error_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    logger, log_file = setup_logging(logs_dir)

    # CSV-Datei vorbereiten
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_csv = logs_dir / f"results_bulk_{timestamp}.csv"
    csv_fields = [
        "filename",
        "status",
        "taric_code",
        "confidence",
        "model_version",
        "backend_status",
        "error_message",
        "raw_response_json",
    ]
    csv_file = results_csv.open("w", newline="", encoding="utf-8")
    csv_writer = csv.DictWriter(csv_file, fieldnames=csv_fields)
    csv_writer.writeheader()

    logger.info("Backend-URL: %s", args.backend_url)
    logger.info("Endpoint-Pfad: %s", args.endpoint_path)
    logger.info("Input-Ordner: %s", input_dir)
    logger.info("Done-Ordner: %s", done_dir)
    logger.info("Error-Ordner: %s", error_dir)
    logger.info("Batch-Größe: %d", args.batch_size)

    # Eingabedateien sammeln
    all_files = sorted(
        [p for p in input_dir.iterdir() if p.is_file() and is_image_file(p)],
        key=lambda p: p.name,
    )

    if not all_files:
        logger.info("Keine Bilddateien in %s gefunden. Abbruch.", input_dir)
        csv_file.close()
        return

    logger.info("Gefundene Bilddateien: %d", len(all_files))

    total_success = 0
    total_error = 0

    for batch_idx, batch in enumerate(chunked(all_files, args.batch_size), start=1):
        logger.info(
            "Verarbeite Batch %d: %d Bilder",
            batch_idx,
            len(batch),
        )

        for image_path in batch:
            result_row = {
                "filename": image_path.name,
                "status": "error",
                "taric_code": "",
                "confidence": "",
                "model_version": "",
                "backend_status": "",
                "error_message": "",
                "raw_response_json": "",
            }

            try:
                logger.info("Sende Bild: %s", image_path.name)
                response_data = send_single_image(
                    image_path=image_path,
                    backend_url=args.backend_url,
                    endpoint_path=args.endpoint_path,
                    file_field_name=args.file_field_name,
                )

                fields = extract_fields_from_response(response_data)
                result_row.update({
                    "status": fields.get("status", "ok"),
                    "taric_code": fields.get("taric_code", ""),
                    "confidence": fields.get("confidence", ""),
                    "model_version": fields.get("model_version", ""),
                    "backend_status": "200",
                    "raw_response_json": json.dumps(response_data, ensure_ascii=False),
                })

                # Datei verschieben
                target = done_dir / image_path.name
                image_path.rename(target)
                total_success += 1
                logger.info(
                    "Erfolgreich: %s -> TARIC=%s, conf=%s",
                    image_path.name,
                    result_row["taric_code"],
                    result_row["confidence"],
                )

            except Exception as e:
                # Fehlerfall
                err_msg = str(e)
                result_row["status"] = "error"
                result_row["backend_status"] = ""
                result_row["error_message"] = err_msg

                logger.error("Fehler bei %s: %s", image_path.name, err_msg)

                # Datei in Error-Ordner verschieben
                try:
                    target = error_dir / image_path.name
                    if image_path.exists():
                        image_path.rename(target)
                except Exception as move_err:
                    logger.error(
                        "Konnte Datei %s nicht in Error-Ordner verschieben: %s",
                        image_path.name,
                        move_err,
                    )

                total_error += 1

            # Ergebnis in CSV schreiben
            csv_writer.writerow(result_row)
            csv_file.flush()

        # kurze Pause zwischen Batches
        if args.sleep_between_batches > 0:
            time.sleep(args.sleep_between_batches)

    csv_file.close()
    logger.info("Bulk-Evaluationslauf beendet.")
    logger.info("Erfolgreich: %d, Fehler: %d", total_success, total_error)
    logger.info("Ergebnis-CSV: %s", results_csv)
    logger.info("Log-Datei: %s", log_file)


if __name__ == "__main__":
    main()
