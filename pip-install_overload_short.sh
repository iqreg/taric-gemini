#!/usr/bin/env bash
set -Eeuo pipefail

# ==============================
# pip-install.sh (farben + logging + sauber)
# - liest requirements.txt zeilenweise
# - ignoriert leerzeilen und kommentare (#...)
# - protokolliert alles nach pip-install.log
# - zeigt farbige statusausgaben + zusammenfassung
# ==============================

LOGFILE="pip-install.log"
REQFILE="requirements.txt"

# -------- Farben / Icons --------
NC="\033[0m"
BOLD="\033[1m"

RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
BLUE="\033[0;34m"
CYAN="\033[0;36m"
GRAY="\033[0;90m"

ICON_OK="✅"
ICON_FAIL="❌"
ICON_WARN="⚠️"
ICON_INFO="ℹ️"
ICON_RUN="▶"
ICON_PKG="📦"
ICON_LOG="🧾"

# -------- Hilfsfunktionen --------
ts() { date +"%Y-%m-%d %H:%M:%S"; }

log() {
  # schreibt nach stdout + logfile (mit timestamp im logfile)
  local msg="$1"
  echo -e "$msg"
  echo -e "[$(ts)] ${msg//\033\[[0-9;]*m/}" >> "$LOGFILE"  # Farben aus Log entfernen
}

hr() {
  log "${GRAY}==============================${NC}"
}

die() {
  log "${RED}${ICON_FAIL} FEHLER:${NC} $1"
  exit 1
}

# -------- Fehlerbehandlung --------
on_error() {
  local exit_code=$?
  log "${RED}${ICON_FAIL} Script abgebrochen (Exit-Code ${exit_code}).${NC}"
  log "${RED}${ICON_LOG} Siehe Log: ${LOGFILE}${NC}"
  exit "$exit_code"
}
trap on_error ERR

# -------- Start --------
rm -f "$LOGFILE"

[[ -f "$REQFILE" ]] || die "requirements.txt nicht gefunden (erwartet: ${REQFILE})."

log "${BOLD}${BLUE}${ICON_RUN} Starte pip-install mit ${REQFILE}${NC}"
log "${GRAY}${ICON_LOG} Logfile: ${LOGFILE}${NC}"

total=0
ok=0
fail=0
skipped=0

# -------- Loop über requirements.txt --------
while IFS= read -r pkg || [ -n "$pkg" ]; do
  # trim whitespace
  pkg="${pkg#"${pkg%%[![:space:]]*}"}"
  pkg="${pkg%"${pkg##*[![:space:]]}"}"

  # skip leer / kommentar
  if [[ -z "$pkg" || "$pkg" == \#* ]]; then
    ((skipped++))
    continue
  fi

  ((total++))
  hr
  log "${CYAN}${ICON_PKG} INSTALLIERE:${NC} ${BOLD}${pkg}${NC}"

  # pip output komplett ins logfile, terminal zeigt es ebenfalls (tee)
  if python -m pip install "$pkg" 2>&1 | tee -a "$LOGFILE"; then
    ((ok++))
    log "${GREEN}${ICON_OK} OK:${NC} ${pkg}"
  else
    ((fail++))
    log "${RED}${ICON_FAIL} FAIL:${NC} ${pkg}"
    log "${RED}${ICON_LOG} Siehe Log: ${LOGFILE}${NC}"
    exit 1
  fi

  log "${GRAY}FERTIG: ${pkg}${NC}"
done < "$REQFILE"

hr
log "${BOLD}${BLUE}${ICON_INFO} Zusammenfassung${NC}"
log "${GREEN}${ICON_OK} Erfolgreich:${NC} ${ok}"
log "${RED}${ICON_FAIL} Fehlgeschlagen:${NC} ${fail}"
log "${YELLOW}${ICON_WARN} Übersprungen (leer/Kommentar):${NC} ${skipped}"
log "${BLUE}${ICON_INFO} Gesamt (Pakete):${NC} ${total}"
log "${GRAY}${ICON_LOG} Logfile: ${LOGFILE}${NC}"

# Optional: Konsistenzcheck (empfohlen)
hr
log "${BLUE}${ICON_RUN} pip check (Dependency-Konsistenz)${NC}"
python -m pip check 2>&1 | tee -a "$LOGFILE" || {
  log "${YELLOW}${ICON_WARN} pip check meldet mögliche Konflikte.${NC}"
  # nicht hart abbrechen, weil manche Umgebungen hier „false positives“ liefern können
}

log "${GREEN}${ICON_OK} Fertig.${NC}"

# ausführen:
#   chmod +x ./pip-install.sh
#   ./pip-install.sh
