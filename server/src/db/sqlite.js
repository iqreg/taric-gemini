const fs = require('fs');
const Database = require('better-sqlite3');
const { DB_PATH, ensureDirs } = require('../utils/paths');

ensureDirs();
fs.mkdirSync(require('path').dirname(DB_PATH), { recursive: true });

const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

function runMigrations() {
  db.exec(`
    CREATE TABLE IF NOT EXISTS cases (
      id TEXT PRIMARY KEY,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      status TEXT,
      description TEXT,
      metadata_json TEXT,
      taric_result_json TEXT
    );

    CREATE TABLE IF NOT EXISTS case_images (
      id TEXT PRIMARY KEY,
      case_id TEXT NOT NULL,
      filename TEXT NOT NULL,
      relative_path TEXT NOT NULL,
      mime_type TEXT,
      created_at TEXT NOT NULL,
      FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS exports (
      id TEXT PRIMARY KEY,
      export_path TEXT NOT NULL,
      case_count INTEGER NOT NULL,
      image_count INTEGER NOT NULL,
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS imports (
      id TEXT PRIMARY KEY,
      import_path TEXT NOT NULL,
      mode TEXT NOT NULL,
      case_count INTEGER NOT NULL,
      image_count INTEGER NOT NULL,
      errors_json TEXT,
      created_at TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_case_images_case_id ON case_images(case_id);
    CREATE INDEX IF NOT EXISTS idx_case_images_relative_path ON case_images(relative_path);
  `);
}

module.exports = { db, runMigrations, DB_PATH };
