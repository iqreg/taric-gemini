#!/usr/bin/env python3
"""
High-End Bildkonverter für TARIC-Bulk-Pipeline

Funktion:
- Findet AVIF, JPG, JPEG, PNG in einem Quellordner
- Konvertiert alle nach WEBP (optimiert für Größe/Qualität)
- Parallelisierung per ProcessPoolExecutor (nutzt mehrere CPU-Kerne)
- Optionales Archivieren der Originalbilder
- Duplikat-Erkennung (Ziel-WEBP existiert bereits -> Überspringen)
- Fortschrittsanzeige und Statistik

Voraussetzungen:
    pip install pillow tqdm

Verwendung:
    python3 convert_to_webp_high_end.py

Empfohlener Workflow:
    1. AVIF/JPG/PNG in SOURCE_DIR legen (z.B. data/taric_bulk_avif_backup/)
    2. Script ausführen -> konvertiert alles nach WEBP in TARGET_DIR (z.B. data/taric_bulk_input/)
    3. Bulk-Evaluation mit bulk-evaluation.py starten (TARGET_DIR ist dann nur WEBP)
"""

import concurrent.futures
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from PIL import Image

try:
    from tqdm import tqdm  # Fortschrittsbalken
except ImportError:  # Fallback ohne tqdm
    tqdm = None


# ---------------------------------------------------------------------------
# KONFIGURATION
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

# QUELLORDNER mit Originalbildern (AVIF, JPG, PNG, WEBP)
SOURCE_DIR = BASE_DIR / "data" / "taric_bulk_source"

# ZIELORDNER für die konvertierten WEBP-Dateien
TARGET_DIR = BASE_DIR / "data" / "taric_bulk_input"

# OPTIONALER Archiv-Ordner für Originale
ARCHIVE_DIR = BASE_DIR / "data" / "taric_bulk_originals"

ARCHIVE_ORIGINALS = True  # wenn du nach Konvertierung aufräumen willst

# Erlaubte Quellformate
ALLOWED_EXTENSIONS = {".avif", ".jpg", ".jpeg", ".png"}

# WEBP-Qualität (0–100) für lossy-Konvertierung
WEBP_QUALITY = 85

# Für PNG optional lossless speichern
LOSSLESS_FOR_PNG = True

# Anzahl paralleler Prozesse (None -> automatisch = Anzahl CPU-Kerne)
MAX_WORKERS = None


# ---------------------------------------------------------------------------
# DATENSTRUKTUREN
# ---------------------------------------------------------------------------

@dataclass
class ConversionResult:
    src_path: Path
    status: str             # "converted", "skipped_exists", "error", "skipped_unsupported"
    src_ext: str
    error_message: str = ""


# ---------------------------------------------------------------------------
# HILFSFUNKTIONEN
# ---------------------------------------------------------------------------

def ensure_directories() -> None:
    """Stellt sicher, dass Ziel- und ggf. Archivordner existieren."""
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    if ARCHIVE_ORIGINALS:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


def find_source_files() -> List[Path]:
    """
    Sucht alle Dateien in SOURCE_DIR mit erlaubter Endung.
    Rückgabe: Liste von Pfaden, sortiert nach Name.
    """
    if not SOURCE_DIR.exists():
        print(f"Quelle existiert nicht: {SOURCE_DIR}")
        return []

    files: List[Path] = []
    for p in sorted(SOURCE_DIR.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() in ALLOWED_EXTENSIONS:
            files.append(p)
    return files


def get_target_path(src: Path) -> Path:
    """
    Bestimmt den Zielpfad der WEBP-Datei im TARGET_DIR.
    Beispiel:
        src = /.../bild01.avif  ->  /.../taric_bulk_input/bild01.webp
    """
    stem = src.stem  # Dateiname ohne Endung
    return TARGET_DIR / f"{stem}.webp"


def convert_single_image(src: Path) -> ConversionResult:
    """
    Konvertiert eine einzelne Bilddatei nach WEBP.
    Wird in einem separaten Prozess ausgeführt (multiprocessing).
    """
    ext = src.suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        return ConversionResult(src, "skipped_unsupported", ext, "Unsupported extension")

    target = get_target_path(src)

    # Duplikat-Erkennung: WEBP existiert bereits
    if target.exists():
        # Optional könnte man hier Größe/Zeitstempel vergleichen – für unseren Zweck reicht Existenz
        return ConversionResult(src, "skipped_exists", ext)

    try:
        # Bild mit Pillow öffnen
        with Image.open(src) as img:
            # Farben in ein kompatibles Format bringen (z.B. "RGB" für viele Modelle)
            if img.mode in ("P", "LA"):
                img = img.convert("RGBA")
            elif img.mode not in ("RGB", "RGBA", "L"):
                img = img.convert("RGB")

            save_kwargs = {}

            # PNG -> optional lossless WEBP
            if ext == ".png" and LOSSLESS_FOR_PNG:
                save_kwargs["lossless"] = True
            else:
                save_kwargs["quality"] = WEBP_QUALITY

            # Sicherstellen, dass Zielordner existiert (im Kind-Prozess)
            target.parent.mkdir(parents=True, exist_ok=True)

            # Speichern als WEBP
            img.save(target, format="WEBP", **save_kwargs)

    except Exception as e:
        return ConversionResult(src, "error", ext, str(e))

    # Optional: Original archivieren (in eigenem Ordner, ggf. gleicher Name)
    if ARCHIVE_ORIGINALS:
        try:
            ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
            dest = ARCHIVE_DIR / src.name

            # Falls im Archiv bereits eine Datei gleichen Namens existiert,
            # hängt man eine laufende Nummer an.
            if dest.exists():
                i = 1
                while True:
                    candidate = ARCHIVE_DIR / f"{src.stem}_{i}{src.suffix}"
                    if not candidate.exists():
                        dest = candidate
                        break
                    i += 1

            shutil.move(str(src), str(dest))
        except Exception as e:
            # Archivierungsfehler sollen die Konvertierung nicht rückgängig machen
            return ConversionResult(
                src,
                "converted",
                ext,
                f"Konvertiert, aber Archivierungsfehler: {e}",
            )

    return ConversionResult(src, "converted", ext)


# ---------------------------------------------------------------------------
# AUSWERTUNG / STATISTIK
# ---------------------------------------------------------------------------

def summarize_results(results: List[ConversionResult]) -> None:
    """Gibt eine kompakte Statistik über alle Konvertierungen aus."""
    total = len(results)
    converted = sum(1 for r in results if r.status == "converted")
    skipped_exists = sum(1 for r in results if r.status == "skipped_exists")
    errors = sum(1 for r in results if r.status == "error")
    skipped_unsupported = sum(1 for r in results if r.status == "skipped_unsupported")

    by_ext = {}
    for r in results:
        by_ext.setdefault(r.src_ext, 0)
        by_ext[r.src_ext] += 1

    print("\n--- Zusammenfassung ---")
    print(f"Quelle      : {SOURCE_DIR}")
    print(f"Ziel (WEBP) : {TARGET_DIR}")
    if ARCHIVE_ORIGINALS:
        print(f"Archiv      : {ARCHIVE_DIR}")
    print()
    print(f"Gesamt Dateien gescannt     : {total}")
    print(f"  -> konvertiert            : {converted}")
    print(f"  -> übersprungen (existiert): {skipped_exists}")
    print(f"  -> Fehler                 : {errors}")
    print(f"  -> nicht unterstützte Endung: {skipped_unsupported}")
    print()
    print("Verteilung nach Quellendung:")
    for ext, count in sorted(by_ext.items()):
        print(f"  {ext or '(unbekannt)'} : {count}")

    if errors:
        print("\nDetails zu Fehlern:")
        for r in results:
            if r.status == "error":
                print(f"  {r.src_path.name}: {r.error_message}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    print("High-End Bildkonverter nach WEBP")
    print("--------------------------------")
    print(f"Quelle      (SOURCE_DIR): {SOURCE_DIR}")
    print(f"Ziel (WEBP) (TARGET_DIR): {TARGET_DIR}")
    if ARCHIVE_ORIGINALS:
        print(f"Archiv      (ARCHIVE_DIR): {ARCHIVE_DIR}")
    print(f"Erlaubte Endungen       : {', '.join(sorted(ALLOWED_EXTENSIONS))}")
    print(f"WEBP-Qualität           : {WEBP_QUALITY}")
    print(f"Lossless für PNG        : {LOSSLESS_FOR_PNG}")
    print()

    ensure_directories()
    files = find_source_files()

    if not files:
        print("Keine passenden Dateien im Quellordner gefunden – nichts zu tun.")
        return

    print(f"Insgesamt {len(files)} konvertierbare Datei(en) gefunden.\n")

    results: List[ConversionResult] = []

    # Parallelisierung mit ProcessPoolExecutor
    with concurrent.futures.ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        iterator = executor.map(convert_single_image, files)

        if tqdm is not None:
            # Fortschrittsanzeige mit tqdm
            for res in tqdm(iterator, total=len(files), desc="Konvertiere"):
                results.append(res)
        else:
            # Fallback ohne tqdm
            for idx, res in enumerate(iterator, start=1):
                print(f"[{idx}/{len(files)}] {res.src_path.name} -> {res.status}")
                results.append(res)

    summarize_results(results)


if __name__ == "__main__":
    main()
