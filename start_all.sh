#!/bin/zsh
echo "This script is for local macOS only. Use: python3 -m uvicorn backend:app --host 0.0.0.0 --port 8000"
exit 1

set -euo pipefail

# ─────────────────────────────────────────────
# ANSI Farben
# ─────────────────────────────────────────────
RED="\033[31m"
GREEN="\033[32m"
YELLOW="\033[33m"
BLUE="\033[34m"
MAGENTA="\033[35m"
CYAN="\033[36m"
WHITE="\033[37m"
RESET="\033[0m"
BOLD="\033[1m"

# ─────────────────────────────────────────────
# Pfade
# ─────────────────────────────────────────────
PROJECT_DIR="/Users/qb/projects/taric-gemini"
VENV_DIR="$PROJECT_DIR/.venv_taric"

BACKEND_LOG="$PROJECT_DIR/backend.log"
FRONTEND_LOG="$PROJECT_DIR/frontend.log"
CF_FE_LOG="$PROJECT_DIR/cf_frontend.log"
CF_BE_LOG="$PROJECT_DIR/cf_backend.log"
GEMINI_KEY_FILE="$PROJECT_DIR/API_GEMINI.txt"

echo ""
echo "${MAGENTA}${BOLD}─────────────────────────────────────────────${RESET}"
echo "${CYAN}${BOLD}       TARIC-Gemini FULL STARTER${RESET}"
echo "${MAGENTA}${BOLD}─────────────────────────────────────────────${RESET}"
echo ""

cd "$PROJECT_DIR"

# ─────────────────────────────────────────────
# Alte Prozesse beenden
# ─────────────────────────────────────────────
echo "${YELLOW}Beende alte Prozesse ...${RESET}"

pkill -f "uvicorn backend:app" || true
pkill -f "python3 -m http.server 8080" || true
pkill -f "cloudflared tunnel --url http://localhost:8080" || true
pkill -f "cloudflared tunnel --url http://localhost:8000" || true

: > "$BACKEND_LOG"
: > "$FRONTEND_LOG"
: > "$CF_FE_LOG"
: > "$CF_BE_LOG"

echo "${GREEN}✓ Alte Prozesse beendet${RESET}"
echo ""

# ─────────────────────────────────────────────
# venv aktivieren
# ─────────────────────────────────────────────
echo "${BLUE}Aktiviere Python venv ...${RESET}"

if [ -f "$VENV_DIR/bin/activate" ]; then
  source "$VENV_DIR/bin/activate"
  echo "${GREEN}✓ venv aktiviert${RESET}"
else
  echo "${RED}${BOLD}FEHLER:${RESET} venv nicht gefunden unter $VENV_DIR"
  exit 1
fi

echo ""

# ─────────────────────────────────────────────
# GEMINI API KEY
# ─────────────────────────────────────────────
echo "${BLUE}Lade GEMINI API-KEY ...${RESET}"

if [ ! -f "$GEMINI_KEY_FILE" ]; then
  echo "${RED}${BOLD}FEHLER:${RESET} API_GEMINI.txt wurde nicht gefunden!"
  exit 1
fi

export GEMINI_API_KEY="$(cat "$GEMINI_KEY_FILE" | tr -d '[:space:]')"

if [ -z "$GEMINI_API_KEY" ]; then
  echo "${RED}${BOLD}FEHLER:${RESET} GEMINI_API_KEY ist leer!"
  exit 1
fi

MASKED_KEY="********${GEMINI_API_KEY: -6}"
echo "${GREEN}✓ GEMINI API-KEY geladen${RESET}: ${YELLOW}${MASKED_KEY}${RESET}"
echo ""

# ─────────────────────────────────────────────
# Backend starten
# ─────────────────────────────────────────────
echo "${CYAN}${BOLD}Starte Backend (Uvicorn auf Port 8000)...${RESET}"

uvicorn backend:app --reload --host 0.0.0.0 --port 8000 > "$BACKEND_LOG" 2>&1 &

echo "${GREEN}✓ Backend läuft${RESET}"
echo ""
sleep 2

# ─────────────────────────────────────────────
# Frontend starten
# ─────────────────────────────────────────────
echo "${CYAN}${BOLD}Starte Frontend (http.server auf Port 8080)...${RESET}"

python3 -m http.server 8080 --bind 0.0.0.0 > "$FRONTEND_LOG" 2>&1 &

echo "${GREEN}✓ Frontend läuft${RESET}"
echo ""

# ─────────────────────────────────────────────
# Cloudflare Tunnel: Frontend
# ─────────────────────────────────────────────
echo "${CYAN}${BOLD}Starte Cloudflare Tunnel für Frontend :8080...${RESET}"

cloudflared tunnel --url http://localhost:8080 > "$CF_FE_LOG" 2>&1 &

echo "${GREEN}✓ Cloudflare Frontend-Tunnel gestartet${RESET}"
echo ""

# ─────────────────────────────────────────────
# Cloudflare Tunnel: Backend
# ─────────────────────────────────────────────
echo "${CYAN}${BOLD}Starte Cloudflare Tunnel für Backend :8000...${RESET}"

cloudflared tunnel --url http://localhost:8000 > "$CF_BE_LOG" 2>&1 &

echo "${GREEN}✓ Cloudflare Backend-Tunnel gestartet${RESET}"
echo ""

# ─────────────────────────────────────────────
# Warten auf URLs
# ─────────────────────────────────────────────
echo "${YELLOW}Warte 15 Sekunden, bis Cloudflare-URLs verfügbar sind ...${RESET}"
sleep 15
echo ""

# ─────────────────────────────────────────────
# send_link.py
# ─────────────────────────────────────────────
echo "${CYAN}${BOLD}Sende E-Mail mit Frontend-Link ...${RESET}"

# python3 send_link.py "$CF_FE_LOG"
python3 send_link.py "$CF_FE_LOG" "$CF_BE_LOG"


echo ""
echo "${MAGENTA}${BOLD}────────────────-─────-──────────────────────────────${RESET}"
echo "${GREEN}${BOLD}      ✓ ALLES GESTARTET — FERTIG${RESET}"
echo "${MAGENTA}${BOLD}───────────────────-─────────────────────────────────${RESET}"
echo "${YELLOW}${BOLD}      Logs in backend.log, frontend.log, cf_frontend.log, cf_backend.log${RESET}"
echo "${YELLOW}${BOLD}      Stoppen mit Ctrl+C oder später ./start_all.sh erneut ausführen${RESET}"
echo "${MAGENTA}${BOLD}───────────────────────-─────────────────────────────${RESET}"
echo "${RED}${BOLD}      pkill -f \"uvicorn backend:app\" || true${RESET}"
echo "${RED}${BOLD}      pkill -f \"python3 -m http.server 8080\" || true${RESET}"
echo "${RED}${BOLD}      pkill -f \"cloudflared tunnel --url http://localhost:8080\" || true${RESET}"
echo "${RED}${BOLD}      pkill -f \"cloudflared tunnel --url http://localhost:8000\" || true${RESET}"
echo "${MAGENTA}${BOLD}─────────────────────────-───────────────────────────${RESET}"
echo ""
