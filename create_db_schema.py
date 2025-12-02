# Datei: create_db_schema.py

import sqlite3
from pathlib import Path

# Basis-Konfiguration aus backend.py übernommen
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "taric_live.db"

# Funktion zur Erstellung der fehlenden Tabelle
def create_taric_reference_table():
    print(f"Versuche, Verbindung zur DB '{DB_PATH.name}' herzustellen...")
    
    # Der conn-Teil ist ähnlich Ihrer get_conn() Funktion
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    print("DB-Verbindung erfolgreich hergestellt.")
    
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS taric_reference (
                taric_code     TEXT PRIMARY KEY NOT NULL,
                cn_code        TEXT,
                hs_chapter     TEXT,
                description_de TEXT,
                description_en TEXT,
                legal_base     TEXT
            )
            """
        )
        conn.commit()
        print("----------------------------------------------------------------------")
        print("✅ SUCCESS: Tabelle 'taric_reference' wurde erfolgreich erstellt/geprüft.")
        print("----------------------------------------------------------------------")

    except Exception as e:
        print(f"❌ CRITICAL ERROR: Fehler beim Erstellen der Tabelle: {e}")
        conn.rollback()

    finally:
        conn.close()
        print("DB-Verbindung geschlossen.")

if __name__ == "__main__":
    create_taric_reference_table()