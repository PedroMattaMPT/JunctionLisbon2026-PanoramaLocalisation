// Screen compositions (showcase pages). Every screen is built only from components + a case record,
// the way the app builds everything from the event log.
import { h, Fragment, cx, fmtCoord, fmtTime, fmtMult, fmtInt } from './rt';
import { Icon } from './icons';
import { Density, Button, Badge, Tabs, Toast, Stamp, EmptyState, Dialog, KeyCap } from './base';
import { RunBar, Wordmark, ModelRoster, CaseCard, ShortcutBar, CleanStateCheck, ModelChip, SystemBadge, Timer, MultiplierChip, ScoreReadout, GpuMeter } from './shell';
import { PanoramaStrip, Viewer360, ZoomCrop, LayerToggles, BearingRuler } from './panorama';
import { StageTimeline, StageRow, EvidenceCard, CorrelationBracket, CaptionBar } from './reasoning';
import { CandidateList, CandidateRow, RuledOutRow, Funnel, EvidenceMatrix } from './beliefs';
import { LanguageVote, SceneShares, CompassDial, EstimateBars, GainMeter, ConfidenceMeter } from './charts';
import { MapView, UncertaintyRing } from './map';
import { QuestionCard, AnswerReceipt, CueComposer } from './human';
import { CoordinateBlock, AnswerSlots, ChoiceNote, ScoreCurve, EventLog, ReplayScrubber, ExportBar } from './output';
import { DropZone, FilenameParse, MatchView, LeaderLines } from './extra';
import { CASE_A, CASE_B, ROSTER, QUEUE, LOG_A } from './samples';

const A = CASE_A, B = CASE_B;
const KEYS_RUN = [{ k: 'J/K', label: 'next / previous evidence' }, { k: 'L', label: 'layers' }, { k: 'V', label: 'strip / 360° view' }, { k: 'M', label: 'map focus' }, { k: 'C', label: 'cue' }, { k: '⇧⏎', label: 'submit' }];
const KEYS_Q = [{ k: '1–4', label: 'answer (×0.95)' }, { k: 'S', label: 'skip (free)' }, { k: 'O', label: 'copy all links' }, { k: 'J/K', label: 'move between options' }];
const cands = (list: any[]) => list.filter(c => !c.other).map(c => ({ id: c.id, rank: c.rank, lat: c.lat, lng: c.lng, name: (c.name.split(' · ')[1] || c.name) }));
const ev = (c: any, id: string) => c.evidence.find((e: any) => e.id === id);
const Panel = ({ title, aside, children, className, style }: any) => h('section', { className: cx('aq-panel', className), style }, title ? h('header', { className: 'aq-panel-h' }, h('span', { className: 'console-title' }, title), aside || null) : null, children);

// ---------------------------------------------------------------------------
export function ScreenIntake() {
  const files = [
    { file: A.file, urban: 'urban', source: 'official' },
    { file: 'IMG_20260512_110547_00_318.jpg', urban: 'non-urban', source: 'official' },
    { file: 'IMG_20250125_144630_00_319.jpg', urban: 'urban', source: 'inferred' },
    { file: 'IMG_20260911_125512_00_749.jpg', size: [5760, 2880], urban: 'non-urban', source: 'inferred', message: 'Not 6080×3040 — accepted as 2:1, flagged in the log.' },
    { file: 'IMG_20260605_092457_00_064.jpg', urban: 'unknown', source: 'unknown', special: true },
    { file: 'pano_final.jpg', urban: 'unknown', source: 'unknown', message: 'Filename does not parse: date, time and shot unknown, so the sun cannot fix north.' },
  ];
  return h(Density, { value: 'console', className: 'aq-screen', style: { width: 1440, height: 900 } },
    h('header', { className: 'aq-runbar' }, h('div', { className: 'aq-runbar-wm' }, h(Wordmark, { size: 22 })), h('span', { className: 'console-heading' }, 'New session'),
      h(Timer, { label: 'Session', used: 0, budget: 3600, compact: true }), h(GpuMeter, { used: 9.4, compact: true }), h('div', { className: 'aq-runbar-sys' }, h(SystemBadge, { kind: 'worker-online' }), h(SystemBadge, { kind: 'tiles-offline' }))),
    h('div', { className: 'aq-intake' },
      h('div', { className: 'aq-intake-main' },
        h('div', { className: 'aq-intake-title' }, h('h1', { className: 'narrative-title' }, 'Six panoramas, six sealed cases'), h('p', { className: 'console-body aq-ink2' }, 'Each file becomes its own case with a new model conversation and empty evidence. Mark the Special One; set the Urban label where it is known.')),
        h(DropZone, { state: 'valid', files: files as any })),
      h('aside', { className: 'aq-intake-side' },
        h(CleanStateCheck, { caseLabel: 'every case', items: [{ label: 'New model conversation per case', ok: true }, { label: 'Evidence file starts empty', ok: true }, { label: 'Nothing carried over between cases', ok: true }, { label: 'Queue never groups by date', ok: true }] }),
        h(ModelRoster, { models: ROSTER, compact: true }),
        h('div', { className: 'aq-intake-go' }, h('div', { className: 'console-body aq-ink2' }, '6 files · 1 flagged size · 1 unparsed name · Special One: case 5'), h(Button, { variant: 'primary', icon: 'play', shortcut: '⏎' }, 'Start the run')))));
}

// ---------------------------------------------------------------------------
export function ScreenRunConsole() {
  const run = { ...A, run: A.run };
  const evidence = ['e2', 'e3', 'e6'].map(id => ev(A, id));
  return h(Density, { value: 'console', className: 'aq-screen', style: { width: 1440, height: 900 } },
    h(RunBar, { c: run }),
    h(LeaderLines, { links: [['e2', 't2'], ['e2', 'area-4050']], className: 'aq-console' },
      h('div', { className: 'aq-col-pano' },
        h(Panel, { title: 'Panorama', aside: h('span', { className: 'console-micro aq-ink3' }, `${A.file} · 6080×3040`) },
          h(PanoramaStrip, { c: A, width: 560, selected: 't2', ruler: 'bearing', labelMode: 'selected', layers: { boxes: true, text: true, mask: true, water: false } }),
          h(LayerToggles, { layers: { boxes: true, text: true, mask: true }, counts: { boxes: '17 · 3 rejected', text: '3' }, columns: 2 })),
        h('div', { className: 'aq-pano-lower' }, h(Viewer360, { c: A, yaw: 212, width: 368, height: 214, selected: 't2' }),
          h('div', { className: 'aq-col' }, h(ZoomCrop, { c: A, target: 't2', width: 184, height: 96 }), h(CompassDial, { yawToBearing: 64, err: 12, sun: { azimuth: 205, elevation: 22 }, water: 200, size: 128 })))),
      h('div', { className: 'aq-col-reason' },
        h(Tabs, { value: 'evidence', tabs: [{ id: 'stages', label: 'Stages', count: 12 }, { id: 'evidence', label: 'Evidence', count: 14 }, { id: 'matrix', label: 'Matrix' }, { id: 'log', label: 'Log', count: 19 }] }),
        h('ol', { className: 'aq-timeline-l aq-nowline' }, h(StageRow, { stage: A.stages[10], pass: 2 })),
        h('div', { className: 'aq-feed' },
          h(EvidenceCard, { e: evidence[0], names: A.matrix.names, selected: true, crop: h('span', { 'data-leader': 'e2' }) }),
          h(CorrelationBracket, { label: A.groups[0].label, cap: A.groups[0].cap }, h(EvidenceCard, { e: ev(A, 'e13'), names: A.matrix.names, compact: true }), h(EvidenceCard, { e: ev(A, 'e12'), names: A.matrix.names, compact: true })),
          h(EvidenceCard, { e: evidence[1], names: A.matrix.names }),
          h(EvidenceCard, { e: evidence[2], names: A.matrix.names }))),
      h('div', { className: 'aq-col-map' },
        h(MapView, { view: { lat: 41.1405, lng: -8.6145, span: 0.026 }, width: 424, height: 330, heat: A.heatTown, candidates: cands(A.candidatesAfter), selected: 'ribeira', refs: A.neighbours.slice(0, 4).map((n: any) => ({ id: n.id, lat: n.lat, lng: n.lng })), area: { lat: 41.1432, lng: -8.6150, r: 420, label: 'postcode area 4050' }, labels: true }),
        h('span', { className: 'aq-area-anchor', 'data-leader': 'area-4050' }),
        h('div', { className: 'aq-pad' }, h(CandidateList, { candidates: A.candidatesAfter, selected: 'ribeira', ruledOut: A.ruledOut, title: 'Candidates' })))),
    h(ShortcutBar, { keys: KEYS_RUN }));
}

// ---------------------------------------------------------------------------
export function ScreenQuestion() {
  const c = { ...A, run: { ...A.run, used: 208, session: 1263, multiplier: 1.0, expected: 9100 }, multiplierHistory: [A.multiplierHistory[0]] };
  return h(Density, { value: 'console', className: 'aq-screen', style: { width: 1440, height: 900 } },
    h(RunBar, { c }),
    h('div', { className: 'aq-qlayout' },
      h('div', { className: 'aq-col-pano' },
        h(Panel, { title: 'Panorama' }, h(PanoramaStrip, { c: A, width: 456, ruler: 'bearing', labelMode: 'text', layers: { boxes: false, text: true } })),
        h(Panel, { title: 'Candidates now' }, h(CandidateList, { candidates: A.candidatesBefore, selected: 'ribeira', ruledOut: A.ruledOut, title: '', caption: 'before the answer' }))),
      h('div', { className: 'aq-col-q' }, h(QuestionCard, { q: A.question, evidence: A.evidence, hoverKey: 'A', cueLine: true })),
      h('div', { className: 'aq-col-map' },
        h(MapView, { view: A.viewTown, width: 448, height: 520, heat: A.heatTown, zones: A.zones, dimOthers: true, inset: { view: { lat: 40, lng: -6, span: 14 }, box: { lat: 41.2, lng: -8.4, span: 0.9 }, label: 'D: everywhere outside' } }),
        h('div', { className: 'aq-pad console-body aq-ink2' }, 'Zones never overlap and together cover the current scope. A click picks a zone; the agent computes the coordinate from it. Option links open on teammates’ devices; nothing seen there goes back in except a click on an option.'))),
    h(ShortcutBar, { keys: KEYS_Q }));
}

export function ScreenQuestionOutcomes() {
  const zonesA = A.zones.map((z: any) => ({ ...z, chosen: z.key === 'A', dim: z.key !== 'A' }));
  return h(Density, { value: 'console', className: 'aq-screen', style: { width: 1440, height: 900 } },
    h('div', { className: 'aq-outcomes' },
      h('section', { className: 'aq-outcome' },
        h('header', { className: 'aq-outcome-h' }, h('span', { className: 'narrative-title' }, 'Answered'), h('span', { className: 'console-body aq-ink2' }, 'Case 3 · the team picked A'), h(MultiplierChip, { value: 0.95, history: A.multiplierHistory })),
        h(AnswerReceipt, { kind: 'answered', q: A.question, before: A.candidatesBefore, after: A.candidatesAfter, multiplierBefore: 1, multiplierAfter: 0.95, t: 212 }),
        h(MapView, { view: A.viewTown, width: 680, height: 470, heat: A.heatTown, zones: zonesA, candidates: cands(A.candidatesAfter), legend: false })),
      h('section', { className: 'aq-outcome' },
        h('header', { className: 'aq-outcome-h' }, h('span', { className: 'narrative-title' }, 'Skipped'), h('span', { className: 'console-body aq-ink2' }, 'Case 4 · free, and nothing moved'), h(MultiplierChip, { value: 1.0, history: B.multiplierHistory })),
        h(AnswerReceipt, { kind: 'skipped', q: B.question, before: B.candidates, multiplierBefore: 1, t: 188 }),
        h(MapView, { view: B.view, width: 680, height: 470, heat: B.heat, zones: B.zones, legend: false, offline: false }))));
}

// ---------------------------------------------------------------------------
export function ScreenExactSpot() {
  const sp = A.spot;
  return h(Density, { value: 'console', className: 'aq-screen', style: { width: 1440, height: 900 } },
    h(RunBar, { c: A }),
    h('div', { className: 'aq-spot' },
      h('div', { className: 'aq-spot-main' },
        h(Panel, { title: 'Exact spot', aside: h(Badge, { tone: 'outline' }, 'conditional · urban') },
          h(MatchView, { c: A, width: 860, height: 300, lines: 40 })),
        h(Panel, { title: 'Reference photos near the candidates' },
          h('table', { className: 'aq-table console-body' }, h('thead', null, h('tr', null, ['', 'Reference', 'Distance', 'Matches', 'Inliers', 'Verdict'].map(x => h('th', { key: x, className: 'console-micro' }, x)))),
            h('tbody', null, sp.refs.map((r: any) => h('tr', { key: r.id, className: r.accepted ? '' : 'is-out' },
              h('td', null, h(Icon, { name: r.accepted ? 'done' : 'failed', className: r.accepted ? 'aq-c-support' : 'aq-c-contra' })), h('td', { className: 'console-data' }, r.id), h('td', { className: 'console-data' }, `${r.dist} m`), h('td', { className: 'console-data' }, r.matches), h('td', { className: 'console-data' }, r.inliers),
              h('td', null, r.accepted ? 'accepted · geometry consistent' : `rejected · ${r.reason.toLowerCase()}`)))))),
        h('div', { className: 'aq-offset' }, h(Icon, { name: 'info' }), h('div', null, h('div', { className: 'console-heading' }, 'A good image match is not a 10 m camera fix'), h('div', { className: 'console-body aq-ink2' }, `412 inliers place the camera near r1’s viewpoint, but r1 was taken ${sp.refs[0].dist} m away and its GPS has its own error. Remaining offset ≈ ${sp.offset} m, so the ring is ± ${sp.camera.r} m (source GPS plus viewpoint offset), not ± 10 m.`)))),
      h('div', { className: 'aq-spot-map' },
        h(MapView, { view: A.viewSpot, width: 500, height: 520, refs: sp.refs.map((r: any) => ({ id: r.id, lat: r.lat, lng: r.lng, accepted: r.accepted, label: `${r.id} · ${r.inliers} inliers` })),
          rings: [{ lat: 41.14094, lng: -8.61290, r: 35, label: 'r1 ± 35 m', tone: 'model' }, { lat: 41.14051, lng: -8.61401, r: 60, label: 'r2 ± 60 m', tone: 'model' }],
          cone: { lat: sp.camera.lat, lng: sp.camera.lng, bearing: 276, err: 12, len: 170, label: '276° ± 12°' }, final: { lat: sp.camera.lat, lng: sp.camera.lng, r: sp.camera.r } }),
        h('div', { className: 'aq-pad' }, h(CoordinateBlock, { a: { ...A.answer, rSource: sp.camera.rSource }, showCopy: false })))),
    h(ShortcutBar, { keys: [{ k: '←/→', label: 'previous / next reference' }, { k: 'R', label: 'show rejected matches' }, { k: 'M', label: 'map focus' }] }));
}

// ---------------------------------------------------------------------------
export function ScreenFinalAnswer() {
  return h(Density, { value: 'console', className: 'aq-screen', style: { width: 1440, height: 900 } },
    h(RunBar, { c: A }),
    h('div', { className: 'aq-final' },
      h('div', { className: 'aq-final-map' }, h(MapView, { view: { lat: 41.14070, lng: -8.61315, span: 0.0062 }, width: 640, height: 640, final: { lat: A.answer.lat, lng: A.answer.lng, r: 22 }, refs: A.spot.refs.filter((r: any) => r.accepted).map((r: any) => ({ id: r.id, lat: r.lat, lng: r.lng })) }),
        h('div', { className: 'aq-pad' }, h(ChoiceNote, { a: A.answer, mostLikelyName: 'Porto · Ribeira 0.69' }))),
      h('div', { className: 'aq-final-side' },
        h('div', { className: 'aq-final-head' }, h('h1', { className: 'narrative-title' }, 'Best estimate'), h(Stamp, { kind: 'estimate' })),
        h(CoordinateBlock, { a: A.answer, size: 'lg' }),
        h(AnswerSlots, { a: A.answer }),
        h(ScoreCurve, { urban: 'urban', band: [10, 44], expected: 12500, multiplier: 0.95, width: 500, height: 170 }),
        h(ExportBar, {}))),
    h(ShortcutBar, { keys: [{ k: 'C', label: 'copy lat, lng' }, { k: 'E', label: 'export JSON log' }, { k: '⇧⏎', label: 'submit (asks to confirm)' }, { k: 'N', label: 'next case' }] }));
}

// ---------------------------------------------------------------------------
export function ScreenCaseReport() {
  return h(Density, { value: 'console', theme: 'light', className: 'aq-screen aq-report', style: { width: 1440 } },
    h('header', { className: 'aq-report-h' },
      h('div', { className: 'aq-report-t' }, h(Wordmark, { size: 26 }), h('h1', { className: 'narrative-display' }, 'Case 3: the Ribeira quay, Porto'),
        h('p', { className: 'console-body aq-ink2' }, `${A.file} · taken 2026-01-15 14:30:12 UTC · shot 204 · Urban (official) · solved in ${fmtTime(A.run.used)} of 08:00`)),
      h('div', { className: 'aq-report-sum' }, h(Stamp, { kind: 'estimate' }), h(CoordinateBlock, { a: A.answer, showCopy: false }), h(ScoreReadout, { expected: 12500, range: [10900, 13400] }))),
    h('section', { className: 'aq-report-sec' }, h('h2', { className: 'narrative-title' }, 'Replay'), h(ReplayScrubber, { events: LOG_A, t: 212, duration: 340, speed: 1 }), h(EventLog, { events: LOG_A, current: 212 })),
    h('div', { className: 'aq-report-2' },
      h('section', { className: 'aq-report-sec' }, h('h2', { className: 'narrative-title' }, 'What supports what'), h(EvidenceMatrix, { evidence: A.evidence, candidates: A.matrix.candidates, names: A.matrix.names, groups: A.groups })),
      h('div', { className: 'aq-col', style: { gap: 28 } },
        h('section', { className: 'aq-report-sec' }, h('h2', { className: 'narrative-title' }, 'Questions, answers and costs'), h(AnswerReceipt, { kind: 'answered', q: A.question, before: A.candidatesBefore, after: A.candidatesAfter, multiplierBefore: 1, multiplierAfter: 0.95, t: 212 }),
          h('div', { className: 'console-body aq-ink2' }, 'Cues sent: none. Place names converted by a human: none (the app produced the coordinates).')),
        h('section', { className: 'aq-report-sec' }, h('h2', { className: 'narrative-title' }, 'Ruled out, and why'), h(RuledOutRow, { r: A.ruledOut[0], byLabels: { e2: 'postcode 4050-253', e4: 'pt 0.93' }, stamp: true }),
          h(CandidateRow, { c: A.candidatesBefore[3], max: 0.7, ghost: true })),
        h('section', { className: 'aq-report-sec' }, h('h2', { className: 'narrative-title' }, 'Far apart, alike'),
          h('div', { className: 'aq-lookalike' },
            h('div', null, h('div', { className: 'console-heading' }, 'Porto · Ribeira'), h('div', { className: 'console-micro aq-ink3' }, '41.14, −8.61')), h(Icon, { name: 'contradiction' }), h('div', null, h('div', { className: 'console-heading' }, 'Lisboa · Alfama'), h('div', { className: 'console-micro aq-ink3' }, '38.71, −9.13 · 274 km south')),
            h('div', { className: 'aq-lookalike-b console-body' }, h('span', { className: 'aq-ink3' }, 'Share: '), 'azulejo façades, wrought-iron balconies, a river view, a steep old town. ', h('span', { className: 'aq-ink3' }, 'Separated by: '), 'granite against limestone, postcode 4050, the 22 prefix.')),
          h('div', { className: 'aq-lookalike' },
            h('div', null, h('div', { className: 'console-heading' }, 'Alentejo montado'), h('div', { className: 'console-micro aq-ink3' }, 'Case 4 · PT')), h(Icon, { name: 'contradiction' }), h('div', null, h('div', { className: 'console-heading' }, 'Extremadura dehesa'), h('div', { className: 'console-micro aq-ink3' }, 'ES')),
            h('div', { className: 'aq-lookalike-b console-body' }, h('span', { className: 'aq-ink3' }, 'Share: '), 'cork and holm oak, red-brown soil, rolling ground, whitewash. ', h('span', { className: 'aq-ink3' }, 'Separated by: '), 'nothing visible; with no text, Portugal against Spain stays open.')),
          h('div', { className: 'console-micro aq-ink3' }, 'Look-alikes are listed per case from that case’s own evidence; cases never inform each other.')),
        h('section', { className: 'aq-report-actions' }, h(Button, { icon: 'download' }, 'Export JSON log'), h(Button, { icon: 'file' }, 'Export report (PDF)'), h(Button, { variant: 'quiet', icon: 'copy' }, 'Copy lat, lng')))));
}

// ---------------------------------------------------------------------------
export function ScreenQueue() {
  return h(Density, { value: 'console', className: 'aq-screen', style: { width: 1440, height: 900 } },
    h('header', { className: 'aq-runbar' }, h('div', { className: 'aq-runbar-wm' }, h(Wordmark, { size: 22 })), h('span', { className: 'console-heading' }, 'Queue'),
      h(Timer, { label: 'Session', used: 1395, budget: 3600 }), h(ScoreReadout, { expected: 13900 + 9800 }), h(GpuMeter, { used: 11.8, compact: true }), h('div', { className: 'aq-runbar-sys' }, h(SystemBadge, { kind: 'worker-online' }))),
    h('div', { className: 'aq-queue' },
      h('div', { className: 'aq-queue-h' }, h('h1', { className: 'narrative-title' }, 'Five cases and the Special One'), h('p', { className: 'console-body aq-ink2' }, 'One GPU worker takes them in turn, each from a clean state; the case you open goes first. Only status crosses between cards: no images, no dates, no shared evidence.')),
      h('div', { className: 'aq-queue-grid' }, QUEUE.map((q: any, i: number) => h(CaseCard, { key: i, ...q }))),
      h('div', { className: 'aq-queue-worker' }, h(Icon, { name: 'running' }), h('span', { className: 'console-body' }, 'Worker: Case 4 · Describe · 00:34 of 00:45 deadline'), h('span', { className: 'console-micro aq-ink3' }, 'next: Case 5, then the Special One'),
        h('span', { className: 'aq-queue-sum console-data' }, 'Submitted 1 · ready 1 · question waiting 1'))),
    h(ShortcutBar, { keys: [{ k: '1–6', label: 'open case' }, { k: '⏎', label: 'open next needing an answer' }, { k: 'P', label: 'prioritise this case' }] }));
}

// ---------------------------------------------------------------------------
const stageBar = (c: any, speed = 1, extra?: any) => h('header', { className: 'aq-runbar aq-stagebar' }, h('div', { className: 'aq-runbar-wm' }, h(Wordmark, { size: 36 })),
  h('span', { className: 'stage-title' }, c.label), h(Badge, { tone: 'outline' }, c.urban === 'urban' ? 'Urban' : 'Non-urban'),
  h(Timer, { label: 'This panorama', used: c.run.used, budget: c.run.budget }), h(MultiplierChip, { value: c.run.multiplier }), extra || null,
  h('div', { className: 'aq-runbar-sys' }, h(SystemBadge, { kind: 'replay', speed })));

export function StageOpening() {
  const models = ROSTER.filter(m => m.id !== 'pvlib');
  return h(Density, { value: 'stage', theme: 'stage', className: 'aq-screen aq-stage-screen aq-opening', style: { width: 1920, height: 1080 } },
    h('div', { className: 'aq-opening-l' }, h(Wordmark, { size: 132 }), h('h1', { className: 'narrative-display' }, 'Where in the world could here be?'),
      h('p', { className: 'stage-body aq-ink2' }, 'One 360° photo. No metadata. Every claim traced back to pixels, every doubt left in view, every ruled-out place kept with its reason.'),
      h('div', { className: 'aq-opening-facts' }, h(Badge, { tone: 'outline', icon: 'gpu' }, 'one laptop · 16 GB GPU'), h(Badge, { tone: 'outline', icon: 'offline' }, 'no cloud APIs'), h(Badge, { tone: 'outline', icon: 'model' }, 'open weights only'))),
    h('div', { className: 'aq-opening-r' }, h('div', { className: 'stage-label aq-ink3' }, 'The local models, and what each one does'),
      h('ul', { className: 'aq-opening-models' }, models.map(m => h('li', { key: m.id }, h(Icon, { name: 'model', className: 'aq-c-model' }), h('div', null, h('div', { className: 'stage-body aq-strong' }, m.name), h('div', { className: 'stage-label aq-ink2' }, m.role)))),
        h('li', null, h(Icon, { name: 'solver', className: 'aq-c-solver' }), h('div', null, h('div', { className: 'stage-body aq-strong' }, 'Solver'), h('div', { className: 'stage-label aq-ink2' }, 'Our code: combines the evidence. Not a model.'))),
        h('li', null, h(Icon, { name: 'team', className: 'aq-c-team' }), h('div', null, h('div', { className: 'stage-body aq-strong' }, 'The team'), h('div', { className: 'stage-label aq-ink2' }, 'Answers the agent’s questions, when one is worth its cost.'))))));
}

export function StageRun() {
  return h(Density, { value: 'stage', theme: 'stage', className: 'aq-screen aq-stage-screen', style: { width: 1920, height: 1080 } },
    stageBar({ ...A, run: { ...A.run, used: 41, multiplier: 1 } }, 2),
    h(LeaderLines, { links: [['crop-t2', 't2']], className: 'aq-stage-run' },
      h('div', { className: 'aq-stage-focus' },
        h('div', { 'data-leader': 'crop-t2' }, h(ZoomCrop, { c: A, target: 't2', width: 1180, height: 470, fov: 9, note: 'full resolution · view 5 · yaw 212.5°' })),
        h(PanoramaStrip, { c: A, width: 1180, selected: 't2', crop: [42, -30], layers: { boxes: false, text: true, mask: false }, ruler: 'yaw' })),
      h('aside', { className: 'aq-stage-rail' },
        h(EvidenceCard, { e: ev(A, 'e2'), names: A.matrix.names, selected: true }),
        h(LanguageVote, { votes: A.language }),
        h(EstimateBars, { rows: A.regions.slice(0, 4).concat([A.regions[5]]), tone: 'model', title: 'Pixels alone (mini-PIGEON)' }))),
    h(CaptionBar, { headline: 'Reading signs', caption: 'A postcode in a format only Portugal uses: 4050 is central Porto', source: 'PP-OCRv6-medium', t: 41.2, speed: 2 }));
}

export function StageQuestion() {
  const c = { ...A, run: { ...A.run, used: 208, multiplier: 1.0 } };
  return h(Density, { value: 'stage', theme: 'stage', className: 'aq-screen aq-stage-screen', style: { width: 1920, height: 1080 } },
    stageBar(c, 1),
    h('div', { className: 'aq-stage-q' },
      h(QuestionCard, { q: { ...A.question, options: A.question.options.map((o: any) => ({ ...o, chips: [] })) }, evidence: A.evidence, brief: true }),
      h(MapView, { view: { lat: 41.1405, lng: -8.6150, span: 0.026 }, width: 860, height: 760, heat: A.heatTown, zones: A.zones, dimOthers: true, legend: false })),
    h(CaptionBar, { headline: 'Asking the team', caption: 'One answer is worth more here than its ×0.95 cost: expected gain +19%', actor: 'solver', source: 'Solver', t: 88 }));
}

export function StageFinal() {
  return h(Density, { value: 'stage', theme: 'stage', className: 'aq-screen aq-stage-screen', style: { width: 1920, height: 1080 } },
    stageBar(A, 1),
    h('div', { className: 'aq-stage-final' },
      h(MapView, { view: { lat: 41.14070, lng: -8.61315, span: 0.0056 }, width: 980, height: 760, final: { lat: A.answer.lat, lng: A.answer.lng, r: 22 }, legend: false }),
      h('div', { className: 'aq-stage-final-r' },
        h('div', { className: 'stage-label aq-ink3' }, 'Best estimate · latitude, longitude'),
        h('div', { className: 'stage-readout' }, fmtCoord(A.answer.lat, A.answer.lng)),
        h('div', { className: 'stage-data aq-c-solver' }, '± 22 m · reference_camera · ×0.95'),
        h(ScoreReadout, { expected: 12500, size: 'xl' }),
        h(AnswerSlots, { a: A.answer }))),
    h(CaptionBar, { headline: 'Pinpoint', caption: 'Best estimate: the Ribeira quay, within about 22 metres', actor: 'solver', source: 'Solver', t: 340 }));
}

// ---------------------------------------------------------------------------
export function ScreenSystemStates() {
  const failStages = [
    { id: 'describe', name: 'Describe', models: ['Qwen3.5-9B'], status: 'failed', dur: 8.2, gb: 7.4, note: 'Returned invalid JSON twice.', fallback: 'Gemma 4 12B, closed checklist only' },
    { id: 'measure', name: 'Measure', optional: true, models: ['EoMT-L', 'pvlib'], status: 'timed_out', dur: 20, gb: 1.1, note: 'No result in 20 s.', fallback: 'scene shares skipped; north stays unknown' },
    { id: 'geo', name: 'Pixel geolocation', models: ['PE-Core', 'mini-PIGEON', 'GeoCLIP'], status: 'done', dur: 9.6, gb: 1.7 },
  ];
  const lowCands = [{ id: 'x1', rank: 1, name: 'Centro region', level: 'region', v: 0.21, lo: 0.11, hi: 0.32, delta: 0, sup: 2, con: 1 }, { id: 'x2', rank: 2, name: 'Castilla y León (ES)', level: 'region', v: 0.18, lo: 0.08, hi: 0.3, delta: 0, sup: 2, con: 0 }, { id: 'x3', rank: 3, name: 'Norte region', level: 'region', v: 0.16, lo: 0.07, hi: 0.27, delta: 0, sup: 1, con: 0 }, { id: 'o', name: 'Other', level: 'area', v: 0.45, other: true }];
  const S = (title: string, note: string, body: any) => h('section', { className: 'aq-state' }, h('header', null, h('h2', { className: 'console-title' }, title), h('p', { className: 'console-body aq-ink2' }, note)), body);
  return h(Density, { value: 'console', className: 'aq-screen aq-states', style: { width: 1440 } },
    S('A stage failed or timed out', 'Every stage has a deadline and a fallback; the run still produces an answer. The row says which fallback ran.',
      h('div', { className: 'aq-col' }, h('ol', { className: 'aq-timeline-l' }, failStages.map(s => h(StageRow, { key: s.id, stage: s }))), h(Toast, { tone: 'contra', title: 'Measure timed out after 20 s', body: 'Skipped scene shares; the bearing ruler stays on camera yaw.', action: 'Show stage' }))),
    S('The VLM returned invalid JSON', 'The raw reply is kept in the log; one retry with a stricter prompt, then the fallback model. Nothing from the bad reply becomes evidence.',
      h('div', { className: 'aq-col' }, h('pre', { className: 'aq-raw console-data-sm' }, '{"granite_masonry": "yes", "azulejo": yes,\n "river_visible": "yes" ...'), h('div', { className: 'aq-row' }, h(Badge, { tone: 'contra', icon: 'failed' }, 'parse error at char 38'), h(Badge, { tone: 'neutral', icon: 'replay' }, 'retry 1 of 1 · failed'), h(Badge, { tone: 'model', icon: 'model' }, 'Gemma 4 12B · answered 9 of 11')))),
    S('Map tiles offline', 'Tiles are prefetched; if they fail, bundled outlines of PT, ES and FR with district borders take over — drawn on purpose, not as an error.',
      h(MapView, { view: { lat: 41.0, lng: -4.5, span: 15 }, width: 640, height: 300, offline: true, heat: A.heatCountry, candidates: [{ id: 'p', rank: 1, lat: 41.15, lng: -8.61, name: 'Porto' }] })),
    S('No text found', 'An empty reading is evidence too. It says so in words, and the language vote is absent rather than zero.',
      h('div', { className: 'aq-col' }, h(EvidenceCard, { e: B.evidence[0] }), h(EmptyState, { icon: 'language', title: 'No language vote', body: 'Nothing to read, so the three voters did not run. Country comes from scene and pixels.' }))),
    S('No candidate above the threshold', 'When nothing clears 0.30, the answer falls back to the cell that maximises expected score and the ring widens; the map stays at region level.',
      h('div', { className: 'aq-col' }, h(CandidateList, { candidates: lowCands, title: 'Candidates', caption: 'nothing above 0.30' }), h('div', { className: 'aq-row' }, h(UncertaintyRing, { r: null }), h('span', { className: 'console-body aq-ink2' }, 'Radius unknown until a stage bounds it; drawn open and large, never as a point.')))),
    S('Urban label unknown', 'The label picks the scoring curve. When nobody knows it, both curves and both expected scores stay on screen.',
      h('div', { className: 'aq-col' }, h(FilenameParse, { file: 'IMG_20260605_092457_00_064.jpg', urban: 'unknown', source: 'unknown', special: true }), h(ScoreCurve, { urban: 'unknown', band: [1500, 8400], expected: { urban: 2900, nonUrban: 11300 }, width: 640, height: 170 }))));
}

// ---------------------------------------------------------------------------
export function Concept() {
  return h(Density, { value: 'console', className: 'aq-screen aq-concept', style: { width: 1440 } },
    h('div', { className: 'aq-concept-top' },
      h('div', { className: 'aq-concept-wm' }, h(Wordmark, { size: 150 }), h('div', { className: 'console-micro aq-ink3' }, 'Newsreader outlines · the tittle is a point inside a broken uncertainty ring')),
      h('div', { className: 'aq-concept-text' }, h('h1', { className: 'narrative-title' }, 'A cartographer’s case file, read by an instrument'),
        h('p', { className: 'console-body' }, 'Aqui is the opposite of the chatbot that names a new town with full confidence. Everything on screen is a record: what a model saw, what follows from it, what the solver estimates — three registers that never blur. The base is quiet Atlantic ink (limestone on paper); colour is spent only on meaning: azulejo cobalt for models, Pombaline ochre for the solver, jacaranda for the team, roof-tile terracotta for every point spent. The memorable thing is the panorama strip and its bearing ruler, which turns from camera yaw to true north the moment the sun is found.'),
        h('p', { className: 'console-body aq-ink2' }, 'Three voices in type: Atkinson Hyperlegible Next for the interface (built to tell I, l and 1 apart — this app reads signs), Atkinson Hyperlegible Mono for every reading and number, Newsreader for the narrator: stage headlines, inference lines, the report.'))),
    h('div', { className: 'aq-moods' },
      h('figure', { className: 'aq-mood' }, h(PanoramaStrip, { c: B, width: 440, ruler: 'bearing', crop: [40, -40], layers: { sun: true, skyline: true, boxes: false, text: false, mask: false }, label: false }), h('figcaption', { className: 'console-body' }, h('b', null, 'The ruler. '), 'North arrives with the sun, with its error on the ruler.')),
      h('figure', { className: 'aq-mood' }, h(Density, { value: 'console', theme: 'light', className: 'aq-mood-paper' }, h('div', { className: 'aq-mood-pad' }, h('div', { className: 'aq-row', style: { justifyContent: 'space-between' } }, h('span', { className: 'narrative-title' }, 'Ruled out, and why'), h(Stamp, { kind: 'ruled-out' })), h(RuledOutRow, { r: A.ruledOut[0] }), h(EvidenceCard, { e: ev(A, 'e2'), names: A.matrix.names, compact: true }))), h('figcaption', { className: 'console-body' }, h('b', null, 'The case file. '), 'Ruled-out places stay, struck through, with the reason.')),
      h('figure', { className: 'aq-mood' }, h(Density, { value: 'stage', theme: 'stage', className: 'aq-mood-stage' }, h('div', { style: { zoom: 0.23 } }, h(CaptionBar, { headline: 'Reading signs', caption: 'A postcode in a format only Portugal uses', source: 'PP-OCRv6-medium', t: 41.2, speed: 2 }), h(ZoomCrop, { c: A, target: 't2', width: 1900, height: 700, fov: 9 }))), h('figcaption', { className: 'console-body' }, h('b', null, 'The room. '), 'One focus, one plain sentence, from the back row.'))));
}

// ---------------------------------------------------------------------------
// Motion key frames: each frame is the real component at a moment of a real log event.
const Frame = ({ n, t, title, children, notes }: any) => h('figure', { className: 'aq-frame' }, h('div', { className: 'aq-frame-h' }, h('span', { className: 'console-data-sm aq-ink3' }, `F${n}`), h('span', { className: 'console-label' }, title), h('span', { className: 'console-data-sm aq-ink3 aq-frame-t' }, t)), h('div', { className: 'aq-frame-b' }, children), h('figcaption', { className: 'console-micro aq-ink2' }, notes));
const Storyboard = ({ beat, event, frames, foot }: any) => h(Density, { value: 'console', className: 'aq-screen aq-story', style: { width: 1440 } },
  h('header', { className: 'aq-story-h' }, h('h1', { className: 'narrative-title' }, beat), h('span', { className: 'console-data aq-ink2' }, event)), h('div', { className: 'aq-frames' }, frames), foot ? h('p', { className: 'console-micro aq-ink3' }, foot) : null);

export function MotionDetect() {
  const all = A.detections.map((d: any) => d.id), kept = A.detections.filter((d: any) => d.kept).map((d: any) => d.id);
  const W = 320;
  return h(Storyboard, { beat: 'Beat 3 · Detect', event: 'evidence.added (detect) ×20 → evidence.added (SAM 3 verdicts)', frames: [
    h(Frame, { key: 1, n: 1, t: '27.3 s', title: 'Boxes proposed', notes: 'Each box enters with its own event: corner brackets scale 0.92 → 1 and fade in, dur-quick 180 ms, ease-enter; stagger dur-stagger 40 ms, capped at 480 ms.' }, h(PanoramaStrip, { c: A, width: W, ruler: false, layers: { text: false, mask: false }, label: false, visibleBoxes: all.slice(0, 5) })),
    h(Frame, { key: 2, n: 2, t: '27.8 s', title: 'All 20 in view', notes: 'Labels appear only after the box settles (dur-quick). No pulsing while waiting for SAM 3 — the stage row’s real clock carries the wait.' }, h(PanoramaStrip, { c: A, width: W, ruler: false, layers: { text: false, mask: false }, label: false })),
    h(Frame, { key: 3, n: 3, t: '33.5 s', title: 'SAM 3 rejects 3', notes: 'Rejected boxes switch to dashed and get a strike (dur-quick), then fade to opacity-ghost over dur-standard 280 ms, ease-exit. They stay, struck, until the layer is toggled off.' }, h(PanoramaStrip, { c: A, width: W, ruler: false, layers: { text: false, mask: false }, label: true, fadedBoxes: [] })),
    h(Frame, { key: 4, n: 4, t: '33.8 s', title: 'Settled', notes: 'The evidence card “17 kept, 3 rejected” lifts into the feed (dur-standard, ease-enter). Reduced motion: each step is a 180 ms cross-fade.' }, h(PanoramaStrip, { c: A, width: W, ruler: false, layers: { text: false, mask: false }, label: false, showRejected: true })),
  ], foot: 'Every frame corresponds to an event in the log; replay at 2× or 5× halves or fifths the waits between events, never the durations above.' });
}

export function MotionFusion() {
  const before = A.candidatesBefore.map((c: any) => ({ ...c, v: c.v * 0.35, lo: undefined, hi: undefined, delta: 0 }));
  return h(Storyboard, { beat: 'Beat 8 · Fusion', event: 'candidates.updated (fusion) at 86.3 s', frames: [
    h(Frame, { key: 1, n: 1, t: '86.1 s', title: 'Evidence sends weight', notes: 'Each supporting card ticks its ▲ chips in sequence (stagger 40 ms) while bars grow: dur-deliberate 520 ms, ease-move.' }, h('div', { className: 'aq-col' }, h(EvidenceCard, { e: ev(A, 'e2'), names: A.matrix.names, compact: true }), before.slice(0, 3).map((c: any) => h(CandidateRow, { key: c.id, c, max: 0.7, showDelta: false })))),
    h(Frame, { key: 2, n: 2, t: '86.2 s', title: 'Correlated sources merge', notes: 'Neighbours and regions slide together under one bracket (dur-standard); the bracket’s cap badge appears last. One voice, one weight.' }, h(CorrelationBracket, { label: 'One voice: PE-Core', cap: 0.35 }, h(EvidenceCard, { e: ev(A, 'e12'), names: A.matrix.names, compact: true }), h(EvidenceCard, { e: ev(A, 'e13'), names: A.matrix.names, compact: true }))),
    h(Frame, { key: 3, n: 3, t: '86.2 s', title: 'A contradiction pulses', notes: 'The two sources outline in contra twice (2 × dur-quick, no loop); Alfama’s range widens over dur-deliberate. Confidence moves both ways.' }, h('div', { className: 'aq-col' }, h(EvidenceCard, { e: ev(A, 'e15'), names: A.matrix.names, compact: true }), h(CandidateRow, { c: A.candidatesBefore[3], max: 0.7 }))),
    h(Frame, { key: 4, n: 4, t: '86.3 s', title: 'Ruled out, ghosted', notes: 'Galicia strikes through (dur-quick), then fades to opacity-ghost (dur-standard, ease-exit) with its reason. It never leaves the list.' }, h('div', { className: 'aq-col' }, A.candidatesBefore.slice(0, 3).map((c: any) => h(CandidateRow, { key: c.id, c, max: 0.7 })), h(RuledOutRow, { r: A.ruledOut[0] }))),
  ] });
}

export function MotionAsk() {
  const zonesA = A.zones.map((z: any) => ({ ...z, chosen: z.key === 'A', dim: z.key !== 'A' }));
  const W = 320, H = 210;
  return h(Storyboard, { beat: 'Beat 10 · Ask', event: 'question.asked 88.0 s → question.answered 212.0 s (or question.skipped)', frames: [
    h(Frame, { key: 1, n: 1, t: '88.0 s', title: 'Zones draw', notes: 'Outlines draw on A → D (stroke-dashoffset, dur-standard each, stagger 40 ms); hatch fades in after. Heat dims to opacity-dim.' }, h(MapView, { view: A.viewTown, width: W, height: H, heat: A.heatTown, zones: A.zones.slice(0, 1), legend: false, labels: false, scale: false, dimOthers: true })),
    h(Frame, { key: 2, n: 2, t: '88.4 s', title: 'Question open', notes: 'The card rises (dur-standard, ease-enter). The gain bar fills to +19% once (dur-deliberate). Nothing else moves while the team decides.' }, h(MapView, { view: A.viewTown, width: W, height: H, heat: A.heatTown, zones: A.zones, legend: false, labels: false, scale: false, dimOthers: true })),
    h(Frame, { key: 3, n: 3, t: '212.0 s', title: 'Answered A', notes: 'Chosen zone thickens, others dim (dur-quick). Multiplier ticks ×1.00 → ×0.95 in place (dur-deliberate, ease-move); bars resize after.' }, h('div', { className: 'aq-col' }, h(MapView, { view: A.viewTown, width: W, height: 150, heat: A.heatTown, zones: zonesA, legend: false, labels: false, scale: false }), h('div', { className: 'aq-row' }, h(MultiplierChip, { value: 0.95 }), h(Badge, { tone: 'team', icon: 'team' }, 'Answered A')))),
    h(Frame, { key: 4, n: 4, t: '188.0 s · Case 4', title: 'Or: skipped', notes: 'A skip moves nothing. The card collapses to a dashed receipt (dur-standard) reading “Skipped · free · nothing changed”. No tick, no bar motion.' }, h('div', { className: 'aq-col' }, h(MapView, { view: B.view, width: W, height: 150, heat: B.heat, zones: B.zones, legend: false, labels: false, scale: false }), h('div', { className: 'aq-row' }, h(MultiplierChip, { value: 1.0 }), h(Badge, { tone: 'outline', icon: 'skip' }, 'Skipped · nothing changed')))),
  ] });
}

export function MotionExactSpot() {
  return h(Storyboard, { beat: 'Beat 11 · Exact spot', event: 'stage.started (spot) 309.0 s → evidence.added (matches) 331.5 s → output.produced 340.0 s', frames: [
    h(Frame, { key: 1, n: 1, t: '309.0 s', title: 'Reference slides in', notes: 'The reference photo slides in beside the query view from the right (dur-standard, ease-enter); its map square highlights.' }, h(MatchView, { c: A, width: 320, height: 120, lines: 0, showRejected: false })),
    h(Frame, { key: 2, n: 2, t: '320.0 s', title: 'Matches draw', notes: 'Lines draw left to right in batches as LightGlue reports them (stagger 40 ms, cap 480 ms per batch). Rejected matches appear dashed, then fade.' }, h(MatchView, { c: A, width: 320, height: 120, lines: 12 })),
    h(Frame, { key: 3, n: 3, t: '331.5 s', title: 'Inliers counted', notes: 'The inlier count climbs to 412 over dur-deliberate — a count-up of a known number, not a progress bar.' }, h(MatchView, { c: A, width: 320, height: 120, lines: 36 })),
    h(Frame, { key: 4, n: 4, t: '340.0 s', title: 'Ring contracts', notes: 'The ring contracts from ± 180 m to ± 22 m (dur-deliberate, ease-move) and stops there — never tighter than the remaining offset.' }, h(MapView, { view: A.viewSpot, width: 320, height: 150, final: { lat: A.answer.lat, lng: A.answer.lng, r: 22 }, legend: false, labels: true, scale: true })),
  ] });
}

export function MotionPinpoint() {
  return h(Storyboard, { beat: 'Beat 12 · Pinpoint', event: 'output.produced 340.0 s', frames: [
    h(Frame, { key: 1, n: 1, t: '340.0 s', title: 'The mark lands', notes: 'The surveyor’s mark drops 12 px and settles with ease-spring over dur-deliberate — the only spring in the system.' }, h(MapView, { view: { lat: 41.14081, lng: -8.61315, span: 0.004 }, width: 320, height: 170, final: { lat: A.answer.lat, lng: A.answer.lng, r: null }, legend: false, labels: false })),
    h(Frame, { key: 2, n: 2, t: '340.2 s', title: 'Ring settles', notes: 'The ring settles at the final radius (dur-deliberate); its label “± 22 m” fades in after (dur-quick).' }, h(MapView, { view: { lat: 41.14081, lng: -8.61315, span: 0.004 }, width: 320, height: 170, final: { lat: A.answer.lat, lng: A.answer.lng, r: 22 }, legend: false })),
    h(Frame, { key: 3, n: 3, t: '340.4 s', title: 'Slots fill', notes: 'The ten rank-weight bars fill left to right, stagger 40 ms (400 ms total), each at its weight 1.00 → 0.63.' }, h(AnswerSlots, { a: A.answer })),
    h(Frame, { key: 4, n: 4, t: '340.9 s', title: 'Expected score counts up', notes: 'Counts 0 → ≈ 12,500 over dur-cinematic 1400 ms, ease-move, always labelled “estimate”. Reduced motion: the final number appears.' }, h(ScoreReadout, { expected: 12500, range: [10900, 13400] })),
  ] });
}
