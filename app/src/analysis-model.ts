import { arr, finite, record, str, strings, type Evidence, type Stage } from './model';
import { plainLabel } from './focus-model';

export const countryNames: Record<string, string> = { PT: 'Portugal', ES: 'Spain', FR: 'France' };
export const readableFeature = (text: string) => text.replaceAll('_', ' ').replace(/^./, first => first.toUpperCase());
export const isReading = (kind: string) => ['text', 'ocr_text', 'postcode', 'phone', 'road_number', 'plate', 'name', 'language'].includes(kind);
export function featuresFor(e: Evidence) {
  const supplied = arr(e.payload.features).map(record).filter(f => str(f.key) && str(f.value));
  const entries = supplied.length ? supplied : Object.entries(record(e.payload.answers)).filter(([, v]) => typeof v === 'string').map(([key, value]) => record({ key, value }));
  return entries.map(f => ({ key: str(f.key), label: str(f.label, readableFeature(str(f.key))),
    value: str(f.value), description: str(f.description) || ({ not_visible: 'Not visible', invalid: 'Unclear', other: 'Other appearance' }[str(f.value)] ?? readableFeature(str(f.value))),
    unknown: ['not_visible', 'invalid', 'other'].includes(str(f.value)) })).sort((a, b) => Number(a.unknown) - Number(b.unknown));
}
export function findingTitle(e: Evidence) {
  if (e.kind === 'vlm_checklist') return `Scene view${e.box ? ` · ${Math.round(e.box.yaw)}°` : str(e.payload.view) ? ` · ${str(e.payload.view)}` : ''}`;
  if (e.kind === 'landmark_hypothesis') return `Possible landmark · ${plainLabel(e.obs, 'Unnamed')}`;
  return plainLabel(e.obs, 'Observation');
}
export function explanationFor(e: Evidence): string | undefined {
  if (e.inference) return e.inference;
  const p = e.payload;
  const places = (codes: unknown) => strings(codes).map(code => countryNames[code] ?? code).join(' or ');
  if (e.kind === 'vlm_checklist') {
    const features = featuresFor(e).filter(f => !f.unknown);
    return features.length ? `Observed ${features.map(f => `${f.label.toLowerCase()}: ${f.description.toLowerCase()}`).join('; ')}. These scene clues will be checked against the other views and reference photos.` : 'No clear scene feature in this view. Unseen features add no location evidence.';
  }
  if (e.kind === 'vlm_summary') {
    const hints = arr(p.hints).map(record).filter(h => h.majority === true && !h.conflict);
    return hints.length ? hints.map(h => `${readableFeature(str(h.key))}: ${readableFeature(str(h.value)).toLowerCase()} supports ${strings(h.regions).join(' or ') || places(h.countries)}${finite(h.support) !== null ? ` across ${h.support} view${h.support === 1 ? '' : 's'}` : ''}.`).join(' ') : 'The inspected views provide no consistent geographic clue yet.';
  }
  if (isReading(e.kind) && places(p.countries)) return `The reading “${str(p.text, str(p.value))}” is consistent with ${places(p.countries)}${strings(p.regions).length ? `; the parsed clue points toward ${strings(p.regions).join(' or ')}` : ''}.`;
  if (['knn', 'region_head', 'geoclip'].includes(e.kind)) {
    const rows = arr(p.neighbours ?? p.regions ?? p.candidates).map(record);
    const top = [...rows].sort((a, b) => (finite(b.weight) ?? 0) - (finite(a.weight) ?? 0))[0];
    return top ? `The ${e.kind === 'knn' ? 'similar reference photos' : e.kind === 'region_head' ? 'region model' : 'geographic image model'} point toward ${plainLabel(str(top.label, str(top.name)), 'an area estimate')}. This is a provisional lead for the solver to compare with the other clues.` : 'This model returned no geographic lead.';
  }
  if (e.kind === 'landmark_hypothesis') return `“${str(p.name)}” is a landmark hypothesis. The name still needs a location lookup and independent verification.`;
  if (e.kind === 'name_lookups') {
    const rows = arr(p.clues).map(record).filter(r => str(r.best));
    return rows.length ? rows.map(r => `“${str(r.text)}” matches ${str(r.best)}${finite(r.candidates) !== null && Number(r.candidates) > 1 ? ` among ${r.candidates} possible places` : ''}.`).join(' ') : 'No matching place name or postcode was resolved.';
  }
  if (e.kind === 'name_match') return `The name “${str(p.query)}” matches ${arr(p.matches).length} indexed place${arr(p.matches).length === 1 ? '' : 's'}. Their points mark places, with camera positions still to be determined.`;
  if (e.kind === 'contradiction') return str(p.note, 'The clues conflict; the search area needs to stay broad.');
  if (['fusion', 'landmark_gallery', 'match', 'region', 'geo_sample', 'scene_shares', 'sun'].includes(e.kind)) return e.obs;
  return undefined;
}
export const analysisTitle = (e: Evidence) => ({ vlm_checklist: 'Scene clues', vlm_summary: 'Clues across views', knn: 'Reference photos', region_head: 'Region estimate', geoclip: 'Geographic estimate', name_lookups: 'Names and places', name_match: 'Names and places', fusion: 'Evidence combined', landmark_hypothesis: 'Possible landmark', landmark_gallery: 'Landmarks compared', match: 'Geometric check', contradiction: 'Conflicting clues' }[e.kind] ?? (isReading(e.kind) ? 'What the reading suggests' : 'Observation explained'));
export function stageActivity(stage: Stage) {
  return stage.progress?.message || ({ prepare: 'Preparing views from the panorama.', views: 'Preparing views from the panorama.', detect: 'Detecting objects and checking their outlines.', read: 'Reading signs, postcodes and place names.', describe: 'Checking architecture, road details and vegetation.', measure: 'Measuring the visible scene and sun direction.', retrieve: 'Comparing the panorama with reference photographs.', geo: 'Estimating regions from the panorama.', geoclip: 'Comparing geographic image estimates.', landmarks: 'Checking possible landmarks against reference photos.', names: 'Resolving readings and scene clues to places.', fuse: 'Weighing the clues and comparing possible locations.', fusion: 'Weighing the clues and comparing possible locations.', ask: 'Checking whether a question would narrow the search.', spot: 'Verifying the most promising location.' }[stage.id] ?? `Running ${stage.name.toLowerCase()}.`);
}
