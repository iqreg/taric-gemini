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

## 5) Ergebnisse in Evaluation/Auswertung sichtbar machen

Die UI-Routen `/evaluation` und `/auswertung` lesen aus `taric_live.db` (Backend-DB).
Batch-Ergebnisse liegen aber in `DB_PATH` (`taric_dataset.db`).
Für die Anzeige in den Masken daher nach einem Batch-Lauf synchronisieren:

```bash
python3 scripts/sync_classifications_to_live.py
```

Das Script kopiert dabei auch die Bilddateien aus `file_path` nach
`/project/workspace/bilder_uploads`, damit die Karten in `/evaluation`
und auf mobilen Geräten (z. B. Samsung Browser) die Bilder anzeigen können.

## Hinweise

- Keine Secrets im Repo speichern.
- `GEMINI_API_KEY` nur per Environment Variable setzen.
- Unterstützte Bildformate: `jpg`, `jpeg`, `png`, `webp`, `avif`, `gif`.

## Troubleshooting (häufige Ursache für `failed=100`)

- Prüfe, ob ein alter `IMAGE_DIR` exportiert wurde:
  ```bash
  echo "$IMAGE_DIR"
  ```
  Falls leer, greift der Default `/project/workspace/data/raw/taric_bulk_avif_backup`.
- Prüfe API-Key/Modell:
  ```bash
  echo "${GEMINI_API_KEY:+SET}"
  echo "${GEMINI_MODEL_NAME:-gemini-2.5-flash-lite}"
  ```
- Fehlerdetails ansehen:
  ```bash
  head -n 5 /project/workspace/results/failed_files.jsonl
  ```
- Das Batch-Script überspringt nur Datensätze mit `status="ok"`.
  Frühere `failed`-Runs (z. B. ohne API-Key) werden beim nächsten Lauf automatisch erneut versucht.
