const fs = require('fs');
const path = require('path');
const { v4: uuidv4 } = require('uuid');
const { IMAGE_DIR } = require('../utils/paths');
const { nowIso } = require('../utils/time');
const imageRepository = require('../repositories/imageRepository');

function sanitizeExt(fileName = '') {
  const ext = path.extname(fileName).toLowerCase();
  return ext && ext.length <= 8 ? ext : '.bin';
}

function buildFilename(caseId, index, originalName) {
  return `${caseId}-${Date.now()}-${index}${sanitizeExt(originalName)}`;
}

function saveImage(file, caseId, index = 1) {
  if (!file || !file.buffer) throw new Error('missing file buffer');

  const filename = buildFilename(caseId, index, file.originalname || 'upload.bin');
  const absolutePath = path.join(IMAGE_DIR, filename);
  fs.writeFileSync(absolutePath, file.buffer);

  const relativePath = path.posix.join('data', 'images', filename);
  const image = imageRepository.saveImage({
    id: uuidv4(),
    case_id: caseId,
    filename,
    relative_path: relativePath,
    mime_type: file.mimetype || null,
    created_at: nowIso()
  });

  return image;
}

function resolveImageAbsolutePath(relativePath) {
  const normalized = relativePath.replace(/^\/+/, '');
  return path.join('/project/workspace', normalized);
}

module.exports = { saveImage, resolveImageAbsolutePath };
