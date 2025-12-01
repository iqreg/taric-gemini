#!/bin/zsh
#
# Exportiert die TARIC-Live-Datenbank + zugehörige Bilder in ein ZIP-Archiv.
# Inhalte:
#   - taric_live.db
#   - bilder_uploads/
#   - README mit Metadaten (Anzahl Datensätze, Bilder, Zeitstempel)

set -euo pipefail

# Projekt-Root relativ zur Skriptposition bestimmen
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

DB_FILE="taric_live.db"
IMG_DIR="bilder_uploads"
EXPORT_BASE_DIR="$SCRIPT_DIR/export"

# 1) Vorprüfungen
echo "== TARIC Export-Skript =="

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "FEHLER: sqlite3 ist nicht installiert oder nicht im PATH."
  echo "Bitte sqlite3 installieren (z.B. über Homebrew: brew install sqlite)."
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

# 2) Metadaten auslesen
echo "Lese Metadaten aus Datenbank..."

LIVE_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM taric_live;")
EVAL_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM taric_evaluation;")
IMG_COUNT=$(find "$IMG_DIR" -type f | wc -l | tr -d ' ')

TS="$(date +'%Y%m%d_%H%M%S')"
EXPORT_DIR="$EXPORT_BASE_DIR/taric_export_$TS"
README_FILE="$EXPORT_DIR/README_taric_export_$TS.txt"
ARCHIVE_FILE="$EXPORT_BASE_DIR/taric_export_$TS.zip"

# 3) Export-Verzeichnis vorbereiten
echo "Erzeuge Export-Verzeichnis: $EXPORT_DIR"
mkdir -p "$EXPORT_DIR"

# 4) Dateien hinein kopieren
echo "Kopiere Datenbank..."
cp "$DB_FILE" "$EXPORT_DIR/"

echo "Kopiere Bilder (dies kann je nach Anzahl einen Moment dauern)..."
mkdir -p "$EXPORT_DIR/$IMG_DIR"
# rsync ist effizienter, falls vorhanden, sonst fallback auf cp
if command -v rsync >/dev/null 2>&1; then
  rsync -a "$IMG_DIR"/ "$EXPORT_DIR/$IMG_DIR"/
else
  cp -R "$IMG_DIR"/ "$EXPORT_DIR/$IMG_DIR"/
fi

# 5) README mit Metadaten erzeugen
cat > "$README_FILE" <<EOF
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
EOF

# 6) ZIP-Archiv erzeugen
echo "Erzeuge ZIP-Archiv: $ARCHIVE_FILE"
mkdir -p "$EXPORT_BASE_DIR"
(
  cd "$EXPORT_BASE_DIR"
  zip -r "taric_export_$TS.zip" "taric_export_$TS" >/dev/null
)

echo
echo "FERTIG."
echo "Export-Verzeichnis: $EXPORT_DIR"
echo "ZIP-Archiv        : $ARCHIVE_FILE"
echo
echo "Diese ZIP-Datei kannst du z.B. sichern, verschicken oder für Trainingszwecke verwenden."
