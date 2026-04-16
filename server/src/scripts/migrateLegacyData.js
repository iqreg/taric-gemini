const { runMigrations } = require('../db/sqlite');
const { ensureDirs } = require('../utils/paths');
const { migrateLegacyData } = require('../services/legacyMigrationService');

ensureDirs();
runMigrations();
const result = migrateLegacyData();
console.log(JSON.stringify(result, null, 2));
