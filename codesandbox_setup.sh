#!/usr/bin/env bash

#richtet die sandbox umgebung ein 
#strarten mit _
#- chmod +x codesandbox_setup.sh
# ./codesandbox_setup.sh
# 
#Hinweis zur CodeSandbox-“Standard”-Umgebung
#Dass du --break-system-packages brauchst, liegt an Debian/PEP 668 (systemweit pip ist gesperrt). 
#Das Script kapselt das.
#Wenn du willst, kann ich dir auch eine passende .vscode/tasks.json-Taskdefinition geben, die genau diese Scripts nutzt.

set -euo pipefail

echo "[1/4] Python prüfen"
python3 -V

echo "[2/4] pip verfügbar?"
if ! python3 -m pip -V >/dev/null 2>&1; then
  echo "pip fehlt -> installiere python3-pip"
  sudo apt-get update
  sudo apt-get install -y python3-pip
fi

echo "[3/4] Basis-Tools aktualisieren"
python3 -m pip install --break-system-packages -U pip setuptools wheel

echo "[4/4] Projekt-Dependencies installieren"
python3 -m pip install --break-system-packages -r requirements.txt

echo "[+] Zusätzliche Laufzeit-Abhängigkeiten (Backend) sicherstellen"
python3 -m pip install --break-system-packages \
  fastapi "uvicorn[standard]" beautifulsoup4 lxml python-multipart

echo "[OK] Setup fertig."
echo "Start: python3 -m uvicorn backend:app --host 0.0.0.0 --port 8000 --reload"
