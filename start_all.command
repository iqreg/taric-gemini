#!/bin/bash
echo "This script is for local macOS only. Use: python3 -m uvicorn backend:app --host 0.0.0.0 --port 8000"
exit 1

# Absoluter Projektpfad
PROJECT_DIR="/Users/qb/projects/taric-gemini"
VENV="$PROJECT_DIR/.venv_taric/bin/activate"

echo "Starte TARIC-System..."
cd "$PROJECT_DIR" || exit 1

# Hilfsfunktion: neues Terminal-Fenster öffnen mit bestimmtem Profil + Befehl
run_profile_terminal () {
  PROFILE="$1"
  COMMAND="$2"

  osascript <<EOF
tell application "Terminal"
    activate
    set newWindow to do script "cd $PROJECT_DIR; source $VENV; $COMMAND"
    delay 0.1
    set current settings of newWindow to settings set "$PROFILE"
end tell
EOF
}

### TERMINAL 1 – Backend → Ocean
run_profile_terminal "Ocean" \
"export GEMINI_API_KEY=\$(cat API_GEMINI.txt); \
echo 'GEMINI_API_KEY geladen: '\$GEMINI_API_KEY; \
uvicorn backend:app --reload --host 0.0.0.0 --port 8000"

### TERMINAL 2 – Bildkonverter-Watcher → Homebrew
run_profile_terminal "Homebrew" \
"./highend_bildconverter_watcher.py"

### TERMINAL 3 – Bulk-Evaluation-Watcher → Red Sands
run_profile_terminal "Red Sands" \
"./bulk_evaluation_watcher.py"

### TERMINAL 4 – Frontend-Server + IP-Anzeige → Grass
run_profile_terminal "Grass" \
"IP=\$(ipconfig getifaddr en0); \
echo '---------------------------------------------'; \
echo 'Frontend gestartet:'; \
echo 'PC / Mac:     http://127.0.0.1:8080/index.html'; \
echo 'Mobile Geräte: http://'\$IP':8080/index.html'; \
echo 'Backend API:   http://'\$IP':8000'; \
echo '---------------------------------------------'; \
python3 -m http.server 8080 --bind 0.0.0.0"

echo "Alle Prozesse gestartet!"
exit 0
