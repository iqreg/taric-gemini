# Projektstatus TARIC-Gemini

## Übersicht

Das Projekt dient der automatisierten Bilderkennung und TARIC-Klassifizierung über ein eigenes Backend (Python/FastAPI + Uvicorn) und ein simples Frontend (lokaler HTTP-Server). Der aktuelle Stand umfasst eine funktionierende Bildübertragung an das Backend, eine stabile Kommunikation mit dem Klassifizierungsmodell sowie funktionierende Netzwerkzugriffe über die lokale IP.

## CODESANDBOX UMGEBUNG VORBEREITEN

## ▶ Verwendung Makefile um die Umgebung aufzusetzen

```bash
make deps
make run-reload
```

## Komponenten

### Backend

- Framework: FastAPI
- Startbefehl:

  ```bash
  uvicorn backend:app --reload --host 0.0.0.0 --port 8000
  ```

- Funktionen:

  - Entgegennahme von Bildern (POST /classify)
  - Speichern der Bilddateien
  - Weiterleitung an Klassifizierungsfunktion

### Frontend

- Lokaler Webserver mittels Python:

  ```bash
  python3 -m http.server 8080 --bind 0.0.0.0
  ```

Frontwnd sollte die ip dre Backendserver Maschine haben, daher automatisch korrekte ip setzen
``bash
[17:47:43] qb@mac ~/projects/taric-gemini % /usr/bin/python3 -m http.server 8080 --bind $(ipconfig getifaddr en0)

Serving HTTP on 192.168.7.124 port 8080 (http://192.168.7.124:8080/) ...

```

* Index-Datei wird korrekt von anderen Geräten im Netzwerk geladen

## Netzwerk & Firewall

* Lokale Mac-IP: Beispiel `192.168.7.124`
* Adressschema für Frontend-Aufruf:

```

http://192.168.7.124:8080/index.html

````
* Firewall-Thema gelöst: Ports korrekt freigegeben
* Wichtig: Bei Änderungen der Firewall-Einträge werden Regeln teilweise automatisch gelöscht → erneute Prüfung notwendig

## Aktueller Stand Backend

* Bildempfang funktioniert:

* Logging zeigt volle Bildbytes
* Dateien werden unter `bilder_uploads/` gespeichert
* Klassifizierungsmodell liefert JSON mit:

* taric_code
* cn_code
* hs_chapter
* confidence
* short_reason
* possible_alternatives

## Beispiel-Response

```json
{
"taric_code": "8517620000",
"cn_code": "85176200",
"hs_chapter": "85",
"confidence": 0.9,
"short_reason": "Dockingstation mit Netzwerkschnittstellen.",
"possible_alternatives": [ ... ]
}
````

## Branch & GitHub

- Ziel: Aktuelle lokale Version (Backend + Frontend + Infrastruktur) in neuen Branch pushen
- Standard-Vorgehen:

  ```bash
  git add .
  git commit -m "Projektstatus aktualisiert, Backend/Frontend stabil"
  git push -u origin <branch-name>
  ```

## Projektordner-Struktur

```
project-root/
│ backend.py
│ index.html
│ bilder_uploads/
│ .venv_taric/
│ kill_http_servers.sh
│ requirements.txt
└─ README.md
```

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

- **Python 3.10+**
- **Google Gemini API Key**

  - erstellen unter [https://aistudio.google.com](https://aistudio.google.com)

- **Virtuelle Umgebung** (empfohlen)

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

- auf Desktop → Doppelklick
- auf Mobile → lokal hochladen oder via `python -m http.server` hosten

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

- API-Keys werden **nicht** in Git gespeichert
- `.venv/`, `*.db` und `bilder/` sind **.gitignore**-geschützt
- Frontend hat **keinen Zugriff** auf den API-Key
- Backend verwaltet den Key über Umgebungsvariablen

---

## 📝 Lizenz

Interne Verwendung – nicht für produktive Zollprozesse vorgesehen.

---

-
