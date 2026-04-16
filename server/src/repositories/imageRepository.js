const { db } = require('../db/sqlite');

const upsertImage = db.prepare(`
  INSERT INTO case_images (id, case_id, filename, relative_path, mime_type, created_at)
  VALUES (@id, @case_id, @filename, @relative_path, @mime_type, @created_at)
  ON CONFLICT(id) DO UPDATE SET
    filename=excluded.filename,
    relative_path=excluded.relative_path,
    mime_type=excluded.mime_type
`);

function saveImage(imageData) {
  upsertImage.run(imageData);
  return getImage(imageData.id);
}

function getImage(id) {
  return db.prepare('SELECT * FROM case_images WHERE id = ?').get(id);
}

function listImagesByCase(caseId) {
  return db.prepare('SELECT * FROM case_images WHERE case_id = ? ORDER BY created_at ASC').all(caseId);
}

function listAllImages() {
  return db.prepare('SELECT * FROM case_images ORDER BY created_at DESC').all();
}

function deleteImagesByCase(caseId) {
  return db.prepare('DELETE FROM case_images WHERE case_id = ?').run(caseId);
}

function countImages() {
  const row = db.prepare('SELECT COUNT(*) AS count FROM case_images').get();
  return row.count;
}

module.exports = { saveImage, getImage, listImagesByCase, listAllImages, deleteImagesByCase, countImages };
