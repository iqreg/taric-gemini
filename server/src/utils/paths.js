const fs = require('fs');
const path = require('path');

const PERSIST_ROOT = process.env.PERSIST_ROOT || '/project/workspace';
const DATA_DIR = path.join(PERSIST_ROOT, 'data');
const IMAGE_DIR = path.join(DATA_DIR, 'images');
const DB_PATH = path.join(DATA_DIR, 'app.db');
const BACKUP_DIR = path.join(PERSIST_ROOT, 'backups');
const REPO_ROOT = path.resolve(__dirname, '..', '..', '..');

const LEGACY_DB_CANDIDATES = [
  path.join(REPO_ROOT, 'taric_live.db'),
  path.join(REPO_ROOT, 'db', 'taric_dataset.db'),
  '/project/workspace/taric_live.db',
  '/project/workspace/db/taric_dataset.db'
];

const LEGACY_IMAGE_DIR_CANDIDATES = [
  path.join(REPO_ROOT, 'bilder_uploads'),
  '/project/workspace/bilder_uploads'
];

function ensureDirs() {
  [DATA_DIR, IMAGE_DIR, BACKUP_DIR].forEach((dir) => fs.mkdirSync(dir, { recursive: true }));
}

module.exports = {
  PERSIST_ROOT,
  DATA_DIR,
  IMAGE_DIR,
  DB_PATH,
  BACKUP_DIR,
  REPO_ROOT,
  LEGACY_DB_CANDIDATES,
  LEGACY_IMAGE_DIR_CANDIDATES,
  ensureDirs
};
