import { readFile, writeFile, mkdir, readdir, copyFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { transform, build } from 'esbuild';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
const repo = new URL('../../', import.meta.url);
const out = new URL('../public/fixtures/', import.meta.url);
await mkdir(out, { recursive: true });
await copyFile(new URL('design_system/assets/Logos/aqui-mark.svg', repo), new URL('../public/favicon.svg', import.meta.url));
const source = await readFile(new URL('design_system/components/src/samples.ts', repo), 'utf8');
const compiled = await transform(source, { loader: 'ts', format: 'esm' });
const { CASE_A: A, CASE_B: B, LOG_A } = await import(`data:text/javascript;base64,${Buffer.from(compiled.code).toString('base64')}`);
globalThis.window = { React };
const load = async (path) => {
  const result = await build({ entryPoints: [new URL(path, repo).pathname], bundle: true, write: false, format: 'esm' });
  return import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].text).toString('base64')}`);
};
const { PanoramaStrip, PerspScene } = await load('design_system/components/src/panorama.tsx');
const { urbanScene, ruralScene, perspPoint } = await load('design_system/components/src/scene.ts');
for (const [name, c] of [['urban', A], ['rural', B]]) {
  const html = renderToStaticMarkup(React.createElement(PanoramaStrip, { c, width: 1600, ruler: false, label: false, layers: { mask: false, boxes: false, text: false } }));
  const svg = html.match(/<svg[\s\S]*<\/svg>/)[0].replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" ');
  await writeFile(new URL(`${name}.svg`, out), svg);
}
const penalty = (answered_questions = 0, cues = 0) => ({ answered_questions, cues, conversions: 0, multiplier: Number((0.95 ** answered_questions * 0.8 ** cues).toFixed(10)) });
function builder(c, id) {
  const events = []; const stamp = new Date('2026-10-10T17:00:00Z');
  const emit = (t, type, payload = {}, stage = null, model = null, actor = model ? 'model' : 'agent') => events.push({ run_id: id, panorama: c.file, seq: 0, t, ts: new Date(+stamp + t * 1000).toISOString(), type, stage, actor, model, payload });
  emit(0, 'run.started', { panorama: c.file, special_one: false, category: { value: c.urban, source: c.urbanSource }, versions: { schema: 'panoloc.log/1', fixture: 'Invented design-system illustration' }, fixture_scene: c.scene });
  const evidence = (t, id, kind, payload, stage, model, actor) => emit(t, 'evidence.added', { evidence_id: id, kind, ...payload }, stage, model, actor);
  const stage = (name, start, end, model, extra = {}) => { emit(start, 'stage.started', { optional: ['detect', 'measure', 'spot'].includes(name), deadline_s: name === 'spot' ? 60 : null }, name, model); emit(end, 'stage.finished', { elapsed_s: end - start, over_deadline: false, ...extra }, name, model); };
  const finish = () => events.sort((a, b) => a.t - b.t).map((e, i) => ({ ...e, seq: i + 1 }));
  return { emit, evidence, stage, finish };
}
const angular = ({ yaw, pitch, w, h }) => ({ yaw, pitch, w, h });
const geojson = (poly) => ({ type: 'Polygon', coordinates: [[...poly, poly[0]].map(([lat, lng]) => [lng, lat])] });
const qPayload = (c) => ({ question_id: 'q1', kind: 'zone', text: c.question.text, gain: c.question.gain, break_even: c.question.breakEven, scope: c.question.scope, worded_by: c.question.wordedBy, options: c.question.options.map((o, i) => { const z = c.zones.find(z => z.key === o.key); return { id: 'abcd'[i], label: o.label, reason: o.reason, evidence: o.chips, point: o.point, none: o.none === true, ...(z?.poly ? { zone: geojson(z.poly) } : {}), ...(z?.region ? { region: z.region } : {}) }; }) });
function candidatePayload(c, list, radius) {
  return { candidates: list.map(v => ({ candidate_id: v.id, name: v.name, label: v.name, level: v.level, weight: v.v, role: 'area', source: `fixture:${v.id}`, lat: v.lat, lng: v.lng, accuracy_m: null, extent_m: v.lat !== undefined ? radius : null, lo: v.lo, hi: v.hi, supports: c.evidence.filter(e => e.pol?.[v.id] > 0).map(e => e.id), contradicts: c.evidence.filter(e => e.pol?.[v.id] < 0).map(e => e.id), evidence: c.evidence.filter(e => e.pol?.[v.id]).map(e => e.id), details: { invented: true } })), ruled_out: c.ruledOut };
}
function output(c, id, lat, lng, radius, method, pen, note) {
  return { output_id: id, coordinates: Array.from({ length: 10 }, (_, i) => ({ rank: i + 1, lat, lng })), output_method: method, source_role: method === 'reference_camera' ? 'camera' : 'area', position_uncertainty_m: radius, uncertainty_source: method === 'reference_camera' ? 'estimated_offset' : 'source_estimate', category: { value: c.urban, source: c.urbanSource }, special_one: false, sources: ['fixture:invented'], penalty: pen, note };
}
const a = builder(A, 'fixture-a');
a.stage('views', 0.1, 1.9, 'py360convert', { views: 8, photographer_masked: 0.18 });
a.stage('detect', 27.3, 33.5, 'YOLOE-26-L · SAM 3', { kept: 17, rejected: 3 });
A.detections.forEach((d, i) => { a.evidence(27.3 + i * 0.04, d.id, 'object', { label: d.label, score: d.score, box: angular(d), kept: true }, 'detect', 'YOLOE-26-L'); if (!d.kept) a.evidence(33.5, d.id, 'object', { label: d.label, score: d.score, sam_score: d.sam, box: angular(d), kept: false }, 'detect', 'SAM 3'); });
a.stage('read', 35.9, 43.0, 'PP-OCRv6-medium');
A.texts.forEach((t, i) => { const ds = A.evidence.find(e => e.ref === t.id); a.evidence(ds?.t ?? 41.9, ds?.id ?? `text-${i}`, t.kind ?? 'text', { text: t.text, confidence: t.conf, box: angular(t), country: t.country, inference: ds?.inference, polarity: ds?.pol }, 'read', 'PP-OCRv6-medium'); });
a.evidence(43.0, 'e4', 'language', { votes: A.language, polarity: A.evidence.find(e => e.id === 'e4').pol }, 'read', 'Language-ID ×3');
a.stage('describe', 44, 66.8, 'qwen3.5:9b');
A.checklist.forEach((item, i) => { const ds = A.evidence.find(e => e.kind === 'checklist' && e.obs.startsWith(item.item)); a.evidence(66 + i * 0.16, ds?.id ?? `check-${i}`, 'checklist', { ...item, answered: i + 1, total: A.checklist.length, inference: ds?.inference, polarity: ds?.pol }, 'describe', 'qwen3.5:9b'); });
a.stage('measure', 68, 73.1, 'EoMT-L · pvlib');
a.evidence(72, 'e10', 'scene_shares', { shares: A.shares, masked: 0.18, mask_url: '/fixtures/urban-mask.svg', polarity: A.evidence.find(e => e.id === 'e10').pol }, 'measure', 'EoMT-L');
a.evidence(73.1, 'e11', 'sun', { azimuth: A.sun.azimuth, elevation: A.sun.elevation, yaw: A.sun.yaw, bearing_of_yaw0: A.sun.bearingOfYaw0, err_deg: A.sun.err, polarity: A.evidence.find(e => e.id === 'e11').pol }, 'measure', 'pvlib');
a.stage('geo', 74, 83.8, 'PE-Core · mini-PIGEON');
A.neighbours.forEach((n, i) => a.evidence(82 + i * 0.08, `neighbour-${i}`, 'neighbour', { photo_url: `/fixtures/ref-${i === 0 ? '1' : '2'}.svg`, place: n.place, lat: n.lat, lng: n.lng, similarity: n.sim, source: `osv5m:invented-${n.id}`, group: 'pe-core', group_cap: 0.35, candidate_ids: i === 2 ? ['gaia'] : i === 4 ? ['alfama'] : ['ribeira', 'miragaia'] }, 'geo', 'PE-Core'));
a.evidence(83.4, 'e13', 'region', { regions: A.regions, cells: A.heatTown.map(b => ({ lat: b.lat, lng: b.lng, size_m: b.s * 111320, v: b.w })), group: 'pe-core', group_cap: 0.35, polarity: A.evidence.find(e => e.id === 'e13').pol }, 'geo', 'mini-PIGEON');
a.evidence(83.5, 'geo-points', 'geo_sample', { points: A.neighbours.map(n => ({ lat: n.lat, lng: n.lng })) }, 'geo', 'GeoCLIP');
a.stage('names', 84.4, 85, 'OSM · Wikidata · GeoNames index');
a.evidence(85, 'e14', 'name_match', { query: '4050', matches: [{ label: 'Postcode area 4050', lat: 41.1432, lng: -8.615, role: 'area', source: 'geonames:invented' }], polarity: { ribeira: 1 } }, 'names', null, 'agent');
a.evidence(86.1, 'e15', 'contradiction', { between: ['e2', 'e6'], note: A.evidence.find(e => e.id === 'e15').inference, polarity: { alfama: -1 } }, 'fuse', null, 'agent');
a.emit(86.3, 'candidates.updated', candidatePayload(A, A.candidatesBefore, 180), 'fuse');
a.emit(86.4, 'output.produced', output(A, 'o1', 41.14070, -8.61310, 180, 'coarse_candidate', penalty(), 'Initial answer, before the question.'), 'output');
a.emit(88, 'question.asked', qPayload(A), 'ask');
a.emit(212, 'question.answered', { question_id: 'q1', option_id: 'a', label: A.question.options[0].label, penalty: penalty(1) }, 'ask', null, 'team');
a.emit(212.6, 'candidates.updated', candidatePayload(A, A.candidatesAfter, 180), 'fuse');
a.emit(309, 'stage.started', { optional: true, deadline_s: 60 }, 'spot', 'MegaLoc');
const sc = urbanScene(), half = 500, height = 320;
const qCam = { pos: [0, 0, 1.7], yaw: 42, fov: 74, w: half, h: height };
const rCams = [{ pos: [-13, -7, 1.6], yaw: 52, fov: 62, w: half, h: height }, { pos: [16, -6, 1.6], yaw: 18, fov: 66, w: half, h: height }, { pos: [-30, -24, 1.6], yaw: 50, fov: 50, w: half, h: height }];
for (const [i, r] of A.spot.refs.entries()) {
  const pairs = sc.keypoints.flatMap(k => { const q = perspPoint(k, qCam), ref = perspPoint(k, rCams[i]); return q && ref && [...q, ...ref].every(Number.isFinite) && q[0] >= 0 && q[0] <= half && ref[0] >= 0 && ref[0] <= half && q[1] >= 0 && q[1] <= height && ref[1] >= 0 && ref[1] <= height ? [{ query: [q[0] / half, q[1] / height], reference: [ref[0] / half, ref[1] / height], inlier: r.accepted }] : []; }).slice(0, 40);
  a.evidence(331.5 + i * 0.04, `match-${r.id}`, 'match', { reference: { id: r.id, photo_url: `/fixtures/ref-${i + 1}.svg`, lat: r.lat, lng: r.lng, source: `osv5m:invented-${r.id}` }, matches: r.matches, inliers: r.inliers, threshold: 50, accepted: r.accepted, reason: r.reason ?? 'Geometry consistent', query_yaw: 42, query_fov: 74, distance_m: r.dist, keypoints: pairs, candidate_ids: ['ribeira'], polarity: { ribeira: r.accepted ? 1 : -1 } }, 'spot', 'ALIKED + LightGlue');
  await writeFile(new URL(`ref-${i + 1}.svg`, out), `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${half} ${height}">${renderToStaticMarkup(React.createElement(PerspScene, { sc, cam: rCams[i] }))}</svg>`);
}
a.emit(339, 'stage.finished', { elapsed_s: 30, over_deadline: false }, 'spot', 'ALIKED + LightGlue');
a.emit(340, 'output.produced', output(A, 'o2', A.answer.lat, A.answer.lng, 22, 'reference_camera', penalty(1), 'Verified camera reference, with source GPS plus viewpoint offset.'), 'output');
a.emit(340, 'run.finished', { duration_s: 340, final_output: 'o2', questions: { answered: 1, skipped: 0, open: 0 }, penalty: penalty(1) });
await writeFile(new URL('case-a.events.jsonl', out), a.finish().map(e => JSON.stringify(e)).join('\n') + '\n');
const b = builder(B, 'fixture-b');
b.stage('views', 0.1, 1.9, 'py360convert', { views: 8, photographer_masked: 0.18 });
b.emit(27.3, 'stage.skipped', { reason: 'Optional detector omitted for this non-urban scene.' }, 'detect');
b.stage('read', 35.9, 40.8, 'PP-OCRv6-medium', { note: 'No text found' });
b.evidence(40.8, 'b0', 'text', { text: '', observation: 'No text found' }, 'read', 'PP-OCRv6-medium');
b.stage('describe', 43, 66.8, 'qwen3.5:9b');
B.checklist.forEach((item, i) => b.evidence(66 + i * 0.1, `b${i + 1}`, 'checklist', { ...item, polarity: { evora: 1, beja: 1, portalegre: 1, extremadura: 1 } }, 'describe', 'qwen3.5:9b'));
b.stage('measure', 68, 73.1, 'EoMT-L · pvlib');
b.evidence(72, 'b-shares', 'scene_shares', { shares: B.shares, masked: 0.18 }, 'measure', 'EoMT-L');
b.evidence(73.1, 'b-sun', 'sun', { azimuth: B.sun.azimuth, elevation: B.sun.elevation, yaw: B.sun.yaw, bearing_of_yaw0: B.sun.bearingOfYaw0, err_deg: B.sun.err }, 'measure', 'pvlib');
b.stage('geo', 74, 83.4, 'PE-Core · mini-PIGEON');
b.evidence(83.4, 'b-regions', 'region', { regions: B.regions, cells: B.heat.map(v => ({ lat: v.lat, lng: v.lng, size_m: v.s * 111320, v: v.w })), group: 'pe-core' }, 'geo', 'mini-PIGEON');
b.emit(85, 'stage.skipped', { reason: 'No name was read or proposed.' }, 'names');
b.emit(86.3, 'candidates.updated', candidatePayload(B, B.candidates, 5000), 'fuse');
b.emit(88, 'question.asked', qPayload(B), 'ask');
b.emit(188, 'question.skipped', { question_id: 'q1' }, 'ask', null, 'team');
b.emit(309, 'stage.skipped', { reason: 'No camera reference available for this scene.' }, 'spot');
b.emit(340, 'output.produced', output(B, 'o1', B.answer.lat, B.answer.lng, B.answer.r, 'coarse_candidate', penalty(), B.answer.why), 'output');
b.emit(340, 'run.finished', { duration_s: 340, final_output: 'o1', questions: { answered: 0, skipped: 1, open: 0 }, penalty: penalty() });
await writeFile(new URL('case-b.events.jsonl', out), b.finish().map(e => JSON.stringify(e)).join('\n') + '\n');
// Use the actual runlog fixture, not a re-created facsimile.
let samples = [];
try { samples = await readdir(new URL('runs/sample/', repo)); } catch { /* generate below */ }
if (!samples.length) {
  const result = spawnSync('python3', [new URL('tools/sample_log.py', repo).pathname], { cwd: repo.pathname, encoding: 'utf8' });
  if (result.status !== 0) throw new Error(result.stderr);
  samples = await readdir(new URL('runs/sample/', repo));
}
const sample = await readFile(new URL(`runs/sample/${samples.sort().at(-1)}/events.jsonl`, repo), 'utf8');
await writeFile(new URL('sample.events.jsonl', out), sample);
const tokens = JSON.parse(await readFile(new URL('design_system/tokens.json', repo), 'utf8'));
const segMarkup = renderToStaticMarkup(React.createElement(PanoramaStrip, { c: A, width: 1600, ruler: false, label: false, layers: { seg: true, mask: false, boxes: false, text: false } }));
const segmentation = segMarkup.match(/<g class="aq-seg-layer">[\s\S]*?<\/g>/)[0].replace(/var\(--(seg-[a-z]+)\)/g, (_, name) => tokens.color.tokens.find(t => t.name === name).value.dark);
await writeFile(new URL('urban-mask.svg', out), `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 800"><clipPath id="visible-scene"><rect width="1600" height="656"/></clipPath><g clip-path="url(#visible-scene)">${segmentation}</g></svg>`);
console.log(`Built invented Cases A/B (LOG_A timing: ${LOG_A.length} beats), procedural images, and the real sample log.`);
