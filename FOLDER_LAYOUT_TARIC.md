# 📁 TARIC – Ordnerlayout & Workflow  
**Version 2025-11-29**

Dieses Dokument beschreibt die **verbindliche Ordnerstruktur** der TARIC-Bildklassifizierung, damit die drei Module

- `highend_bildconverter_taric.py`
- `bulk-evaluation.py`
- `backend.py`

sauber getrennt laufen, ohne gegenseitige Überschneidungen oder Datenkonflikte.

Ziel:  
**Klare Verantwortlichkeiten, reproduzierbarer Workflow, keine Dateikollisionen.**

---

# 1. Gesamtstruktur

```text
taric-gemini/
├── backend.py
├── bulk-evaluation.py
├── highend_bildconverter_taric.py
├── taric_live.db
│
├── bilder_uploads/                 # Nur Backend: Sofort-Uploads von /classify
│
└── data/
    ├── taric_bulk_source/          # Rohmaterial (AVIF / JPG / PNG / WEBP)
    ├── taric_bulk_input/           # Converter-Ergebnis (NUR WEBP → Bulk liest hier)
    ├── taric_bulk_done/            # Erfolgreich klassifizierte Bilder
    ├── taric_bulk_error/           # Dauerhafte Fehlerbilder
    ├── taric_bulk_originals/       # Archivierte Originale nach Konversion
    └── taric_bulk_log.csv          # Logfile aller Bulk-Abläufe
