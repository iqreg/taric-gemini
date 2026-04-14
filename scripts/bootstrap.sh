#!/usr/bin/env bash
set -euo pipefail

IMAGE_DIR="${IMAGE_DIR:-/project/workspace/data/raw/taric_bulk_avif_backup}"
DB_PATH="${DB_PATH:-/project/workspace/db/taric_dataset.db}"
RESULTS_DIR="${RESULTS_DIR:-/project/workspace/results}"

mkdir -p "$IMAGE_DIR"
mkdir -p "$(dirname "$DB_PATH")"
mkdir -p "$RESULTS_DIR"

python3 scripts/classify_batch.py --init-db-only

echo "Bootstrap OK"
echo "IMAGE_DIR=$IMAGE_DIR"
echo "DB_PATH=$DB_PATH"
echo "RESULTS_DIR=$RESULTS_DIR"

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  echo "Hinweis: GEMINI_API_KEY ist nicht gesetzt (nur DB-Init wurde geprüft)."
else
  echo "GEMINI_API_KEY ist gesetzt."
fi

echo "MODEL=${GEMINI_MODEL_NAME:-gemini-2.5-flash-lite}"
echo "SKIP_EXISTING=${SKIP_EXISTING:-true}"
echo "REQUEST_DELAY_SECONDS=${REQUEST_DELAY_SECONDS:-0.4}"
