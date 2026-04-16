const fs = require('fs');
const path = require('path');
const { v4: uuidv4 } = require('uuid');
const { BACKUP_DIR, DB_PATH } = require('../utils/paths');
const { backupTimestamp, nowIso } = require('../utils/time');
const caseRepository = require('../repositories/caseRepository');
const imageRepository = require('../repositories/imageRepository');
const { db } = require('../db/sqlite');

function exportAllData() {
  const timestamp = backupTimestamp();
  const exportDir = path.join(BACKUP_DIR, timestamp);
  const exportImageDir = path.join(exportDir, 'images');
  fs.mkdirSync(exportImageDir, { recursive: true });

  const cases = caseRepository.listCases();
  const images = imageRepository.listAllImages();
  const imageByCase = new Map();
  images.forEach((img) => {
    if (!imageByCase.has(img.case_id)) imageByCase.set(img.case_id, []);
    imageByCase.get(img.case_id).push(img);
  });

  const payload = {
    sourceVersion: '1.0',
    exportedAt: nowIso(),
    cases: cases.map((item) => ({
      id: item.id,
      createdAt: item.createdAt,
      updatedAt: item.updatedAt,
      status: item.status,
      description: item.description,
      metadata: item.metadata,
      taricResult: item.taricResult,
      imageFiles: (imageByCase.get(item.id) || []).map((img) => img.filename)
    }))
  };

  let copiedImages = 0;
  images.forEach((img) => {
    const source = path.join('/project/workspace', img.relative_path);
    const destination = path.join(exportImageDir, img.filename);
    if (fs.existsSync(source)) {
      fs.copyFileSync(source, destination);
      copiedImages += 1;
    }
  });

  fs.writeFileSync(path.join(exportDir, 'cases.json'), JSON.stringify(payload, null, 2));

  const manifest = {
    sourceVersion: '1.0',
    exportedAt: payload.exportedAt,
    caseCount: payload.cases.length,
    imageCount: copiedImages,
    dbPath: DB_PATH,
    appVersion: process.env.APP_VERSION || 'unknown'
  };
  fs.writeFileSync(path.join(exportDir, 'manifest.json'), JSON.stringify(manifest, null, 2));

  db.prepare('INSERT INTO exports (id, export_path, case_count, image_count, created_at) VALUES (?, ?, ?, ?, ?)')
    .run(uuidv4(), exportDir, payload.cases.length, copiedImages, nowIso());

  return { exportDir, manifest };
}

module.exports = { exportAllData };
