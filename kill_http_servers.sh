#!/bin/bash

echo "Suche nach laufenden Python-HTTP-Servern..."

# Finde alle python-Prozesse, die http.server oder port 8080/8000 verwenden
PIDS=$(ps aux | grep "[p]ython" | grep "http.server" | awk '{print $2}')

# Falls nichts gefunden wird:
if [ -z "$PIDS" ]; then
    echo "Keine laufenden Python-HTTP-Server gefunden."
    exit 0
fi

echo "Gefundene Server-Prozess(e): $PIDS"

# Prozesse stoppen
for PID in $PIDS; do
    echo "Beende Prozess PID $PID ..."
    kill "$PID" 2>/dev/null

    # Falls Prozess hartnäckig ist:
    sleep 1
    if ps -p "$PID" > /dev/null; then
        echo "Prozess $PID läuft noch – sende KILL..."
        kill -9 "$PID" 2>/dev/null
    fi
done

echo "Alle Python-HTTP-Server wurden beendet."
