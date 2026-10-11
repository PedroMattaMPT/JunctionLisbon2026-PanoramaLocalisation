import { arr, record, str, finite, nonnegative, positive, strings, angularBox, point, snapshot, extentOf, type Box, type CaseRecord, type RunEvent, type Evidence, type Candidate, type Category, type Output, type Question } from './model';
import { modelName, stageName, roleText, score, MAX_SCORE } from './format';
import { captionFor } from './captions';

export function emptyCase(): CaseRecord {
  return { id: '', label: 'New case', file: '', urban: 'unknown', urbanSource: 'unknown', special: false, events: [], stages: [], evidence: [], candidates: [], outputs: [], questions: [], ruledOut: [], detections: [], texts: [], language: null, shares: null, yawToBearing: null, regions: [], neighbours: [], matches: [], groups: [], matrix: { candidates: [], names: {} }, penalty: { answered_questions: 0, cues: 0, conversions: 0, multiplier: 1 }, multiplierHistory: [], finished: false, submitted: false, run: { used: 0, budget: 480, session: 0, sessionBudget: 3600, gpu: null, gpuMax: 16, multiplier: 1, expected: null } };
}
export function parseFilename(file: string) {
  const m = /^IMG_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_00_(\d+)\.jpe?g$/i.exec(file);
  if (!m) return {};
  const date = `${m[1]}-${m[2]}-${m[3]}`, time = `${m[4]}:${m[5]}:${m[6]}`;
  const parsed = new Date(`${date}T${time}Z`);
  if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 19) !== `${date}T${time}`) return {};
  return { date, time, shot: Number(m[7]) };
}
const category = (value: unknown): Category => value === 'urban' || value === 'non-urban' ? value : 'unknown';
const TEXT_KINDS = ['text', 'ocr_text', 'postcode', 'phone', 'road_number'];
/** panoloc.pipeline logs (versions.pipeline) put yaw 0 at the image centre; this app puts it at the left edge. */
const pipelineYaw = (p: Record<string, unknown>) => typeof record(p.versions).pipeline === 'string';
const shifted = (box: Box | undefined, shift = 0): Box | undefined => box && shift ? { ...box, yaw: ((box.yaw + shift) % 360 + 360) % 360 } : box;
/** Scope chips: logged strings, or a panoloc.questions box {south, west, north, east}. */
function scopeText(value: unknown): string[] {
  if (Array.isArray(value)) return strings(value);
  const s = record(value), [south, west, north, east] = ['south', 'west', 'north', 'east'].map(k => finite(s[k]));
  if (south !== null && west !== null && north !== null && east !== null) return [`Area ${south.toFixed(2)}…${north.toFixed(2)}° lat, ${west.toFixed(2)}…${east.toFixed(2)}° lng`];
  return [str(s.name, str(s.zone_name))].filter(Boolean);
}
function shares(value: unknown) {
  const entries = Array.isArray(value) ? arr(value).map(record) : Object.entries(record(value)).map(([id, v]) => ({ id, v }));
  return entries.filter(p => str(p.id) && finite(p.v) !== null).map(p => ({ id: str(p.id), v: p.v as number }));
}
function observation(p: Record<string, unknown>, e: RunEvent): string {
  if (str(p.observation)) return str(p.observation);
  const kind = str(p.kind);
  if (['text', 'postcode', 'phone', 'road_number'].includes(kind)) return str(p.text, 'No text logged');
  if (kind === 'checklist') return `${str(p.item, 'Item not logged')}: ${p.answer === 'not_visible' ? "can't tell" : str(p.answer, 'unknown')}`;
  if (kind === 'landmark_hypothesis') return str(p.name, 'Hypothesis not named');
  if (kind === 'object') return `${str(p.label, 'Object')}${p.kept === false ? ' · rejected' : p.kept === true ? ' · kept' : ' · verdict not logged'}`;
  if (kind === 'language' && p.votes !== undefined) return shares(p.votes).map(v => `${v.id} ${v.v.toFixed(2)}`).join(' · ') || 'No language vote';
  // panoloc OCR items (ocr_text, name, plate, language ...): the verbatim reading, then the parsed value.
  if (str(p.text) || str(p.value)) return [str(p.text), str(p.value) && p.value !== p.text ? `→ ${str(p.value)}` : ''].filter(Boolean).join(' ');
  return captionFor(e).caption;
}
function candidates(value: unknown, previous: Candidate[]): Candidate[] {
  const input = arr(value).map(record).sort((a, b) => (finite(b.weight) ?? 0) - (finite(a.weight) ?? 0));
  const total = input.reduce((sum, c) => sum + Math.max(0, finite(c.weight) ?? 0), 0);
  return input.map((p, i) => {
    const id = str(p.candidate_id, str(p.source, `candidate-${i + 1}`));
    const weight = Math.max(0, finite(p.weight) ?? 0), v = total > 0 ? weight / total : null;
    const prev = previous.find(c => c.id === id); const supports = strings(p.supports), contradicts = strings(p.contradicts);
    const accuracy = nonnegative(p.accuracy_m), extent = nonnegative(p.extent_m);
    return { id, rank: i + 1, name: str(p.name, str(p.label, id)), level: str(p.level, roleText(str(p.role))), ...point(p), role: str(p.role, 'unknown'), source: str(p.source, 'not logged'), weight, v,
      lo: finite(p.lo) ?? undefined, hi: finite(p.hi) ?? undefined, delta: v !== null && prev?.v != null ? v - prev.v : null,
      sup: Array.isArray(p.supports) ? supports.length : undefined, con: Array.isArray(p.contradicts) ? contradicts.length : undefined,
      r: accuracy === null && extent === null ? null : (accuracy ?? 0) + (extent ?? 0), supports, contradicts, evidence: strings(p.evidence), group: str(p.group) || undefined, details: record(p.details) };
  });
}
/** One pure event application. A record belongs to exactly one run. */
export function reduceEvent(previous: CaseRecord, e: RunEvent): CaseRecord {
  if (previous.events.some(p => p.seq === e.seq) || previous.id && previous.id !== e.run_id) return previous;
  const p = e.payload, penalty = snapshot(p.penalty);
  let c: CaseRecord = { ...previous, id: e.run_id, file: e.panorama, events: [...previous.events, e], run: { ...previous.run, used: e.t } };
  if (penalty) c = { ...c, penalty, run: { ...c.run, multiplier: penalty.multiplier }, multiplierHistory: penalty.multiplier !== previous.penalty.multiplier ? [...c.multiplierHistory, { t: e.t, m: penalty.multiplier, what: captionFor(e).headline }] : c.multiplierHistory };
  if (e.type === 'run.started') c = { ...c, file: str(p.panorama, e.panorama), ...parseFilename(str(p.panorama, e.panorama)), label: 'Case', urban: category(record(p.category).value), urbanSource: str(record(p.category).source, 'unknown'), special: p.special_one === true, scene: str(p.fixture_scene) || undefined, multiplierHistory: [{ t: e.t, m: c.penalty.multiplier, what: 'Run started' }], yawShift: pipelineYaw(p) ? 180 : 0 };
  if (e.type.startsWith('stage.')) {
    const id = str(e.stage, 'unnamed'); const existing = c.stages.find(s => s.id === id);
    const status = ({ started: 'running', finished: 'done', skipped: 'skipped', failed: 'failed', timed_out: 'timed_out' } as Record<string, string>)[e.type.split('.')[1]];
    if (status) {
      const stage = { ...(existing ?? { id, name: stageName(id), models: [], started: e.t, deadline: null, optional: false, dur: null }), models: e.model ? [modelName(e.model)] : existing?.models ?? ['Solver'],
        status, seq: e.seq, ...(e.type === 'stage.started' ? { started: e.t, dur: 0, deadline: finite(p.deadline_s), optional: p.optional === true } : { dur: finite(p.elapsed_s) }),
        note: str(p.message, str(p.reason)) || undefined, fallback: str(p.fallback) || undefined };
      c.stages = existing ? c.stages.map(s => s.id === id ? stage : s) : [...c.stages, stage];
      if (id === 'views' && status === 'done') { c.viewCount = finite(p.views) ?? undefined; c.photographerMask = finite(p.photographer_masked) ?? undefined; }
    }
    if (e.type === 'stage.progress' && existing?.status === 'running') {
      const completed = nonnegative(p.completed), total = positive(p.total);
      c.stages = c.stages.map(s => s.id !== id ? s : { ...s, progress: {
        message: str(p.message), completed: completed !== null && total !== null && completed <= total ? completed : null,
        total, view: str(p.view) || undefined, box: shifted(angularBox(p.box), c.yawShift),
      } });
    }
  }
  if (e.type === 'evidence.added') {
    const id = str(p.evidence_id, `seq-${e.seq}`), kind = str(p.kind, 'unknown'), box = shifted(angularBox(p.box), c.yawShift);
    const ev: Evidence = { id, kind, stage: stageName(e.stage), actor: e.actor === 'agent' || e.actor === 'solver' ? 'solver' : e.actor === 'team' ? 'team' : 'model', model: e.actor === 'agent' ? 'Solver' : modelName(e.model), t: e.t, seq: e.seq, obs: observation(p, e), inference: str(p.inference) || undefined, conf: finite(p.confidence), box, ref: box ? id : undefined, notVisible: p.answer === 'not_visible', group: str(p.group) || undefined, pol: Object.fromEntries(Object.entries(record(p.polarity)).filter(([, v]) => finite(v) !== null)) as Record<string, number>, payload: p };
    c.evidence = [...c.evidence.filter(x => x.id !== id), ev];
    if (kind === 'object' && box) c.detections = [...c.detections.filter(x => x.id !== id), { ...box, id, label: str(p.label, 'Object'), score: finite(p.score), kept: typeof p.kept === 'boolean' ? p.kept : undefined }];
    // ocr_text is the pipeline's sign reading; its parsed items (postcode, phone...) repeat the sign's box via ocr_evidence_id.
    if (TEXT_KINDS.includes(kind) && box && !str(p.ocr_evidence_id)) c.texts = [...c.texts.filter(x => x.id !== id), { ...box, id, text: str(p.text), conf: finite(p.confidence) }];
    if (kind === 'language' && p.votes !== undefined) c.language = shares(p.votes).filter(v => ['pt', 'gl', 'es', 'ca', 'eu', 'fr'].includes(v.id));
    if (kind === 'scene_shares') { c.shares = shares(p.shares).filter(v => ['sky', 'building', 'grass', 'tree', 'road', 'water', 'ground'].includes(v.id)); c.masked = finite(p.masked) ?? undefined; c.maskUrl = str(p.mask_url) || undefined; c.maskPalette = Object.keys(record(p.mask_palette)).length ? record(p.mask_palette) : undefined; }
    if (kind === 'sun') {
      const azimuth = finite(p.azimuth), elevation = finite(p.elevation);
      if (azimuth !== null && elevation !== null) c.sun = { azimuth, elevation, yaw: finite(p.yaw) ?? undefined };
      c.yawToBearing = finite(p.bearing_of_yaw0); c.yawToBearingErr = finite(p.err_deg) ?? undefined;
    }
    if (kind === 'region') c.regions = arr(p.regions).map(record).filter(r => str(r.name) && finite(r.v) !== null);
    if (kind === 'views') { c.viewCount = finite(p.count) ?? undefined; c.photographerMask = finite(p.photographer_masked) ?? undefined; }
  }
  if (e.type === 'candidates.updated' && e.actor !== 'model') {
    c.candidates = candidates(p.candidates, c.candidates);
    c.ruledOut = [...c.ruledOut, ...arr(p.ruled_out).map(record)].filter((r, i, all) => all.findIndex(x => x.name === r.name) === i);
    c.questions = c.questions.map(q => q.status === 'answered' && !q.after ? { ...q, after: c.candidates } : q);
  }
  if (e.type === 'question.asked') {
    const options = arr(p.options).slice(0, 4).map((v, i) => {
      const o = record(v); const pp = Array.isArray(o.point) ? point({ lat: o.point[0], lng: o.point[1] }) : point(o.point);
      // panoloc.questions marks "None of these" / "Outside" / "Elsewhere" with complement: true.
      return { id: str(o.id, 'abcd'[i]), key: 'ABCD'[i], label: str(o.label, 'Option not labelled'), reason: str(o.reason, str(o.detail, 'Reason not logged')), chips: strings(o.evidence), point: pp ? [pp.lat, pp.lng] as [number, number] : undefined, zone: Object.keys(record(o.zone)).length ? record(o.zone) : undefined, region: str(o.region) || undefined, radius: positive(o.radius_m) ?? undefined, extent: extentOf(o.extent), none: o.none === true || o.complement === true, links: Object.fromEntries(Object.entries(record(o.links)).filter(([, v]) => typeof v === 'string')) as Record<string, string> };
    });
    const gain = record(p.expected_gain); // panoloc.pipeline nests the gate under expected_gain
    const q: Question = { id: str(p.question_id), text: str(p.text, 'Question text not logged'), kind: str(p.kind), options, scope: scopeText(p.scope), gain: finite(p.gain) ?? finite(gain.gain), breakEven: finite(p.break_even) ?? finite(gain.break_even) ?? 1 / 0.95 - 1, cost: 0.95, wordedBy: str(p.worded_by) || undefined, status: 'open', askedAt: e.t, before: c.candidates, multiplierBefore: c.penalty.multiplier };
    c.questions = [...c.questions.filter(q0 => q0.id !== q.id), q];
  }
  if (e.type === 'question.answered' || e.type === 'question.skipped') {
    const skipped = e.type === 'question.skipped';
    c.questions = c.questions.map(q => q.id !== p.question_id ? q : { ...q, status: skipped ? 'skipped' : 'answered', answer: skipped ? undefined : q.options.find(o => o.id === p.option_id)?.key, resolvedAt: e.t, multiplierAfter: c.penalty.multiplier, ...(skipped ? { after: q.before } : {}) });
  }
  if (e.type === 'output.produced' && e.actor !== 'model') {
    const coords = arr(p.coordinates).map(record).flatMap((v, i) => { const pt = point(v); return pt ? [{ ...pt, rank: finite(v.rank) ?? i + 1 }] : []; });
    if (coords.length && penalty) {
      const cat = category(record(p.category).value), radius = nonnegative(p.position_uncertainty_m), best = c.candidates[0];
      const output: Output = { id: str(p.output_id, `seq-${e.seq}`), t: e.t, seq: e.seq, ...coords[0], role: str(p.source_role, 'not logged'), method: str(p.output_method, 'not logged'), r: radius, rSource: str(p.uncertainty_source, 'unknown'), penalty: { ...penalty }, multiplier: penalty.multiplier, category: cat, special: p.special_one === true, ...score(radius, cat, penalty.multiplier, coords.length), max: MAX_SCORE, why: str(p.note, 'Choice reason not logged'), sources: strings(p.sources), mostLikely: best?.lat !== undefined && best.lng !== undefined ? best.lat === coords[0].lat && best.lng === coords[0].lng : undefined, coordinates: coords, raw: p };
      c.outputs = [...c.outputs, output]; c.answer = output;
    }
  }
  if (e.type === 'run.finished') c.finished = true;
  if (e.type === 'run.submitted') c.submitted = true;
  // Rebuild derived links from logged identifiers only.
  c.evidence = c.evidence.map(ev => ({ ...ev, pol: { ...ev.pol, ...Object.fromEntries(c.candidates.flatMap(candidate => candidate.supports.includes(ev.id) ? [[candidate.id, 1]] : candidate.contradicts.includes(ev.id) ? [[candidate.id, -1]] : [])) } }));
  c.matrix = { candidates: c.candidates.map(v => v.id), names: Object.fromEntries(c.candidates.map(v => [v.id, v.name])) };
  c.groups = [...new Set(c.evidence.map(v => v.group).filter((v): v is string => !!v))].map(id => ({ id, label: `One voice: ${id}`, members: c.evidence.filter(v => v.group === id).map(v => v.id), cap: finite(c.evidence.find(v => v.group === id)?.payload.group_cap) ?? undefined }));
  c.neighbours = c.evidence.filter(ev => ev.kind === 'neighbour' || ev.kind === 'landmark_photo');
  c.matches = c.evidence.filter(ev => ev.kind === 'match');
  c.question = c.questions.find(q => q.status === 'open');
  c.stages = c.stages.map(s => s.status === 'running' ? { ...s, dur: Math.max(0, e.t - s.started) } : s);
  const estimate = score(c.answer?.r ?? c.candidates[0]?.r ?? null, c.urban, c.penalty.multiplier, c.answer?.coordinates.length ?? 10);
  c.run = { ...c.run, ...estimate };
  return c;
}
export function reduce(events: readonly RunEvent[]): CaseRecord {
  return [...events].sort((a, b) => a.seq - b.seq).reduce(reduceEvent, emptyCase());
}
