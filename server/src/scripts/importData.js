const { runMigrations } = require('../db/sqlite');
const { ensureDirs } = require('../utils/paths');
const { importBackup } = require('../services/importService');

const backupPath = process.argv[2];
const mode = process.argv[3] || 'merge';

if (!backupPath) {
  console.error('Usage: node src/scripts/importData.js <backupPath> [merge|replace]');
  process.exit(1);
}

ensureDirs();
runMigrations();
const result = importBackup(backupPath, mode);
console.log(JSON.stringify(result, null, 2));
