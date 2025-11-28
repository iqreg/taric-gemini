#!/usr/bin/env python3
"""
Konvertiert automatisch alle .avif Dateien in einem Ordner nach .webp
und verschiebt die Original-AVIF-Dateien in einen Backup-Ordner.

Voraussetzungen:
    pip install pillow pillow-avif-plugin
"""

import os
from pathlib import Path
from PIL import Image
import pillow_avif  # wichtig für AVIF-Support

# -------------------------------------------------------------
# KONFIGURATION
# -------------------------------------------------------------
INPUT_DIR = Path("data/taric_bulk_input")              # Ordner mit den AVIF-Bildern
BACKUP_DIR = Path("data/taric_bulk_avif_backup")       # Backup-Ordner der Originale
QUALITY = 90                                            # WEBP Qualität (80–95 empfohlen)
# -------------------------------------------------------------


def main():
    print("AVIF → WEBP Konverter")
    print("----------------------")

    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(INPUT_DIR.glob("*.avif"))

    if not files:
        print("Keine AVIF-Dateien im Ordner gefunden.")
        return

    print(f"Gefundene AVIF-Dateien: {len(files)}")

    for avif_path in files:
        print(f"Konvertiere: {avif_path.name}")

        try:
            with Image.open(avif_path) as img:
                img = img.convert("RGB")

                webp_path = avif_path.with_suffix(".webp")
                img.save(webp_path, "WEBP", quality=QUALITY)

            backup_path = BACKUP_DIR / avif_path.name
            avif_path.rename(backup_path)

            print(f"  → Fertig: {webp_path.name}")

        except Exception as e:
            print(f"FEHLER bei {avif_path.name}: {e}")

    print("\nKonvertierung abgeschlossen.")
    print(f"AVIF-Dateien wurden verschoben nach: {BACKUP_DIR}")


if __name__ == "__main__":
    main()
