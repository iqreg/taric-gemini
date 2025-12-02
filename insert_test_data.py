# Datei: insert_test_data.py

import sqlite3
from pathlib import Path

# Basis-Konfiguration
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "taric_live.db"

TEST_DATA = [
    (
        "8517120000",
        "85171200",
        "85",
        "Mobiltelefone und andere drahtlose Kommunikationsgeräte (z.B. Smartphones)",
        "Cellular phones and other wireless communication apparatus",
        "ZolltarifDE",
    ),
    (
        "8528721000",
        "85287210",
        "85",
        "Farb-Monitore mit Flachbildschirm für Videoaufzeichnung oder -wiedergabe (TV-Geräte)",
        "Colour monitors with flat screen for video recording or reproduction",
        "ZolltarifDE",
    ),
    (
        "4202125000",
        "42021250",
        "42",
        "Überzüge (Mäntel) für Waren der Position 4202 12 50, mit Außenfläche aus Kunststofffolien, Gewebe aus Spinnstoffen oder Vulkanfiber",
        "Outer covers (jackets) for goods of heading 4202 12 50, with outer surface of plastic sheeting, textile fabrics or vulcanised fibre",
        "ZolltarifDE",
    ),
]

def insert_test_data():
    """Fügt die Testdaten in die taric_reference Tabelle ein."""
    print(f"Versuche, Verbindung zur DB '{DB_PATH.name}' herzustellen...")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        print("DB-Verbindung erfolgreich hergestellt.")
        print(f"Versuche, {len(TEST_DATA)} Datensätze einzufügen/zu ersetzen...")

        for data in TEST_DATA:
            cur.execute(
                """
                INSERT OR REPLACE INTO taric_reference 
                (taric_code, cn_code, hs_chapter, description_de, description_en, legal_base)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                data,
            )
        
        conn.commit()
        print("----------------------------------------------------------------------")
        print(f"✅ SUCCESS: {len(TEST_DATA)} Test-Datensätze erfolgreich eingefügt.")
        print("----------------------------------------------------------------------")

    except Exception as e:
        print(f"❌ CRITICAL ERROR: Fehler beim Einfügen der Daten: {e}")
        conn.rollback()

    finally:
        conn.close()
        print("DB-Verbindung geschlossen.")

if __name__ == "__main__":
    insert_test_data()