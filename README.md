# taric-gemini (CodeSandbox + GitHub robust setup)

Dieses Repository enthält jetzt einen robusten Batch-Workflow mit persistenten Pfaden unter `/project/workspace`.

## 1) Vorbereitung in CodeSandbox

```bash
pip install -r requirements.txt
bash scripts/bootstrap.sh
```

Optional notwendige Variablen setzen:

```bash
export GEMINI_API_KEY="..."
export GEMINI_MODEL_NAME="gemini-2.5-flash-lite"
export IMAGE_DIR="/project/workspace/data/raw/taric_bulk_avif_backup"
export DB_PATH="/project/workspace/db/taric_dataset.db"
export RESULTS_DIR="/project/workspace/results"
export SKIP_EXISTING="true"
export REQUEST_DELAY_SECONDS="0.4"
```

## 2) Batch-Klassifikation starten

```bash
python3 scripts/classify_batch.py
```

Optional alles neu verarbeiten (ohne Skip):

```bash
python3 scripts/classify_batch.py --force
```

## 3) Persistente Outputs

Das Script schreibt nach:

- DB: `/project/workspace/db/taric_dataset.db`
- JSONL: `/project/workspace/results/classifications.jsonl`
- CSV: `/project/workspace/results/classifications.csv`
- Fehler: `/project/workspace/results/failed_files.jsonl`
- Lauf-Metadaten: `/project/workspace/results/run_manifest.json`

## 4) DB aus JSONL vollständig neu aufbauen

```bash
python3 scripts/rebuild_db_from_jsonl.py
```

Dabei wird `DB_PATH` komplett aus `RESULTS_DIR/classifications.jsonl` neu erzeugt.

## Hinweise

- Keine Secrets im Repo speichern.
- `GEMINI_API_KEY` nur per Environment Variable setzen.
- Unterstützte Bildformate: `jpg`, `jpeg`, `png`, `webp`, `avif`, `gif`.
