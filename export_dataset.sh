#!/bin/zsh
#
# Exportiert die TARIC-Live-Datenbank + zugehörige Bilder in ein ZIP-Archiv.
# Inhalte:
#   - taric_live.db
#   - bilder_uploads/
#   - README mit Metadaten (Anzahl Datensätze, Bilder, Zeitstempel)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

DB_FILE="taric_live.db"
IMG_DIR="bilder_uploads"
EXPORT_BASE_DIR="$SCRIPT_DIR/export"

echo "== TARIC Export-Skript =="

if ! command -v python3 >/dev/null 2>&1; then
  echo "FEHLER: python3 ist nicht installiert oder nicht im PATH."
  exit 1
fi

if [ ! -f "$DB_FILE" ]; then
  echo "FEHLER: Datenbank '$DB_FILE' wurde nicht gefunden im Verzeichnis:"
  echo "       $SCRIPT_DIR"
  exit 1
fi

if [ ! -d "$IMG_DIR" ]; then
  echo "FEHLER: Bildverzeichnis '$IMG_DIR' wurde nicht gefunden im Verzeichnis:"
  echo "       $SCRIPT_DIR"
  exit 1
fi

echo "Lese Metadaten aus Datenbank..."

read -r LIVE_COUNT EVAL_COUNT IMG_COUNT <<EOF_COUNTS
$(python3 - <<'PY'
import os
import sqlite3
from pathlib import Path

db_file = Path("taric_live.db")
img_dir = Path("bilder_uploads")

conn = sqlite3.connect(db_file)
cur = conn.cursor()

def count_or_zero(table: str) -> int:
    try:
        return cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except sqlite3.OperationalError:
        return 0

live_count = count_or_zero("taric_live")
eval_count = count_or_zero("taric_evaluation")
conn.close()

img_count = 0
for _root, _dirs, files in os.walk(img_dir):
    img_count += len(files)

print(live_count, eval_count, img_count)
PY
)
EOF_COUNTS

TS="$(date +'%Y%m%d_%H%M%S')"
EXPORT_DIR="$EXPORT_BASE_DIR/taric_export_$TS"
README_FILE="$EXPORT_DIR/README_taric_export_$TS.txt"
ARCHIVE_FILE="$EXPORT_BASE_DIR/taric_export_$TS.zip"

echo "Erzeuge Export-Verzeichnis: $EXPORT_DIR"
mkdir -p "$EXPORT_DIR"

echo "Kopiere Datenbank..."
cp "$DB_FILE" "$EXPORT_DIR/"

echo "Kopiere Bilder (dies kann je nach Anzahl einen Moment dauern)..."
mkdir -p "$EXPORT_DIR/$IMG_DIR"
if command -v rsync >/dev/null 2>&1; then
  rsync -a "$IMG_DIR"/ "$EXPORT_DIR/$IMG_DIR"/
else
  cp -R "$IMG_DIR"/ "$EXPORT_DIR/$IMG_DIR"/
fi

cat > "$README_FILE" <<EOF_README
TARIC-Live Export
=================

Zeitpunkt des Exports: $(date +'%Y-%m-%d %H:%M:%S')
Projektverzeichnis    : $SCRIPT_DIR

Inhalte
-------

1) Datenbank:
   - Datei: taric_live.db
   - Tabelle taric_live        : $LIVE_COUNT Datensätze
   - Tabelle taric_evaluation  : $EVAL_COUNT Datensätze

2) Bilder:
   - Verzeichnis: bilder_uploads/
   - Anzahl Dateien: $IMG_COUNT

Hinweise
--------

- Die Spalte 'filename' in der Tabelle 'taric_live' verweist direkt
  auf Dateien im Verzeichnis 'bilder_uploads/'.
- Evaluationsdaten sind über 'taric_evaluation.taric_live_id'
  mit 'taric_live.id' verknüpft.
EOF_README

echo "Erzeuge ZIP-Archiv: $ARCHIVE_FILE"
mkdir -p "$EXPORT_BASE_DIR"
python3 - <<PY
from pathlib import Path
import zipfile

export_dir = Path("$EXPORT_DIR")
archive_file = Path("$ARCHIVE_FILE")

with zipfile.ZipFile(archive_file, "w", zipfile.ZIP_DEFLATED) as zf:
    for p in export_dir.rglob("*"):
        zf.write(p, p.relative_to(export_dir.parent))
PY

echo
echo "FERTIG."
echo "Export-Verzeichnis: $EXPORT_DIR"
echo "ZIP-Archiv        : $ARCHIVE_FILE"
echo
echo "Diese ZIP-Datei kannst du z.B. sichern, verschicken oder für Trainingszwecke verwenden."
