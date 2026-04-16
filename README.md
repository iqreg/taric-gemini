# taric-gemini (CodeSandbox + persistente TARIC-Datenhaltung)

Dieses Repo enthält weiterhin den bestehenden Python/FastAPI-Flow und zusätzlich ein neues Node/Express-Storage-Backend mit robuster Persistenz unter `/project/workspace`.

## Kurze Ist-Analyse (Bestand vor der Änderung)

- **Falldaten** lagen bereits in SQLite (`taric_live.db`) in der Tabelle `taric_live` (inkl. Klassifikationsergebnis als JSON-Text). 
- **Bilder** wurden im Dateisystem unter `bilder_uploads/` abgelegt und über Dateiname in `taric_live.filename` referenziert.
- **Frontend-/Browser-State**: In HTML-UIs wurden nur einzelne UI-Flags lokal per `localStorage` gehalten (z. B. Backend-Modus), nicht der Primärdatenbestand.
- **Risiken**:
  - Kein separates, versioniertes Export-/Import-Format für vollständige Restore-Prozesse.
  - Keine klare Trennung in Repository/Service/Routing für Cases/Bilder.
  - Fehlende robuste Merge/Replace-Importstrecke inkl. Manifest-Validierung.
- **Migrationsansatz**: Legacy-Daten aus `taric_live.db` + `bilder_uploads/` werden beim Start oder per Script in neue `cases`/`case_images`-Struktur überführt.

## Neue Zielarchitektur (Node/Express + SQLite)

```txt
/project/workspace
  /server
    /src
      /db
      /repositories
      /services
      /routes
      /utils
  /data
    app.db
    /images
  /backups
    /<timestamp>
      cases.json
      /images
      manifest.json
```

Implementiert unter `server/src/...`.

## Datenmodell (SQLite)

### `cases`
- `id TEXT PRIMARY KEY`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- `status TEXT`
- `description TEXT`
- `metadata_json TEXT`
- `taric_result_json TEXT`

### `case_images`
- `id TEXT PRIMARY KEY`
- `case_id TEXT NOT NULL`
- `filename TEXT NOT NULL`
- `relative_path TEXT NOT NULL`
- `mime_type TEXT`
- `created_at TEXT NOT NULL`
- FK auf `cases(id)`

Zusätzlich:
- `exports`
- `imports`

## API-Endpunkte

### Cases
- `GET    /api/cases`
- `GET    /api/cases/:id`
- `POST   /api/cases`
- `PUT    /api/cases/:id`
- `DELETE /api/cases/:id`

### Images
- `POST   /api/cases/:id/images`
- `GET    /api/cases/:id/images`

### Admin
- `POST   /api/admin/export`
- `POST   /api/admin/import` (`backupPath`, `mode=merge|replace`)
- `GET    /api/admin/storage-status`

## Export

Export erzeugt:
- `/project/workspace/backups/<timestamp>/cases.json`
- `/project/workspace/backups/<timestamp>/images/*`
- `/project/workspace/backups/<timestamp>/manifest.json`

`manifest.json` enthält u. a.:
- `sourceVersion`
- `exportedAt`
- `caseCount`
- `imageCount`
- `dbPath`
- `appVersion`

## Import / Restore

Import-Modi:
- `merge`: ergänzt/aktualisiert Fälle, Bestand bleibt erhalten.
- `replace`: leert bestehende Cases/Bildreferenzen und spielt Backup neu ein.

Validiert `manifest.json` und `cases.json`, protokolliert fehlende Bilddateien im Ergebnis/Import-Log.

## Migration vorhandener Sandbox-Daten

- Quelle 1 (bevorzugt): `taric_live.db` (Tabelle `taric_live`)
- Quelle 2: `bilder_uploads/`
- Ziel: `/project/workspace/data/app.db` + `/project/workspace/data/images`

Legacy-Migration läuft automatisch beim Start des Node-Servers und kann manuell ausgeführt werden.

## Betrieb (Node-Storage-Service)

```bash
cd server
npm install
npm run start
```

### CLI-Skripte

```bash
npm run export:data
npm run import:data -- /project/workspace/backups/<timestamp> merge
npm run import:data -- /project/workspace/backups/<timestamp> replace
npm run migrate:legacy
```

## Bekannte Grenzen

- Kein Frontend-Admin-Screen eingebaut (stattdessen robuste API + CLI).
- Legacy-Migration mappt alte `taric_live`-Zeilen auf `cases` mit IDs `legacy_<id>`.
- MIME-Typ bei Legacy-Bildern ggf. `null` (wenn aus altem Dateinamen nicht bestimmbar).

## Nächster Schritt Richtung externer Persistenz

- Repository-Schicht auf SQL-Adapter abstrahieren (PostgreSQL-kompatibel).
- Storage-Service auf pluggable Backend erweitern (lokales FS ↔ S3-kompatibel).
