function nowIso() {
  return new Date().toISOString();
}

function backupTimestamp() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

module.exports = { nowIso, backupTimestamp };
