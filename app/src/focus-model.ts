import type { Candidate, CaseRecord, Option, Output, Question } from './model';
import { distance, haversine } from './format';
import { questionBounds } from './bounds';

// Presentation only: the full record and verbatim question/option wording stay untouched.
const internalId = /\b(?:wikidata|geonames|regionhead|geoclip|osv5m|commons|fallback):[^\s,;)]+/gi;
export function plainLabel(value: string, fallback = 'Area estimate'): string {
  if (/^(?:wikidata|geonames|regionhead|geoclip|osv5m|commons|fallback):/i.test(value)) return fallback;
  const label = value.replace(/^GeoCLIP estimate in\s+/i, '').replace(internalId, '')
    .replace(/(?:GeoCLIP stock gallery point|OSV-5M photo|PE-Core neighbour)\s*\d*/gi, '')
    .replace(/\b(coarse_candidate|geographic_cell|reference_camera)\b/g, word => ({ coarse_candidate: 'Rough area estimate', geographic_cell: 'Narrowed by your answers', reference_camera: 'Matched to a reference photo' })[word]!)
    .replace(/\bSolver\b/g, 'Agent').replace(/\s+/g, ' ').trim();
  return label && !/^(?:not logged|unknown|\([^)]*\))$/i.test(label) ? label : fallback;
}
export function optionSize(option: Option): string {
  if (option.none) return '';
  if (option.radius !== undefined) return `within ${distance(option.radius)}`;
  const bounds = questionBounds({ options: [option] } as Question);
  if (!bounds || !option.extent && !option.zone) return '';
  const lat = (bounds.south + bounds.north) / 2, lng = (bounds.west + bounds.east) / 2;
  const width = haversine({ lat, lng: bounds.west }, { lat, lng: bounds.east });
  const height = haversine({ lat: bounds.south, lng }, { lat: bounds.north, lng });
  return `${distance(width)} × ${distance(height)} area`;
}
export function focusOptions(q: Question) {
  const labels = q.options.map(o => plainLabel(o.label, 'Option'));
  return q.options.map((option, index) => {
    const size = optionSize(option), duplicate = labels.filter(label => label === labels[index]).length > 1;
    return { option, label: duplicate && size ? `${labels[index]} · ${size}` : labels[index], size: duplicate ? '' : size };
  });
}
export function focusCandidate(candidate: Candidate): Candidate {
  return { ...candidate, name: plainLabel(candidate.name, candidate.role === 'camera' ? 'Reference photo' : 'Area estimate') };
}
export function uncertaintySentence(a: Output): string {
  if (a.r === null) return 'Uncertainty unknown.';
  const within = `probably within ${distance(a.r)}.`;
  return a.role === 'camera' ? `A camera position, ${within}` : a.role === 'area' ? `The centre of an area, ${within}` : a.role === 'landmark' ? `A landmark point, ${within}` : `Probably within ${distance(a.r)}.`;
}
export function focusCaseStatus(c: CaseRecord, started: boolean, backendStatus?: string) {
  if (c.submitted || backendStatus === 'submitted') return 'submitted';
  if (c.question || backendStatus === 'question waiting') return 'question';
  if (c.finished || backendStatus === 'finished' || c.answer && backendStatus === 'answer ready') return 'done';
  return started && (c.stages.length > 0 || c.evidence.length > 0 || c.answer || backendStatus === 'processing') ? 'working' : 'waiting';
}
export function initialFullConsole(search: string, storage?: Pick<Storage, 'getItem'>): boolean {
  const view = new URLSearchParams(search).get('view');
  if (view === 'full' || view === 'focus') return view === 'full';
  try { return storage?.getItem('aqui-console-view') === 'full'; } catch { return false; }
}
