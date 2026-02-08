#!/usr/bin/env bash
LOGFILE=pip-install.log
rm -f "$LOGFILE"

while IFS= read -r pkg || [ -n "$pkg" ]; do
  if [[ -z "$pkg" || "$pkg" == \#* ]]; then
    continue
  fi

  echo "=============================="
  echo "INSTALLIERE: $pkg"
  echo "INSTALLIERE: $pkg" >> "$LOGFILE"

 if python -m pip install "$pkg" 2>&1 | tee -a "$LOGFILE"; then
  echo "OK: $pkg" | tee -a "$LOGFILE"
else
  echo "FAIL: $pkg" | tee -a "$LOGFILE"
  exit 1
fi

  echo "FERTIG: $pkg"
  echo "FERTIG: $pkg" >> "$LOGFILE"
done < requirements.txt

#! ausführen mit -->  ./pip-install.sh