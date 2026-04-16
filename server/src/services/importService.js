const fs = require('fs');
const path = require('path');
const { v4: uuidv4 } = require('uuid');
const caseRepository = require('../repositories/caseRepository');
const imageRepository = require('../repositories/imageRepository');
const { db } = require('../db/sqlite');
const { IMAGE_DIR } = require('../utils/paths');
const { nowIso } = require('../utils/time');

function validateBackup(backupPath) {
  const manifestPath = path.join(backupPath, 'manifest.json');
  const casesPath = path.join(backupPath, 'cases.json');
  if (!fs.existsSync(manifestPath)) throw new Error('manifest.json missing');
  if (!fs.existsSync(casesPath)) throw new Error('cases.json missing');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const casesDoc = JSON.parse(fs.readFileSync(casesPath, 'utf8'));
  if (!Array.isArray(casesDoc.cases)) throw new Error('cases.json has invalid shape');
  return { manifest, casesDoc };
}

function importBackup(backupPath, mode = 'merge') {
  const { manifest, casesDoc } = validateBackup(backupPath);
  const imageSourceDir = path.join(backupPath, 'images');
  const errors = [];

  const tx = db.transaction(() => {
    if (mode === 'replace') {
      db.prepare('DELETE FROM case_images').run();
      db.prepare('DELETE FROM cases').run();
    }

    casesDoc.cases.forEach((item) => {
      caseRepository.saveCase({
        id: item.id,
        createdAt: item.createdAt,
        updatedAt: item.updatedAt,
        status: item.status,
        description: item.description,
        metadata: item.metadata,
        taricResult: item.taricResult
      }, item.id);

      (item.imageFiles || []).forEach((fileName) => {
        const src = path.join(imageSourceDir, fileName);
        const dest = path.join(IMAGE_DIR, fileName);

        if (!fs.existsSync(src)) {
          errors.push(`missing image in backup: ${fileName}`);
          return;
        }

        if (!fs.existsSync(dest)) fs.copyFileSync(src, dest);

        const existing = imageRepository.listImagesByCase(item.id).find((img) => img.filename === fileName);
        if (!existing) {
          imageRepository.saveImage({
            id: uuidv4(),
            case_id: item.id,
            filename: fileName,
            relative_path: path.posix.join('data', 'images', fileName),
            mime_type: null,
            created_at: nowIso()
          });
        }
      });
    });
  });

  tx();

  db.prepare('INSERT INTO imports (id, import_path, mode, case_count, image_count, errors_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)')
    .run(
      uuidv4(),
      backupPath,
      mode,
      casesDoc.cases.length,
      (casesDoc.cases || []).reduce((acc, c) => acc + (c.imageFiles || []).length, 0),
      JSON.stringify(errors),
      nowIso()
    );

  return {
    mode,
    importedCases: casesDoc.cases.length,
    sourceVersion: manifest.sourceVersion,
    errors
  };
}

module.exports = { importBackup, validateBackup };
