// Sample content for mockups (invented; brief §"Sample content"). Everything a screen shows derives from these objects,
// the way the real app derives everything from the event log.

export const ROSTER = [
  { id: 'yoloe', name: 'YOLOE-26-L', role: 'Open-vocabulary detector', stage: 'detect', gb: 1.9, state: 'idle' },
  { id: 'sam3', name: 'SAM 3', role: 'Checks each detection box', stage: 'detect', gb: 1.2, state: 'idle' },
  { id: 'ocr', name: 'PP-OCRv6-medium', role: 'Reads text (CPU)', stage: 'read', gb: 0, cpu: true, state: 'idle' },
  { id: 'lid', name: 'Language-ID ×3', role: 'Votes pt / gl / es / ca / eu / fr (CPU)', stage: 'read', gb: 0, cpu: true, state: 'idle' },
  { id: 'qwen', name: 'Qwen3.5-9B', role: 'Vision-language: checklist, landmark guesses, question wording', stage: 'describe', gb: 7.4, state: 'resident' },
  { id: 'gemma', name: 'Gemma 4 12B', role: 'Fallback vision-language model', stage: 'describe', gb: 0, state: 'standby' },
  { id: 'eomt', name: 'EoMT-L', role: 'Segmentation: sky, trees, buildings, water', stage: 'measure', gb: 1.1, state: 'idle' },
  { id: 'pvlib', name: 'pvlib', role: 'Sun position to compass heading (code)', stage: 'measure', gb: 0, cpu: true, state: 'idle' },
  { id: 'pecore', name: 'PE-Core', role: 'Image embeddings for retrieval and regions', stage: 'geo', gb: 0.9, state: 'resident' },
  { id: 'pigeon', name: 'mini-PIGEON', role: 'Our region classifier (on PE-Core)', stage: 'geo', gb: 0.2, state: 'resident' },
  { id: 'geoclip', name: 'GeoCLIP', role: 'Extra location generator', stage: 'geo', gb: 0.6, state: 'idle' },
  { id: 'megaloc', name: 'MegaLoc', role: 'Place retrieval near candidates', stage: 'spot', gb: 0.5, state: 'resident' },
  { id: 'lightglue', name: 'ALIKED + LightGlue', role: 'Keypoint matching', stage: 'spot', gb: 0.4, state: 'running' },
];

const CASE_A_STAGES = [
  { id: 'intake', name: 'Intake', models: ['Filename parser'], status: 'done', dur: 0.1, gb: 0 },
  { id: 'views', name: 'Views', models: ['py360convert'], status: 'done', dur: 1.8, gb: 0 },
  { id: 'detect', name: 'Detect', optional: true, models: ['YOLOE-26-L', 'SAM 3'], status: 'done', dur: 6.2, gb: 3.1 },
  { id: 'read', name: 'Read', models: ['PP-OCRv6-medium', 'Language-ID ×3'], status: 'done', dur: 4.9, gb: 0, cpu: true },
  { id: 'describe', name: 'Describe', models: ['Qwen3.5-9B'], status: 'done', dur: 22.4, gb: 7.4 },
  { id: 'measure', name: 'Measure', optional: true, models: ['EoMT-L', 'pvlib'], status: 'done', dur: 5.1, gb: 1.1 },
  { id: 'geo', name: 'Pixel geolocation', models: ['PE-Core', 'mini-PIGEON', 'GeoCLIP'], status: 'done', dur: 9.8, gb: 1.7 },
  { id: 'names', name: 'Name lookup', models: ['OSM · Wikidata · GeoNames index'], status: 'done', dur: 0.6, gb: 0 },
  { id: 'fusion', name: 'Fusion', models: ['Solver (code)'], status: 'done', dur: 0.2, gb: 0, solver: true },
  { id: 'ask', name: 'Ask', models: ['Solver (code)', 'Qwen3.5-9B'], status: 'done', dur: 1.4, gb: 0, note: 'Answered A · ×0.95' },
  { id: 'spot', name: 'Exact spot', optional: true, models: ['MegaLoc', 'ALIKED + LightGlue'], status: 'running', dur: 31.0, deadline: 60, gb: 2.6 },
  { id: 'answer', name: 'Answer', models: ['Solver (code)'], status: 'queued', dur: null, gb: 0, solver: true },
];

export const CASE_A: any = {
  id: 'A', label: 'Case 3', file: 'IMG_20260115_143012_00_204.jpg', date: '2026-01-15', time: '14:30:12', shot: 204,
  urban: 'urban', urbanSource: 'official', special: false, size: [6080, 3040],
  run: { used: 340, budget: 480, session: 1395, sessionBudget: 3600, gpu: 12.6, gpuMax: 16, multiplier: 0.95, expected: 12500, expectedRange: [10900, 13400] },
  multiplierHistory: [{ t: 0, m: 1.0, what: 'Run started' }, { t: 212, m: 0.95, what: 'Answered question 1 (A) · ×0.95' }],
  stages: CASE_A_STAGES,
  scene: 'urban', yawToBearing: 64, yawToBearingErr: 12,
  detections: [
    { id: 'd1', label: 'shop sign', score: 0.88, yaw: 38, pitch: 6, w: 9, h: 3.2, kept: true },
    { id: 'd2', label: 'shop sign', score: 0.81, yaw: 212.5, pitch: -3.1, w: 6, h: 2.6, kept: true },
    { id: 'd3', label: 'balcony', score: 0.77, yaw: 300, pitch: 14, w: 7, h: 5, kept: true },
    { id: 'd4', label: 'azulejo panel', score: 0.74, yaw: 330, pitch: 8, w: 10, h: 12, kept: true },
    { id: 'd5', label: 'bollard', score: 0.69, yaw: 252, pitch: -14, w: 2, h: 5, kept: true },
    { id: 'd6', label: 'street lamp', score: 0.66, yaw: 96, pitch: 10, w: 2, h: 12, kept: true },
    { id: 'd7', label: 'licence plate', score: 0.31, sam: 0.02, yaw: 268, pitch: -12, w: 3, h: 1.4, kept: false },
    { id: 'd8', label: 'church', score: 0.28, sam: 0.04, yaw: 150, pitch: 4, w: 6, h: 8, kept: false },
    { id: 'd9', label: 'granary', score: 0.22, sam: 0.01, yaw: 70, pitch: -2, w: 5, h: 3, kept: false },
  ],
  detectSummary: { kept: 17, rejected: 3 },
  texts: [
    { id: 't1', text: 'CAFÉ', conf: 0.97, yaw: 38, pitch: 6.5, w: 7, h: 2.6 },
    { id: 't2', text: '4050-253', conf: 0.94, yaw: 212.5, pitch: -3.1, w: 4.2, h: 1.6, kind: 'postcode', country: 'PT' },
    { id: 't3', text: '22• ••• •••', conf: 0.71, yaw: 289, pitch: 2, w: 5, h: 1.4, kind: 'phone', country: 'PT' },
  ],
  language: [{ id: 'pt', v: 0.93 }, { id: 'gl', v: 0.04 }, { id: 'es', v: 0.02 }, { id: 'ca', v: 0.0 }, { id: 'eu', v: 0.0 }, { id: 'fr', v: 0.01 }],
  checklist: [
    { item: 'Granite masonry', answer: 'yes' }, { item: 'Blue-and-white azulejo façade', answer: 'yes' }, { item: 'Wrought-iron balconies', answer: 'yes' },
    { item: 'River visible', answer: 'yes' }, { item: 'Calçada portuguesa pavement', answer: 'not_visible' }, { item: 'Vegetation', answer: 'not_visible' },
  ],
  shares: [{ id: 'sky', v: 0.31 }, { id: 'building', v: 0.44 }, { id: 'road', v: 0.17 }, { id: 'water', v: 0.05 }, { id: 'tree', v: 0.03 }],
  sun: { azimuth: 205, elevation: 22, yaw: 141, bearingOfYaw0: 64, err: 12 },
  water: { bearing: 200 },
  regions: [{ name: 'Porto', v: 0.47, lo: 0.36, hi: 0.58 }, { name: 'Braga', v: 0.12, lo: 0.06, hi: 0.19 }, { name: 'Lisboa', v: 0.11, lo: 0.05, hi: 0.18 }, { name: 'Viana do Castelo', v: 0.06 }, { name: 'Galicia (ES)', v: 0.05 }, { name: 'Other', v: 0.19, other: true }],
  neighbours: [
    { id: 'n1', place: 'Porto · Cais da Ribeira', lat: 41.1405, lng: -8.6122, sim: 0.83 },
    { id: 'n2', place: 'Porto · Miragaia', lat: 41.1432, lng: -8.6203, sim: 0.79 },
    { id: 'n3', place: 'Vila Nova de Gaia · Cais', lat: 41.1372, lng: -8.6125, sim: 0.77 },
    { id: 'n4', place: 'Porto · Ribeira', lat: 41.1411, lng: -8.6141, sim: 0.74 },
    { id: 'n5', place: 'Lisboa · Alfama', lat: 38.7114, lng: -9.1300, sim: 0.61 },
  ],
  // candidates after first fusion (before question)
  candidatesBefore: [
    { id: 'ribeira', rank: 1, name: 'Porto · Ribeira', level: 'spot', v: 0.52, lo: 0.41, hi: 0.63, delta: 0.09, sup: 9, con: 0, lat: 41.1407, lng: -8.6131 },
    { id: 'gaia', rank: 2, name: 'Vila Nova de Gaia · riverside', level: 'town', v: 0.21, lo: 0.13, hi: 0.30, delta: -0.02, sup: 6, con: 1, lat: 41.1372, lng: -8.6118 },
    { id: 'miragaia', rank: 3, name: 'Porto · Miragaia', level: 'spot', v: 0.12, lo: 0.07, hi: 0.19, delta: 0.03, sup: 7, con: 1, lat: 41.1432, lng: -8.6203 },
    { id: 'alfama', rank: 4, name: 'Lisboa · Alfama', level: 'spot', v: 0.05, lo: 0.02, hi: 0.09, delta: -0.06, sup: 2, con: 3, lat: 38.7114, lng: -9.1300, contradictedBy: 'postcode 4050-253' },
    { id: 'other', rank: 5, name: 'Other', level: 'area', v: 0.10, lo: 0.05, hi: 0.17, other: true },
  ],
  candidatesAfter: [
    { id: 'ribeira', rank: 1, name: 'Porto · Ribeira', level: 'spot', v: 0.69, lo: 0.58, hi: 0.78, delta: 0.17, sup: 10, con: 0, lat: 41.1407, lng: -8.6131 },
    { id: 'miragaia', rank: 2, name: 'Porto · Miragaia', level: 'spot', v: 0.21, lo: 0.13, hi: 0.29, delta: 0.09, sup: 8, con: 1, lat: 41.1432, lng: -8.6203 },
    { id: 'gaia', rank: 3, name: 'Vila Nova de Gaia · riverside', level: 'town', v: 0.03, lo: 0.01, hi: 0.07, delta: -0.18, sup: 6, con: 2, lat: 41.1372, lng: -8.6118, keptNote: 'kept in case the answer was wrong' },
    { id: 'other', rank: 4, name: 'Other', level: 'area', v: 0.07, lo: 0.03, hi: 0.12, other: true },
  ],
  ruledOut: [{ name: 'Galicia (ES)', level: 'region', reason: 'Portuguese postcode format and Portuguese spelling', by: ['e2', 'e4'] }],
  funnel: [
    { level: 'Country', name: 'Portugal', v: 0.95 }, { level: 'Region', name: 'Norte · Porto district', v: 0.86 },
    { level: 'Town', name: 'Porto', v: 0.81 }, { level: 'Spot', name: 'Ribeira', v: 0.69 },
  ],
  question: {
    id: 'q1', text: 'Which zone contains the camera?', gain: 0.19, breakEven: 0.0526, cost: 0.95, wordedBy: 'Qwen3.5-9B', chosenBy: 'Solver',
    scope: ['Portugal', 'Porto district'],
    options: [
      { key: 'A', label: 'Porto riverfront, Ribeira to Miragaia', reason: 'Postcode area 4050 and the river to the south-west', chips: ['e2', 'e9'], point: [41.1415, -8.6165] },
      { key: 'B', label: 'Vila Nova de Gaia riverfront', reason: 'Same river, same 22 phone prefix; postcode would be 4400', chips: ['e3', 'e9'], point: [41.1368, -8.6100] },
      { key: 'C', label: 'Rest of Porto district', reason: 'Granite and the 22 prefix fit, the river view narrows it', chips: ['e6', 'e3'], point: [41.18, -8.58] },
      { key: 'D', label: 'None of these (anywhere else in PT, ES or FR)', reason: 'Covers everywhere outside A to C, so a wrong scope can be corrected', chips: [], point: null, none: true },
    ],
    answer: 'A', answeredAt: 212,
  },
  spot: {
    refs: [
      { id: 'r1', inliers: 412, matches: 530, dist: 38, lat: 41.14094, lng: -8.61290, accepted: true },
      { id: 'r2', inliers: 118, matches: 260, dist: 96, lat: 41.14051, lng: -8.61401, accepted: true },
      { id: 'r3', inliers: 36, matches: 190, dist: 142, lat: 41.14152, lng: -8.61198, accepted: false, reason: 'Inliers below 50' },
    ],
    camera: { lat: 41.14081, lng: -8.61315, r: 22, rSource: 'source GPS plus viewpoint offset' },
    offset: 17,
  },
  answer: { lat: 41.14081, lng: -8.61315, role: 'camera', method: 'reference_camera', r: 22, rSource: 'estimated offset', multiplier: 0.95, expected: 12500, max: 16050.52, mostLikely: true },
};

CASE_A.evidence = [
  { id: 'e2', kind: 'text', stage: 'read', actor: 'model', model: 'PP-OCRv6-medium', obs: '4050-253', conf: 0.94, ref: 't2',
    inference: 'a Portuguese postcode; area 4050 is central Porto', estimate: { label: 'Porto', v: 0.47 }, pol: { ribeira: 1, miragaia: 1, gaia: -1, alfama: -1 }, t: 41.2 },
  { id: 'e3', kind: 'text', stage: 'read', actor: 'model', model: 'PP-OCRv6-medium', obs: '22• ••• •••', conf: 0.71, ref: 't3',
    inference: 'a Portuguese landline; prefix 22 is Porto and Gaia', pol: { ribeira: 1, miragaia: 1, gaia: 1, alfama: -1 }, t: 41.9 },
  { id: 'e1', kind: 'text', stage: 'read', actor: 'model', model: 'PP-OCRv6-medium', obs: 'CAFÉ', conf: 0.97, ref: 't1',
    inference: 'the same word in pt, es and fr — no help on its own', pol: {}, t: 40.8 },
  { id: 'e4', kind: 'language', stage: 'read', actor: 'model', model: 'Language-ID ×3', obs: 'pt 0.93 · gl 0.04 · es 0.02 · fr 0.01', conf: 0.93,
    inference: 'Portuguese spelling, not Galician', pol: { ribeira: 1, miragaia: 1, gaia: 1, alfama: 1 }, t: 43.0 },
  { id: 'e5', kind: 'object', stage: 'detect', actor: 'model', model: 'YOLOE-26-L · SAM 3', obs: '17 boxes kept, 3 rejected', conf: null,
    inference: 'signs, balconies, an azulejo panel; no licence plate after all', pol: {}, t: 33.5 },
  { id: 'e6', kind: 'checklist', stage: 'describe', actor: 'model', model: 'Qwen3.5-9B', obs: 'Granite masonry: yes', conf: null,
    inference: 'granite is the northern building stone; Lisbon builds in limestone', pol: { ribeira: 1, miragaia: 1, gaia: 1, alfama: -1 }, t: 66.0 },
  { id: 'e7', kind: 'checklist', stage: 'describe', actor: 'model', model: 'Qwen3.5-9B', obs: 'Calçada portuguesa: not_visible', conf: null,
    inference: 'pavement out of view; says nothing either way', pol: {}, notVisible: true, t: 66.4 },
  { id: 'e9', kind: 'checklist', stage: 'describe', actor: 'model', model: 'Qwen3.5-9B', obs: 'River visible: yes', conf: null,
    inference: 'a riverfront; narrows to the banks of the Douro', pol: { ribeira: 1, miragaia: 1, gaia: 1, alfama: 0 }, t: 66.8 },
  { id: 'e10', kind: 'measure', stage: 'measure', actor: 'model', model: 'EoMT-L', obs: 'sky 31% · building 44% · road 17% · water 5% · tree 3%', conf: null,
    inference: 'a dense waterside street; water at a bearing of ~200°', pol: { ribeira: 1, gaia: 0, miragaia: 1 }, t: 72.0 },
  { id: 'e11', kind: 'sun', stage: 'measure', actor: 'model', model: 'pvlib · EoMT-L', obs: 'sun at yaw 141°, elevation 22°', conf: null,
    inference: 'with 14:30 UTC on 15 Jan, image yaw 0 points to bearing 64° ± 12°; the river lies south-west', pol: { ribeira: 1, gaia: -1, miragaia: 1 }, t: 73.1 },
  { id: 'e12', kind: 'neighbour', stage: 'geo', actor: 'model', model: 'PE-Core · kNN', obs: '5 nearest reference photos: 4 Porto/Gaia, 1 Lisboa', conf: null, group: 'pecore',
    inference: 'the closest-looking photos were taken on the Porto riverfront', estimate: { label: 'Porto', v: 0.62 }, pol: { ribeira: 1, miragaia: 1, gaia: 1, alfama: 0 }, t: 82.0 },
  { id: 'e13', kind: 'region', stage: 'geo', actor: 'model', model: 'mini-PIGEON (on PE-Core)', obs: 'Porto 0.47 · Braga 0.12 · Lisboa 0.11', conf: null, group: 'pecore',
    inference: 'pixels alone point north, Porto first', estimate: { label: 'Porto', v: 0.47 }, pol: { ribeira: 1, miragaia: 1, gaia: 1, alfama: -1 }, t: 83.4 },
  { id: 'e14', kind: 'name', stage: 'names', actor: 'model', model: 'OSM · Wikidata · GeoNames', obs: '"4050": postcode area · "Cais da Ribeira": landmark', conf: null,
    inference: 'an area coordinate and a landmark coordinate, not a camera position', pol: { ribeira: 1 }, sub: 'local index, offline', t: 85.0 },
  { id: 'e15', kind: 'contradiction', stage: 'fusion', actor: 'solver', model: 'Solver (code)', obs: 'VLM landmark guess "Alfama" (0.18) vs postcode 4050-253', conf: null,
    inference: 'the postcode outweighs a low-confidence landmark guess; Alfama stays, its range widens', pol: { alfama: -1 }, between: ['e2', 'e6'], t: 86.1 },
];
CASE_A.groups = [{ id: 'pecore', label: 'One voice: PE-Core encoder', members: ['e12', 'e13'], cap: 0.35, note: 'Neighbours and regions share one image encoder, so fusion caps their combined weight' }];
CASE_A.matrix = {
  candidates: ['ribeira', 'gaia', 'miragaia', 'alfama'],
  names: { ribeira: 'Ribeira', gaia: 'Gaia', miragaia: 'Miragaia', alfama: 'Alfama' },
};

export const CASE_B: any = {
  id: 'B', label: 'Case 4', file: 'IMG_20260512_110547_00_318.jpg', date: '2026-05-12', time: '11:05:47', shot: 318,
  urban: 'non-urban', urbanSource: 'official', special: false, size: [6080, 3040],
  run: { used: 298, budget: 480, session: 1880, sessionBudget: 3600, gpu: 11.8, gpuMax: 16, multiplier: 1.0, expected: 11300, expectedRange: [8200, 12900] },
  multiplierHistory: [{ t: 0, m: 1.0, what: 'Run started' }, { t: 188, m: 1.0, what: 'Skipped question 1 · free · nothing changed' }],
  scene: 'rural', yawToBearing: 312, yawToBearingErr: 15,
  stages: [
    { id: 'intake', name: 'Intake', models: ['Filename parser'], status: 'done', dur: 0.1 },
    { id: 'views', name: 'Views', models: ['py360convert'], status: 'done', dur: 1.7 },
    { id: 'detect', name: 'Detect', optional: true, models: ['YOLOE-26-L', 'SAM 3'], status: 'skipped', note: 'Dropped for non-urban scenes' },
    { id: 'read', name: 'Read', models: ['PP-OCRv6-medium', 'Language-ID ×3'], status: 'done', dur: 3.2, note: 'No text found' },
    { id: 'describe', name: 'Describe', models: ['Qwen3.5-9B'], status: 'done', dur: 19.6, gb: 7.4 },
    { id: 'measure', name: 'Measure', optional: true, models: ['EoMT-L', 'pvlib'], status: 'done', dur: 4.8, gb: 1.1 },
    { id: 'geo', name: 'Pixel geolocation', models: ['PE-Core', 'mini-PIGEON', 'GeoCLIP'], status: 'done', dur: 10.2, gb: 1.7 },
    { id: 'names', name: 'Name lookup', models: ['OSM · Wikidata · GeoNames index'], status: 'skipped', note: 'Nothing to look up' },
    { id: 'fusion', name: 'Fusion', models: ['Solver (code)'], status: 'done', dur: 0.2, solver: true },
    { id: 'ask', name: 'Ask', models: ['Solver (code)', 'Qwen3.5-9B'], status: 'done', dur: 1.1, note: 'Skipped · free' },
    { id: 'spot', name: 'Exact spot', optional: true, models: ['MegaLoc', 'ALIKED + LightGlue'], status: 'skipped', note: 'Not run for non-urban scenes' },
    { id: 'answer', name: 'Answer', models: ['Solver (code)'], status: 'done', dur: 0.1, solver: true },
  ],
  texts: [],
  language: null,
  checklist: [
    { item: 'Cork oak (stripped trunks, painted digit)', answer: 'yes' }, { item: 'Holm oak', answer: 'yes' }, { item: 'Unpaved track', answer: 'yes' },
    { item: 'Whitewashed farmhouse, blue trim (distant)', answer: 'yes' }, { item: 'Red-brown soil', answer: 'yes' }, { item: 'Terrain', answer: 'gently rolling' },
    { item: 'Road signs', answer: 'not_visible' },
  ],
  shares: [{ id: 'sky', v: 0.47 }, { id: 'grass', v: 0.24 }, { id: 'tree', v: 0.22 }, { id: 'ground', v: 0.06 }, { id: 'building', v: 0.01 }],
  sun: { azimuth: 130, elevation: 61, yaw: 178, bearingOfYaw0: 312, err: 15 },
  regions: [{ name: 'Évora', v: 0.31, lo: 0.22, hi: 0.41 }, { name: 'Beja', v: 0.24, lo: 0.16, hi: 0.33 }, { name: 'Portalegre', v: 0.17, lo: 0.10, hi: 0.25 }, { name: 'Extremadura (ES)', v: 0.12, lo: 0.06, hi: 0.20 }, { name: 'Setúbal', v: 0.09 }, { name: 'Other', v: 0.07, other: true }],
  candidates: [
    { id: 'evora', rank: 1, name: 'Alentejo Central (Évora)', level: 'region', v: 0.33, lo: 0.22, hi: 0.44, delta: 0.02, sup: 6, con: 0, lat: 38.57, lng: -7.91 },
    { id: 'beja', rank: 2, name: 'Baixo Alentejo (Beja)', level: 'region', v: 0.25, lo: 0.16, hi: 0.35, delta: 0.01, sup: 5, con: 0, lat: 37.95, lng: -7.87 },
    { id: 'portalegre', rank: 3, name: 'Alto Alentejo (Portalegre)', level: 'region', v: 0.17, lo: 0.10, hi: 0.26, delta: 0, sup: 5, con: 0, lat: 39.20, lng: -7.60 },
    { id: 'extremadura', rank: 4, name: 'Extremadura (ES) · dehesa', level: 'region', v: 0.13, lo: 0.06, hi: 0.22, delta: 0, sup: 5, con: 0, lat: 38.90, lng: -6.40, lookalike: true },
    { id: 'other', rank: 5, name: 'Other', level: 'area', v: 0.12, lo: 0.06, hi: 0.19, other: true },
  ],
  ruledOut: [],
  lookalikes: [{ a: 'Alentejo montado (PT)', b: 'Extremadura dehesa (ES)', shared: ['cork oak', 'holm oak', 'red-brown soil', 'rolling terrain', 'whitewashed farmhouse'], differ: 'Only text or a road sign would separate them; none is visible' }],
  question: {
    id: 'q1', text: 'Which zone contains the camera?', gain: 0.11, breakEven: 0.0526, cost: 0.95, wordedBy: 'Qwen3.5-9B', chosenBy: 'Solver', scope: ['Portugal · Spain · France', 'Alentejo'],
    options: [
      { key: 'A', label: 'Alto Alentejo', reason: 'Cork and holm oak on rolling ground; granite outcrops would fit', chips: ['b1', 'b2'], point: [39.25, -7.55], region: 'PT-12' },
      { key: 'B', label: 'Alentejo Central', reason: 'Montado with red-brown soil; the highest region estimate', chips: ['b1', 'b5'], point: [38.62, -7.85], region: 'PT-07' },
      { key: 'C', label: 'Baixo Alentejo and Alentejo Litoral', reason: 'Open montado, whitewash with blue trim', chips: ['b4', 'b5'], point: [37.95, -7.95], region: 'PT-02' },
      { key: 'D', label: 'Anywhere else in PT, ES or FR', reason: 'Covers Extremadura dehesa, which looks the same', chips: ['b6'], point: null, none: true },
    ],
    answer: null, skippedAt: 188,
  },
  answer: { lat: 38.60610, lng: -7.84120, role: 'area', method: 'geographic_cell', r: 4200, rSource: 'geometric bound', multiplier: 1.0, expected: 11300, max: 16050.52, mostLikely: false,
    why: 'The cell centre between Évora and Beja scores higher in expectation than Évora alone: on the non-Urban curve a 40 km miss still keeps 20%, so hedging toward the second candidate pays.' },
};
CASE_B.evidence = [
  { id: 'b0', kind: 'text', stage: 'read', actor: 'model', model: 'PP-OCRv6-medium', obs: 'No text found', conf: null, inference: 'no signs, plates or painted words in any of the 10 views', pol: {}, empty: true, t: 9.0 },
  { id: 'b1', kind: 'checklist', stage: 'describe', actor: 'model', model: 'Qwen3.5-9B', obs: 'Cork oak: yes (stripped trunks, painted digit)', conf: null, inference: 'montado or dehesa: southern Portugal or western Spain', pol: { evora: 1, beja: 1, portalegre: 1, extremadura: 1 }, t: 28.0 },
  { id: 'b2', kind: 'checklist', stage: 'describe', actor: 'model', model: 'Qwen3.5-9B', obs: 'Holm oak: yes', conf: null, inference: 'dry interior, either side of the border', pol: { evora: 1, beja: 1, portalegre: 1, extremadura: 1 }, t: 28.4 },
  { id: 'b4', kind: 'checklist', stage: 'describe', actor: 'model', model: 'Qwen3.5-9B', obs: 'Whitewashed farmhouse with blue trim: yes (distant)', conf: null, inference: 'Alentejo vernacular, also found in Extremadura', pol: { evora: 1, beja: 1, portalegre: 1, extremadura: 0 }, t: 28.9 },
  { id: 'b5', kind: 'checklist', stage: 'describe', actor: 'model', model: 'Qwen3.5-9B', obs: 'Red-brown soil: yes', conf: null, inference: 'common across the Alentejo plain', pol: { evora: 1, beja: 1, portalegre: 0, extremadura: 1 }, t: 29.2 },
  { id: 'b6', kind: 'checklist', stage: 'describe', actor: 'model', model: 'Qwen3.5-9B', obs: 'Road signs: not_visible', conf: null, inference: "can't tell the country from signage", pol: {}, notVisible: true, t: 29.6 },
  { id: 'b7', kind: 'sun', stage: 'measure', actor: 'model', model: 'pvlib · EoMT-L', obs: 'sun at yaw 178°, elevation 61°', conf: null, inference: 'image yaw 0 points to bearing 312° ± 15°', pol: {}, t: 36.0 },
  { id: 'b8', kind: 'region', stage: 'geo', actor: 'model', model: 'mini-PIGEON (on PE-Core)', obs: 'Évora 0.31 · Beja 0.24 · Portalegre 0.17 · Extremadura 0.12', conf: null, group: 'pecore', inference: 'Alentejo first; Spain not excluded', estimate: { label: 'Évora', v: 0.31 }, pol: { evora: 1, beja: 1, portalegre: 1, extremadura: 1 }, t: 47.0 },
];
CASE_B.matrix = { candidates: ['evora', 'beja', 'portalegre', 'extremadura'], names: { evora: 'Évora', beja: 'Beja', portalegre: 'Portalegre', extremadura: 'Extremadura' } };
CASE_B.groups = [{ id: 'pecore', label: 'One voice: PE-Core encoder', members: ['b8'], cap: 0.35 }];

export const QUEUE = [
  { label: 'Case 1', status: 'submitted', multiplier: 1.0, expected: 13900, used: 262 },
  { label: 'Case 2', status: 'done', multiplier: 0.95, expected: 9800, used: 431 },
  { label: 'Case 3', status: 'needs-answer', multiplier: 1.0, expected: 9100, used: 205, current: true, gain: 0.19 },
  { label: 'Case 4', status: 'processing', stage: 'Describe', elapsed: 64 },
  { label: 'Case 5', status: 'waiting' },
  { label: 'Special One', status: 'waiting', special: true },
];

export const LOG_A = [
  { t: 0.0, type: 'run.started', actor: 'solver', text: 'New conversation · empty evidence · nothing carried over' },
  { t: 0.1, type: 'stage.finished', stage: 'intake', actor: 'solver', text: '2026-01-15 14:30:12 UTC · shot 204 · Urban (official)' },
  { t: 1.9, type: 'stage.finished', stage: 'views', actor: 'model', model: 'py360convert', text: '8 views of 45°, sky, ground; photographer mask 18%' },
  { t: 27.3, type: 'evidence.added', stage: 'detect', actor: 'model', model: 'YOLOE-26-L', text: '20 boxes proposed' },
  { t: 33.5, type: 'evidence.added', stage: 'detect', actor: 'model', model: 'SAM 3', text: '3 boxes rejected (licence plate 0.31, SAM 0.02)' },
  { t: 40.8, type: 'evidence.added', stage: 'read', actor: 'model', model: 'PP-OCRv6-medium', text: '"CAFÉ" 0.97' },
  { t: 41.2, type: 'evidence.added', stage: 'read', actor: 'model', model: 'PP-OCRv6-medium', text: '"4050-253" 0.94 · postcode · PT' },
  { t: 43.0, type: 'evidence.added', stage: 'read', actor: 'model', model: 'Language-ID ×3', text: 'pt 0.93 · gl 0.04 · es 0.02' },
  { t: 66.0, type: 'evidence.added', stage: 'describe', actor: 'model', model: 'Qwen3.5-9B', text: 'Granite masonry: yes' },
  { t: 73.1, type: 'evidence.added', stage: 'measure', actor: 'model', model: 'pvlib', text: 'Yaw 0 points to bearing 64° ± 12°' },
  { t: 83.4, type: 'evidence.added', stage: 'geo', actor: 'model', model: 'mini-PIGEON', text: 'Porto 0.47 · Braga 0.12 · Lisboa 0.11' },
  { t: 86.3, type: 'candidates.updated', stage: 'fusion', actor: 'solver', text: 'Ribeira 0.52 · Gaia 0.21 · Miragaia 0.12 · Galicia ruled out' },
  { t: 86.4, type: 'output.produced', stage: 'answer', actor: 'solver', text: 'First answer 41.14070, −8.61310 · ± 180 m · ×1.00' },
  { t: 88.0, type: 'question.asked', stage: 'ask', actor: 'solver', text: 'Which zone contains the camera? · gain +19% vs 5.26%' },
  { t: 212.0, type: 'question.answered', stage: 'ask', actor: 'team', text: 'A · Porto riverfront · ×0.95' },
  { t: 212.6, type: 'candidates.updated', stage: 'fusion', actor: 'solver', text: 'Ribeira 0.69 · Miragaia 0.21 · Gaia 0.03' },
  { t: 309.0, type: 'stage.started', stage: 'spot', actor: 'model', model: 'MegaLoc', text: '3 reference photos within 150 m' },
  { t: 331.5, type: 'evidence.added', stage: 'spot', actor: 'model', model: 'ALIKED + LightGlue', text: 'Inliers 412 / 118 / 36' },
  { t: 340.0, type: 'output.produced', stage: 'answer', actor: 'solver', text: '41.14081, −8.61315 · ± 22 m · ×0.95' },
];

// map layers derived from pixel-geolocation evidence (blobs → heat cells, sampled points)
CASE_A.heatCountry = [{ lat: 41.15, lng: -8.61, w: 0.95, s: 0.22 }, { lat: 41.55, lng: -8.42, w: 0.38, s: 0.2 }, { lat: 38.72, lng: -9.14, w: 0.36, s: 0.2 }, { lat: 41.7, lng: -8.8, w: 0.22, s: 0.18 }, { lat: 42.4, lng: -8.6, w: 0.22, s: 0.3 }];
CASE_A.heatTown = [{ lat: 41.1409, lng: -8.6131, w: 0.95, s: 0.0011 }, { lat: 41.1370, lng: -8.6118, w: 0.55, s: 0.0012 }, { lat: 41.1434, lng: -8.6205, w: 0.5, s: 0.001 }];
CASE_A.viewCountry = { lat: 40.4, lng: -5.2, span: 16 };
CASE_A.viewTown = { lat: 41.1405, lng: -8.6150, span: 0.03 };
CASE_A.viewSpot = { lat: 41.1409, lng: -8.6132, span: 0.0062 };
CASE_A.zones = [
  { key: 'A', poly: [[41.1411, -8.6235], [41.1452, -8.6235], [41.1450, -8.6080], [41.1404, -8.6080], [41.1404, -8.6140], [41.1410, -8.6200]], point: [41.1415, -8.6165], label: 'A · Porto riverfront' },
  { key: 'B', poly: [[41.1381, -8.6235], [41.1384, -8.6140], [41.1386, -8.6080], [41.1352, -8.6080], [41.1347, -8.6235]], point: [41.1368, -8.6100], label: 'B · Gaia riverfront' },
  { key: 'C', rest: true, point: [41.1318, -8.6268], label: 'C · rest of Porto district' },
];
CASE_B.heat = [{ lat: 38.57, lng: -7.91, w: 0.8, s: 0.33 }, { lat: 37.95, lng: -7.87, w: 0.66, s: 0.33 }, { lat: 39.2, lng: -7.6, w: 0.5, s: 0.28 }, { lat: 38.9, lng: -6.4, w: 0.46, s: 0.38 }, { lat: 38.3, lng: -8.6, w: 0.3, s: 0.24 }];
CASE_B.view = { lat: 38.55, lng: -7.4, span: 5.2 };
CASE_B.zones = [
  { key: 'A', region: 'PT-12', point: [39.25, -7.55], label: 'A · Alto Alentejo' },
  { key: 'B', region: 'PT-07', point: [38.62, -7.85], label: 'B · Alentejo Central' },
  { key: 'C', region: 'PT-02', point: [37.92, -7.95], label: 'C · Baixo Alentejo' },
  { key: 'D', rest: true, point: null, label: 'D · anywhere else in PT, ES or FR' },
];
