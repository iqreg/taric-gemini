const { db } = require('../db/sqlite');
const { nowIso } = require('../utils/time');

const upsertStmt = db.prepare(`
  INSERT INTO cases (id, created_at, updated_at, status, description, metadata_json, taric_result_json)
  VALUES (@id, @created_at, @updated_at, @status, @description, @metadata_json, @taric_result_json)
  ON CONFLICT(id) DO UPDATE SET
    updated_at=excluded.updated_at,
    status=excluded.status,
    description=excluded.description,
    metadata_json=excluded.metadata_json,
    taric_result_json=excluded.taric_result_json
`);

function normalizeCase(caseData, explicitId) {
  const now = nowIso();
  return {
    id: explicitId || caseData.id,
    created_at: caseData.created_at || caseData.createdAt || now,
    updated_at: caseData.updated_at || caseData.updatedAt || now,
    status: caseData.status || null,
    description: caseData.description || null,
    metadata_json: JSON.stringify(caseData.metadata || caseData.metadata_json || {}),
    taric_result_json: JSON.stringify(caseData.taricResult || caseData.taric_result_json || {})
  };
}

function saveCase(caseData, explicitId) {
  const payload = normalizeCase(caseData, explicitId);
  if (!payload.id) throw new Error('case id is required');
  upsertStmt.run(payload);
  return getCase(payload.id);
}

function getCase(id) {
  const row = db.prepare('SELECT * FROM cases WHERE id = ?').get(id);
  return row ? hydrateCase(row) : null;
}

function listCases() {
  const rows = db.prepare('SELECT * FROM cases ORDER BY updated_at DESC, id DESC').all();
  return rows.map(hydrateCase);
}

function deleteCase(id) {
  const result = db.prepare('DELETE FROM cases WHERE id = ?').run(id);
  return result.changes > 0;
}

function hydrateCase(row) {
  return {
    id: row.id,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    status: row.status,
    description: row.description,
    metadata: safeJson(row.metadata_json, {}),
    taricResult: safeJson(row.taric_result_json, {})
  };
}

function safeJson(raw, fallback) {
  try {
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

module.exports = { saveCase, getCase, listCases, deleteCase };
