const fs = require('fs');
const path = require('path');
const Database = require('better-sqlite3');
const { v4: uuidv4 } = require('uuid');
const caseRepository = require('../repositories/caseRepository');
const imageRepository = require('../repositories/imageRepository');
const { LEGACY_DB_CANDIDATES, LEGACY_IMAGE_DIR_CANDIDATES } = require('../utils/paths');

function firstExisting(candidates) {
  return candidates.find((entry) => fs.existsSync(entry));
}

function migrateLegacyData() {
  const legacyDbPath = firstExisting(LEGACY_DB_CANDIDATES);
  const legacyImageDir = firstExisting(LEGACY_IMAGE_DIR_CANDIDATES);

  if (!legacyDbPath) {
    return { migrated: false, reason: 'no legacy sqlite DB found', sources: { legacyDbPath: null, legacyImageDir } };
  }

  const sourceDb = new Database(legacyDbPath, { readonly: true });
  const hasTaricLive = sourceDb.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='taric_live'").get();
  if (!hasTaricLive) {
    return { migrated: false, reason: 'legacy db has no taric_live table', sources: { legacyDbPath, legacyImageDir } };
  }

  const rows = sourceDb.prepare('SELECT id, created_at, filename, taric_code, cn_code, hs_chapter, confidence, short_reason, raw_response_json FROM taric_live').all();

  let migratedCases = 0;
  let migratedImages = 0;

  rows.forEach((row) => {
    const caseId = `legacy_${row.id}`;
    caseRepository.saveCase({
      id: caseId,
      createdAt: row.created_at,
      updatedAt: row.created_at,
      status: 'migrated',
      description: row.short_reason,
      metadata: { legacyTable: 'taric_live', legacyId: row.id },
      taricResult: {
        taric_code: row.taric_code,
        cn_code: row.cn_code,
        hs_chapter: row.hs_chapter,
        confidence: row.confidence,
        raw_response: safeJson(row.raw_response_json, {})
      }
    }, caseId);
    migratedCases += 1;

    if (row.filename && legacyImageDir) {
      const sourceImagePath = path.join(legacyImageDir, row.filename);
      if (fs.existsSync(sourceImagePath)) {
        const newName = `${caseId}-${Date.now()}-1${path.extname(row.filename) || '.bin'}`;
        const destination = path.join('/project/workspace/data/images', newName);
        fs.copyFileSync(sourceImagePath, destination);
        imageRepository.saveImage({
          id: uuidv4(),
          case_id: caseId,
          filename: newName,
          relative_path: path.posix.join('data', 'images', newName),
          mime_type: null,
          created_at: row.created_at || new Date().toISOString()
        });
        migratedImages += 1;
      }
    }
  });

  sourceDb.close();

  return {
    migrated: true,
    migratedCases,
    migratedImages,
    sources: { legacyDbPath, legacyImageDir }
  };
}

function safeJson(raw, fallback) {
  try {
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

module.exports = { migrateLegacyData };
