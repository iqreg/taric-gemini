const express = require('express');
const { runMigrations } = require('./db/sqlite');
const { ensureDirs } = require('./utils/paths');
const caseRoutes = require('./routes/cases');
const adminRoutes = require('./routes/admin');
const { migrateLegacyData } = require('./services/legacyMigrationService');

ensureDirs();
runMigrations();

const migrationSummary = migrateLegacyData();
console.log('[startup] legacy migration summary:', migrationSummary);

const app = express();
app.use(express.json({ limit: '10mb' }));
app.use('/api', caseRoutes);
app.use('/api', adminRoutes);

app.get('/health', (_req, res) => res.json({ status: 'ok' }));

const port = Number(process.env.PORT || 3001);
app.listen(port, () => {
  console.log(`TARIC storage API listening on ${port}`);
});
