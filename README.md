Hier ist eine klar strukturierte, saubere und vollständige **README.md**, fertig zum Einfügen auf GitHub.
Sie ist so geschrieben, dass ein Kollege ohne Rückfragen sofort versteht, was das Projekt tut und wie er es starten kann.

---

# README.md

# TARIC Gemini – KI-gestützte Klassifikation von Warenbildern

Dieses Projekt ermöglicht die automatische Ermittlung des passenden **TARIC-Codes** anhand eines **Produktfotos**.
Es kombiniert eine minimalistische **Web-App** zur Bildaufnahme (Browser/Kamera) mit einem **FastAPI-Backend**, das Bilder an **Google Gemini** sendet und die Ergebnisse strukturiert speichert.

---

## 🚀 Funktionen

* Foto aufnehmen oder hochladen
* Bild wird per API an Gemini gesendet
* TARIC-Klassifikation in strukturiertem JSON:

  * `taric_code` (10-stellig)
  * `cn_code`
  * `hs_chapter`
  * `confidence`
  * `short_reason`
  * `possible_alternatives[]`
* Vollautomatische Speicherung:

  * Bild wird im Ordner **`bilder/`** abgelegt
  * Klassifikation wird in **`taric_live.db`** (SQLite) gespeichert
* REST-API mit **FastAPI**
* Einfache lokale Web-App (`index.html`) für mobile Nutzung

---

## 📁 Projektstruktur

```
taric-gemini/
 ├── backend.py              # FastAPI KI-Service + Bildspeicherung + DB
 ├── taric_batch_gemini.py   # Batch-Script zur Ordnerklassifikation
 ├── index.html              # Browser-App zum Fotografieren/Testen
 ├── .gitignore
 └── README.md
```

Ordner/Dateien, die automatisch entstehen:

```
taric-gemini/
 ├── bilder/                 # gespeicherte Fotos
 ├── taric_live.db           # SQLite DB mit Ergebnissen
```

---

## 🔧 Voraussetzungen

* **Python 3.10+**
* **Google Gemini API Key**

  * erstellen unter [https://aistudio.google.com](https://aistudio.google.com)
* **Virtuelle Umgebung** (empfohlen)

Abhängigkeiten:

```
fastapi
uvicorn
python-multipart
google-generativeai
```

---

## 📦 Installation

### 1. Repository klonen

```bash
git clone https://github.com/USERNAME/taric-gemini.git
cd taric-gemini
```

### 2. Virtuelle Umgebung erstellen

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Abhängigkeiten installieren

```bash
pip install fastapi "uvicorn[standard]" python-multipart google-generativeai
```

### 4. API-Key setzen

```bash
export GEMINI_API_KEY="DEIN_KEY_HIER"
```

(optional: `.env` oder `API_GEMINI.txt` verwenden)

---

## ▶️ Backend starten

```bash
uvicorn backend:app --reload --host 0.0.0.0 --port 8000
```

Testen:

```bash
http://localhost:8000/health
```

---

## 📸 Web-App nutzen

Die Datei `index.html` kann direkt geöffnet werden:

* auf Desktop → Doppelklick
* auf Mobile → lokal hochladen oder via `python -m http.server` hosten

Workflow:

1. Foto aufnehmen
2. „Senden“ klicken
3. Ergebnis erscheint sofort
4. Bild + TARIC-Daten automatisch gespeichert

---

## 🗄️ Datenbank–Speicherung

Jede Anfrage erzeugt:

### `bilder/yyyy_timestamp_originalname.jpg`

und einen Datenbankeintrag in **`taric_live.db`**:

| Spalte              | Beschreibung                        |
| ------------------- | ----------------------------------- |
| `created_at`        | Zeitstempel                         |
| `filename`          | Bilddateiname im Ordner `bilder/`   |
| `taric_code`        | 10-stelliger TARIC-Code             |
| `cn_code`           | 8-stelliger CN-Code                 |
| `hs_chapter`        | HS-Kapitel                          |
| `confidence`        | Modell-Confidence                   |
| `short_reason`      | kurze Klassifikationserklärung      |
| `alternatives_json` | alternative Codes                   |
| `raw_response_json` | kompletter JSON-Response von Gemini |

---

## 🧪 Batch-Modus (Ordnerverarbeitung)

Mit:

```bash
python taric_batch_gemini.py
```

werden alle Bilder in `bilder/` klassifiziert und in einer separaten DB gespeichert (`taric_dataset.db`).

---

## 🔒 Sicherheit

* API-Keys werden **nicht** in Git gespeichert
* `.venv/`, `*.db` und `bilder/` sind **.gitignore**-geschützt
* Frontend hat **keinen Zugriff** auf den API-Key
* Backend verwaltet den Key über Umgebungsvariablen

---

## 📝 Lizenz

Interne Verwendung – nicht für produktive Zollprozesse vorgesehen.

---




* 