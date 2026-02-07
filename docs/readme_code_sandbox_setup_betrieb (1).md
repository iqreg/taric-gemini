# FastAPI Backend – CodeSandbox Setup & Betrieb

Diese README ist die **empfohlene, vollständige Referenzdokumentation** für das Projekt.  
Sie ist bewusst **einsteigerfreundlich**, **schrittweise** aufgebaut und beschreibt den **aktuellen, stabil funktionierenden Stand** in **CodeSandbox**.

> Ziel: *Repository öffnen → wenige Befehle → System läuft zuverlässig.*

---

## 1. Überblick

**Technologie-Stack**

- **Python:** 3.11.x (CodeSandbox Standard)
- **Framework:** FastAPI
- **ASGI-Server:** Uvicorn
- **Parsing / Scraping:** BeautifulSoup4, lxml
- **AI / APIs:** OpenAI, Google Generative AI
- **Betrieb:** CodeSandbox (Debian-basiert)

**Wichtige Rahmenbedingungen**

- Betrieb erfolgt **ohne virtuelle Umgebung (venv)**
- Python-System ist durch **PEP 668** geschützt
- Pakete werden bewusst mit `--break-system-packages` installiert
- Änderungen an GitHub sind **nicht zwingend erforderlich**, aber möglich

---

## 2. Projektstruktur (vereinfacht)

```
workspace/
├── backend.py          # FastAPI-Anwendung (app = FastAPI())
├── requirements.txt   # Vollständige Abhängigkeiten
├── README.md          # Diese Dokumentation
```

---

## 3. Git-Status prüfen (Orientierung)

```bash
git status
git branch --show-current
git rev-parse --short HEAD
```

Erwartung:
- Branch: `codesandbox`
- Working tree: `clean`

Damit ist sichergestellt, dass du auf dem vorgesehenen Stand arbeitest.

---

## 4. Python-Umgebung prüfen

CodeSandbox bringt Python bereits mit.

```bash
python3 -V
python3 -m pip -V
```

Beispiel:
```
Python 3.11.2
pip 23.x
```

Falls `pip` fehlt, kann es installiert werden:

```bash
sudo apt-get update
sudo apt-get install -y python3-pip
```

---

## 5. Abhängigkeiten installieren

Alle notwendigen Abhängigkeiten sind in `requirements.txt` definiert.

**Wichtig (CodeSandbox / Debian / PEP 668):**
Systemweite Installation erfordert das Flag `--break-system-packages`.

```bash
python3 -m pip install --break-system-packages -r requirements.txt
```

Typische installierte Pakete:
- fastapi
- uvicorn
- beautifulsoup4
- lxml
- python-multipart
- google-* / openai

---

## 6. Backend-Import testen (wichtig!)

Vor dem Start wird geprüft, ob das Backend korrekt geladen werden kann:

```bash
python3 - << 'EOF'
import backend
print("backend import OK")
print("app:", getattr(backend, "app", None))
EOF
```

Erwartete Ausgabe:
```
backend import OK
app: <fastapi.applications.FastAPI object at ...>
```

Wenn hier ein Fehler auftritt, fehlt in der Regel eine Dependency.

---

## 7. Backend starten

```bash
python3 -m uvicorn backend:app --host 0.0.0.0 --port 8000 --reload
```

Erwartete Konsolenausgabe:
```
Uvicorn running on http://0.0.0.0:8000
```

---

## 8. Anwendung im Browser öffnen

In CodeSandbox:

1. Tab **PORTS** öffnen
2. Port **8000** auswählen
3. **Open** klicken

Nützliche URLs:

- **Swagger UI:** `/docs`
- **OpenAPI JSON:** `/openapi.json`

---

## 9. Typische Fehler & Lösungen

### Fehler: `ModuleNotFoundError: No module named 'xyz'`

Ursache: Abhängigkeit fehlt.

Lösung:
```bash
python3 -m pip install --break-system-packages xyz
```

Danach erneut **Abschnitt 6** ausführen.

---

### Fehler: `Form data requires "python-multipart"`

Ursache: Formular-/Upload-Endpunkte.

Lösung:
```bash
python3 -m pip install --break-system-packages python-multipart
```

---

### Fehler: `Error loading ASGI app. Could not import module "backend"`

Mögliche Ursachen:
- `backend.py` liegt nicht im Projekt-Root
- FastAPI-Instanz heißt nicht `app`

Prüfen:
```bash
ls -la backend.py
grep -R "FastAPI(" -n backend.py
```

---

## 10. Warum hier **keine venv** verwendet wird

In **CodeSandbox** gilt:

- isolierte Umgebung
- kein produktives System
- schnelle Reproduzierbarkeit wichtiger als formale Trennung

Daher ist der bewusste Einsatz von:

```bash
--break-system-packages
```

akzeptabel.

⚠️ **Außerhalb von CodeSandbox (lokal / Produktion) wird dringend eine venv empfohlen.**

---

## 11. Empfohlener Standard-Workflow

```bash
# Abhängigkeiten installieren
python3 -m pip install --break-system-packages -r requirements.txt

# Backend starten
python3 -m uvicorn backend:app --host 0.0.0.0 --port 8000 --reload
```

---

## 12. Nächste sinnvolle Erweiterungen (optional)

- `.env` / Secrets-Handling
- Trennung `dev` / `prod` Requirements
- Dockerfile für reproduzierbare Builds
- CI/CD (GitHub Actions)
- Logging & Monitoring

---

## Status

✅ System lauffähig in CodeSandbox  
✅ Dokumentation entspricht dem **aktuellen, getesteten Stand**

---

**Ende der Referenzdokumentation**

