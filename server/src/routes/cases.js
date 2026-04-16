const express = require('express');
const multer = require('multer');
const { v4: uuidv4 } = require('uuid');
const caseRepository = require('../repositories/caseRepository');
const imageRepository = require('../repositories/imageRepository');
const { saveImage } = require('../services/storageService');

const router = express.Router();
const upload = multer({ storage: multer.memoryStorage() });

router.get('/cases', (_req, res) => {
  res.json(caseRepository.listCases());
});

router.get('/cases/:id', (req, res) => {
  const item = caseRepository.getCase(req.params.id);
  if (!item) return res.status(404).json({ error: 'case not found' });
  return res.json(item);
});

router.post('/cases', (req, res) => {
  const id = req.body.id || uuidv4();
  const item = caseRepository.saveCase({ ...req.body, id }, id);
  res.status(201).json(item);
});

router.put('/cases/:id', (req, res) => {
  const existing = caseRepository.getCase(req.params.id);
  if (!existing) return res.status(404).json({ error: 'case not found' });
  const item = caseRepository.saveCase({ ...existing, ...req.body, id: req.params.id }, req.params.id);
  return res.json(item);
});

router.delete('/cases/:id', (req, res) => {
  const deleted = caseRepository.deleteCase(req.params.id);
  if (!deleted) return res.status(404).json({ error: 'case not found' });
  return res.status(204).send();
});

router.post('/cases/:id/images', upload.array('images'), (req, res) => {
  if (!caseRepository.getCase(req.params.id)) return res.status(404).json({ error: 'case not found' });
  const files = req.files || [];
  const images = files.map((file, idx) => saveImage(file, req.params.id, idx + 1));
  return res.status(201).json({ images });
});

router.get('/cases/:id/images', (req, res) => {
  res.json(imageRepository.listImagesByCase(req.params.id));
});

module.exports = router;
