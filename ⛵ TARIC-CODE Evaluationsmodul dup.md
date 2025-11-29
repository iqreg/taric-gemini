# TARIC Evaluationsmodul

Dieses Modul erweitert das bestehende Projekt **taric-gemini** um eine vollständige Oberfläche und API zur **Nachkontrolle** der automatischen TARIC-Klassifikation durch Zollprofis und Supervisor:innen.

Ziele:

- Bereits klassifizierte Bilder aus `taric_live.db` gezielt nachbearbeiten.
- Bild + TARIC-Daten komfortabel anzeigen.
- Pro Datensatz festhalten:
  - wie viele Stellen (0–10) des TARIC-Codes korrekt sind (Zollprofi),
  - optionale Supervisor-Bewertung (0–10),
  - Reviewer-Name/Kürzel,
  - Kommentar.
- Sowohl unbewertete als auch bereits bewertete Datensätze laden und korrigieren.


---

## 1. Komponentenüberblick

Das Evaluationsmodul besteht aus drei Hauptkomponenten:

1. **Datenbank**
   - Haupttabelle: `taric_live`
   - Evaluations-Tabelle: `taric_evaluation`
   - Datei: `taric_live.db` (im Projekt-Root)

2. **Backend (FastAPI)**
   - Datei: `backend.py`
   - Neue Endpunkte:
     - `GET /api/evaluation/items`
     - `POST /api/evaluation/save`
   - Nutzt dieselbe DB wie die Klassifikation (`taric_live.db`)

3. **Frontend**
   - Datei: `evaluation.html`
   - Statisches HTML/CSS/JS
   - Läuft über `python3 -m http.server` (Port 8080)
   - Kommuniziert mit dem Backend über Port 8000


---

## 2. Datenbankstruktur

### 2.1 Tabelle `taric_live`

Diese Tabelle wird bereits von der automatischen Klassifikation verwendet.

```sql
CREATE TABLE IF NOT EXISTS taric_live (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at        TEXT,
    filename          TEXT,
    taric_code        TEXT,
    cn_code           TEXT,
    hs_chapter        TEXT,
    confidence        REAL,
    short_reason      TEXT,
    alternatives_json TEXT,
    raw_response_json TEXT
);
```

- `filename`: Dateiname des gespeicherten Bildes (im Ordner `bilder_uploads/`).
- `taric_code`: 10-stelliger TARIC-Code.
- `cn_code`: 8-stelliger KN-Code.
- `hs_chapter`: 2-stelliges HS-Kapitel.
- `alternatives_json`: JSON mit möglichen Alternativen.
- `raw_response_json`: Vollständige Antwort des LLM-Modells.

### 2.2 Tabelle `taric_evaluation`

Diese Tabelle hält die **menschliche Bewertung** der KI-Ergebnisse.

```sql
CREATE TABLE IF NOT EXISTS taric_evaluation (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    taric_live_id         INTEGER NOT NULL,
    correct_digits        INTEGER NOT NULL,
    reviewer              TEXT,
    comment               TEXT,
    reviewed_at           TEXT DEFAULT CURRENT_TIMESTAMP,
    superviser_bewertung  INTEGER,
    UNIQUE (taric_live_id)
);
```

- `taric_live_id`: Referenz auf `taric_live.id`.
- `correct_digits`: Anzahl korrekter Stellen (0–10), aus Sicht des Zollprofis.
- `reviewer`: Name/Kürzel der bewertenden Person.
- `comment`: Freitextkommentar.
- `reviewed_at`: Zeitstempel der letzten Änderung.
- `superviser_bewertung`: optionale zweite Bewertung (0–10) durch Supervisor.

#### 2.2.1 Migration bestehender DB

Falls `taric_evaluation` bereits ohne `superviser_bewertung` existierte:

```bash
sqlite3 taric_live.db "ALTER TABLE taric_evaluation ADD COLUMN superviser_bewertung INTEGER;"
```


---

## 3. Backend: API-Endpunkte

### 3.1 GET `/api/evaluation/items`

Liefert eine Liste von Datensätzen aus `taric_live` (inkl. Evaluationsdaten aus `taric_evaluation`).

**Query-Parameter:**

- `limit` (int, optional, default: 50)
- `offset` (int, optional, default: 0)
- `only_unreviewed` (bool)
- `only_reviewed` (bool)

**Filterlogik:**

- `only_unreviewed=true` → nur Datensätze ohne Bewertung  
- `only_reviewed=true` → nur Datensätze mit Bewertung  
- beide false → alle Datensätze

**Response (Beispiel):**

```json
[
  {
    "id": 1,
    "created_at": "2025-11-26 12:46:40",
    "filename": "1764161187_20251125_133402.jpg",
    "taric_code": "8210000000",
    "cn_code": "82100000",
    "hs_chapter": "82",
    "confidence": 0.95,
    "short_reason": "...",
    "alternatives_json": "...",
    "evaluation_id": 10,
    "correct_digits": 8,
    "reviewer": "AB",
    "comment": "…",
    "reviewed_at": "2025-11-27 09:30:00",
    "superviser_bewertung": 9
  }
]
```

---

### 3.2 POST `/api/evaluation/save`

Speichert oder aktualisiert eine Bewertung.

**Request Body Beispiel:**

```json
{
  "taric_live_id": 1,
  "correct_digits": 7,
  "reviewer": "AB",
  "comment": "TARIC bis Position 7 korrekt.",
  "superviser_bewertung": 8
}
```

Backend-Logik:

- existiert Bewertung? → UPDATE
- sonst → INSERT

**Response:**

```json
{ "status": "ok", "action": "created", "taric_live_id": 1 }
```


---

## 4. Frontend: `evaluation.html`

### 4.1 Aufgaben & Use-Case

- Darstellung aller TARIC-Datensätze mit Bildern.
- Bewertung durch den Zollprofi.
- Optionale Supervisor-Korrektur.
- Navigation durch Datensätze.
- Filterfunktionen:
  - „Nur unbewertete“
  - „Nur bewertete“
  - „Alle“

### 4.2 Funktionen

- Bildanzeige (`bilder_uploads/<filename>`)
- Anzeige aller wichtigen TARIC-Felder
- Auswahl der korrekt bewerteten Stellen (0–10)
- optional: Supervisor (0–10)
- Reviewer + Kommentar
- Buttons:
  - Speichern
  - Speichern & weiter
  - Zurück
  - Weiter

### 4.3 Technische Umsetzung

- Vollständig in **Vanilla JS**
- Nutzung der Backend-API
- Bilder werden über denselben HTTP-Server geliefert wie die HTML-Datei
- Keine externen Libraries

---

## 5. Technischer Architekturplan

### 5.1 Komponenten

| Komponente        | Aufgabe |
|------------------|---------|
| `evaluation.html` | UI, Logik des Review-Workflows |
| `backend.py`      | API, DB-Zugriffe, Upsert-Logik |
| `taric_live.db`   | Persistente Klassifikations- und Evaluationsdaten |
| `/bilder_uploads` | Bildspeicher |

### 5.2 Datenfluss

```text
index.html → /classify → taric_live.db
evaluation.html → /api/evaluation/items → Anzeige
evaluation.html → /api/evaluation/save → taric_evaluation
```

### 5.3 Erweiterbarkeit

- zusätzliche Bewertungsstufen
- Auswertungs-Reports
- CSV/PDF-Export
- Hotkeys
- Filter pro Warengruppe, Confidence-Bereich, u. a.

---

## 6. Lokales Setup & Start

### 6.1 Backend starten

```bash
cd ~/projects/taric-gemini
source .venv_taric/bin/activate
uvicorn backend:app --reload --host 0.0.0.0 --port 8000
```

### 6.2 Frontend starten

```bash
cd ~/projects/taric-gemini
python3 -m http.server 8080 --bind 0.0.0.0
```

### 6.3 Zugriff

- Evaluation:  
  `http://<IP>:8080/evaluation.html`
- Klassifikation:  
  `http://<IP>:8080/index.html`

---

## 7. Git-Workflow & Deployment

### 7.1 Branch prüfen

```bash
git branch
```

### 7.2 Änderungen committen

```bash
git add backend.py evaluation.html README.md
git commit -m "Add TARIC evaluation module"
```

### 7.3 Branch pushen

```bash
git push origin feature/auswertung-db
```

### 7.4 Optional: Merge in main

```bash
git checkout main
git pull --rebase origin main
git merge feature/auswertung-db
git push origin main
```

### 7.5 Optional: Release Tag

```bash
git tag -a v1.1.0 -m "Evaluation module added"
git push origin v1.1.0
```

---

## 8. Kurzanleitung für den Zollprofi

1. `evaluation.html` öffnen.
2. Filter „Nur unbewertete“ auswählen.
3. Bild + TARIC prüfen.
4. korrekte Stellen (0–10) wählen.
5. optional Supervisor-Bewertung eintragen.
6. Reviewer + Kommentar ausfüllen.
7. Speichern & weiter.

---

## 9. Status

Das Evaluationsmodul ist vollständig implementiert, dokumentiert und bereit für Deployment & Review.
