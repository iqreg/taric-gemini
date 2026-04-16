const express = require('express');
const fs = require('fs');
const path = require('path');
const multer = require('multer');
const { exportAllData } = require('../services/exportService');
const { importBackup } = require('../services/importService');
const { db, DB_PATH } = require('../db/sqlite');
const { IMAGE_DIR, BACKUP_DIR } = require('../utils/paths');
const imageRepository = require('../repositories/imageRepository');

const router = express.Router();
const upload = multer({ storage: multer.memoryStorage() });

router.post('/admin/export', (_req, res) => {
  const result = exportAllData();
  res.json(result);
});

router.post('/admin/import', upload.none(), (req, res) => {
  const backupPath = req.body.backupPath;
  const mode = req.body.mode || 'merge';
  if (!backupPath) return res.status(400).json({ error: 'backupPath is required' });
  if (!['merge', 'replace'].includes(mode)) return res.status(400).json({ error: 'mode must be merge|replace' });

  const result = importBackup(backupPath, mode);
  return res.json(result);
});

router.get('/admin/storage-status', (_req, res) => {
  const caseCount = db.prepare('SELECT COUNT(*) AS count FROM cases').get().count;
  const imageCount = imageRepository.countImages();
  const filesInUploadDir = fs.existsSync(IMAGE_DIR) ? fs.readdirSync(IMAGE_DIR).length : 0;
  const latestExports = db.prepare('SELECT * FROM exports ORDER BY created_at DESC LIMIT 10').all();

  res.json({
    dbPath: DB_PATH,
    imageDir: IMAGE_DIR,
    backupDir: BACKUP_DIR,
    caseCount,
    imageCount,
    filesInUploadDir,
    latestExports
  });
});

module.exports = router;
