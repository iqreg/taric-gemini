#!/bin/zsh
#
# Erstellt alle Ordner für die automatische TARIC-Bulk-Auswertung
# Struktur gemäß Konzept (Variante A)

BASE_DIR="$(pwd)"

echo "Erstelle Bulk-Verzeichnisstruktur unter: $BASE_DIR"

# Datenordner
mkdir -p "$BASE_DIR/data/taric_bulk_input"
mkdir -p "$BASE_DIR/data/taric_bulk_done"
mkdir -p "$BASE_DIR/data/taric_bulk_error"

# Log-Verzeichnisse
mkdir -p "$BASE_DIR/logs/bulk_runs"

echo "Fertig."
echo
echo "Angelegte Ordner:"
echo "  data/taric_bulk_input"
echo "  data/taric_bulk_done"
echo "  data/taric_bulk_error"
echo "  logs/bulk_runs"
