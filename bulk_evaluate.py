#!/usr/bin/env python3
"""
Bulk-Auswertung von Produktbildern gegen das TARIC-Backend.

Funktion:
- Liest alle Bilder aus data/taric_bulk_input/
- Schickt maximal `batch_size` Bilder pro Schleife (ein Request pro Bild)
- Nutzt den Single-Image-Endpunkt POST /classify mit Multipart-Feld "file"
- Schreibt Ergebnisse in eine CSV-Datei unter logs/bulk_runs/
- Verschiebt erfolgreiche Bilder nach data/taric_bulk_done/
- Verschiebt fehlerhafte Bilder nach data/taric_bulk_error/
"""

import argparse
import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List

import requests

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
INPUT_DIR = DATA_DIR / "taric_bulk_input"
DONE_DIR = DATA_DIR / "taric_bulk_done"
ERROR_DIR = DATA_DIR / "taric_bulk_error"
LOG_DIR = BASE_DIR / "logs" / "bulk_runs"

for d in [INPUT_DIR, DONE_DIR, ERROR_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
DEFAULT_ENDPOINT_PATH = "/classify"
DEFAULT_FILE_FIELD_NAME = "file"
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


def setup_logger() -> logging.Logger:
    log_file = LOG_DIR / "bulk_evaluate.log"
    logger = logging.getLogger("bulk_evaluate")
    logger.setLevel(logging.INFO)

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    fh.setFormatter(fh_formatter)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch_formatter = logging.Formatter("[%(levelname)s] %(message)s")
    ch.setFormatter(ch_formatter)
    logger.addHandler(ch)

    logger.info("Bulk-Evaluationslauf gestartet.")
    logger.info("Log-Datei: %s", log_file)
    return logger


def chunked(iterable: List[Path], size: int) -> Iterable[List[Path]]:
    for i in range(0, len(iterable), size):
        yield iterable[i : i + size]


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}


def send_single_image(
    image_path: Path,
    backend_url: str,
    endpoint_path: str,
    file_field_name: str,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    url = backend_url.rstrip("/") + endpoint_path
    if not image_path.is_file():
        raise FileNotFoundError(f"Datei existiert nicht: {image_path}")

    size = image_path.stat().st_size
    if size > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"Datei zu groß: {size} Bytes")

    ext = image_path.suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    elif ext == ".png":
        mime = "image/png"
    elif ext == ".webp":
        mime = "image/webp"
    else:
        mime = "application/octet-stream"

    with image_path.open("rb") as f:
        files = {file_field_name: (image_path.name, f, mime)}
        response = requests.post(url, files=files, timeout=timeout)

    if not response.ok:
        raise RuntimeError(
            f"Backend-Fehler HTTP {response.status_code}: {response.text[:500]}"
        )

    try:
        data = response.json()
    except Exception as e:
        raise RuntimeError(f"Antwort war kein JSON: {e}") from e

    return data


def main() -> None:
    logger = setup_logger()

    parser = argparse.ArgumentParser(
        description="Bulk-Auswertung von Produktbildern gegen TARIC-Backend."
    )
    parser.add_argument(
        "--backend-url",
        default=DEFAULT_BACKEND_URL,
        help=f"Basis-URL des Backends (default: {DEFAULT_BACKEND_URL})",
    )
    parser.add_argument(
        "--endpoint-path",
        default=DEFAULT_ENDPOINT_PATH,
        help=f"Endpunkt-Pfad (default: {DEFAULT_ENDPOINT_PATH})",
    )
    parser.add_argument(
        "--file-field-name",
        default=DEFAULT_FILE_FIELD_NAME,
        help=f"Form-Feldname für Datei (default: {DEFAULT_FILE_FIELD_NAME})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Batch-Größe (Anzahl Bilder pro Schleife, default: 50)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur anzeigen, welche Dateien verarbeitet würden (kein Upload).",
    )

    args = parser.parse_args()

    all_files = sorted(
        [p for p in INPUT_DIR.iterdir() if p.is_file() and is_image_file(p)],
        key=lambda p: p.name,
    )

    if not all_files:
        logger.info("Keine Bilddateien in %s gefunden. Abbruch.", INPUT_DIR)
        return

    logger.info("Gefundene Bilddateien: %d", len(all_files))

    ts = time.strftime("%Y%m%d_%H%M%S")
    csv_path = LOG_DIR / f"bulk_results_{ts}.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile, delimiter=";")
        writer.writerow(
            [
                "filename",
                "status",
                "taric_code",
                "cn_code",
                "hs_chapter",
                "confidence",
                "raw_response",
            ]
        )

        total_success = 0
        total_error = 0

        for batch_idx, batch in enumerate(chunked(all_files, args.batch_size), start=1):
            logger.info("Verarbeite Batch %d (%d Bilder)", batch_idx, len(batch))

            for img_path in batch:
                logger.info("Bild: %s", img_path.name)

                if args.dry_run:
                    writer.writerow(
                        [
                            img_path.name,
                            "DRY_RUN",
                            "",
                            "",
                            "",
                            "",
                            "",
                        ]
                    )
                    continue

                try:
                    data = send_single_image(
                        img_path,
                        backend_url=args.backend_url,
                        endpoint_path=args.endpoint_path,
                        file_field_name=args.file_field_name,
                    )

                    taric_code = data.get("taric_code", "")
                    cn_code = data.get("cn_code", "")
                    hs_chapter = data.get("hs_chapter", "")
                    confidence = data.get("confidence", "")

                    writer.writerow(
                        [
                            img_path.name,
                            "OK",
                            taric_code,
                            cn_code,
                            hs_chapter,
                            confidence,
                            json.dumps(data, ensure_ascii=False),
                        ]
                    )
                    csvfile.flush()

                    target = DONE_DIR / img_path.name
                    img_path.rename(target)
                    total_success += 1
                except Exception as e:
                    logger.error("Fehler beim Verarbeiten von %s: %s", img_path, e)
                    writer.writerow(
                        [
                            img_path.name,
                            f"ERROR: {type(e).__name__}",
                            "",
                            "",
                            "",
                            "",
                            str(e),
                        ]
                    )
                    csvfile.flush()

                    try:
                        target = ERROR_DIR / img_path.name
                        if img_path.exists():
                            img_path.rename(target)
                    except Exception as e2:
                        logger.error("Konnte fehlerhafte Datei nicht verschieben: %s", e2)

                    total_error += 1

    logger.info("Bulk-Lauf abgeschlossen.")
    logger.info("Erfolgreich: %d, Fehler: %d", total_success, total_error)
    logger.info("Ergebnis-CSV: %s", csv_path)


if __name__ == "__main__":
    main()
