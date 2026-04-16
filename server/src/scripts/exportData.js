const { runMigrations } = require('../db/sqlite');
const { ensureDirs } = require('../utils/paths');
const { exportAllData } = require('../services/exportService');

ensureDirs();
runMigrations();
const result = exportAllData();
console.log(JSON.stringify(result, null, 2));
