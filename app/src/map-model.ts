import { arr, finite, nonnegative, point, record, str, strings, type CaseRecord, type Fields } from './model';
import { countryNames } from './analysis-model';
import { plainLabel } from './focus-model';

export interface View { lat: number; lng: number; span: number }
export interface SearchFocus { view: View; label: string; source: string; provisional: boolean }
export const openingView: View = { lat: 43, lng: -3, span: 24 };
const countries: Record<string, View> = { PT: { lat: 39.5, lng: -8, span: 12 }, ES: { lat: 40, lng: -3, span: 16 }, FR: { lat: 46.5, lng: 2.5, span: 19 } };
const cosine = (lat: number) => Math.max(0.2, Math.cos(lat * Math.PI / 180));
function radiusSpan(lat: number, radius: number | null, minimum: number) {
  return radius === null ? Math.max(14, minimum) : Math.max(radius * 6 / (111320 * cosine(lat)), minimum);
}

/** Fit real geographic leads and their logged extents. A raw image match never implies street accuracy. */
function leadsView(rows: Fields[], minimum: number): View | undefined {
  const leads = rows.filter(r => point(r) && (finite(r.weight) ?? finite(r.v) ?? 0) > 0)
    .sort((a, b) => (finite(b.weight) ?? finite(b.v) ?? 0) - (finite(a.weight) ?? finite(a.v) ?? 0)).slice(0, 3);
  if (!leads.length) return;
  const first = point(leads[0])!;
  let span = minimum;
  for (const lead of leads) {
    const p = point(lead)!, accuracy = nonnegative(lead.accuracy_m), extent = nonnegative(lead.extent_m);
    const radius = accuracy === null && extent === null ? null : (accuracy ?? 0) + (extent ?? 0);
    const bound = radius === null ? minimum : radiusSpan(p.lat, radius, minimum);
    span = Math.max(span, Math.abs(p.lng - first.lng) * 2.6 + bound, Math.abs(p.lat - first.lat) * 4.5 + bound);
  }
  return { ...first, span: Math.min(360, span) };
}

export function searchFocus(c: CaseRecord, selected?: string, final = false): SearchFocus {
  const candidate = c.candidates.find(v => v.id === selected) ?? c.candidates[0];
  const target = final && c.answer ? c.answer : candidate;
  if (target?.lat !== undefined && target.lng !== undefined && (final || (candidate?.weight ?? 0) > 0)) {
    return { view: { lat: target.lat, lng: target.lng, span: radiusSpan(target.lat, target.r,
      !final && candidate?.level === 'country' ? 16 : !final && candidate?.level === 'region' ? 5 : 0.004) },
      label: final ? 'Best estimate' : plainLabel(candidate?.name ?? '', 'Leading area'), source: final ? 'Logged solver output' : 'Combined evidence', provisional: !final };
  }
  for (const e of [...c.evidence].reverse()) {
    if (!['region_head', 'knn', 'geoclip', 'region'].includes(e.kind)) continue;
    const rows = arr(e.payload.neighbours ?? e.payload.candidates ?? e.payload.regions).map(record);
    const view = leadsView(rows, e.kind === 'knn' ? 2 : 5);
    const top = rows.filter(r => point(r) && (finite(r.weight) ?? finite(r.v) ?? 0) > 0).sort((a, b) => (finite(b.weight) ?? finite(b.v) ?? 0) - (finite(a.weight) ?? finite(a.v) ?? 0))[0];
    if (view) return { view, label: plainLabel(str(top?.label, str(top?.name)), 'Provisional search area'),
      source: e.kind === 'knn' ? 'Similar reference photos' : e.kind === 'geoclip' ? 'Geographic image estimate' : 'Region estimates', provisional: true };
  }
  // A contrary country clue widens the view; missing or ambiguous clues never turn into a precise point.
  const countryGroups: string[][] = [];
  for (const e of c.evidence) {
    if (e.payload.kept === false) continue;
    const hints = [e.payload, ...arr(e.payload.features).map(record),
      ...arr(e.payload.hints).map(record).filter(h => h.majority === true && !h.conflict)];
    for (const hint of hints) {
      const codes = strings(hint.countries).filter(code => countries[code]);
      if (codes.length && ['strong', 'medium-strong', 'medium'].includes(String(hint.strength))) countryGroups.push(codes);
    }
    const code = String(e.payload.country ?? '');
    if (countries[code]) countryGroups.push([code]);
  }
  const common = countryGroups.reduce<Set<string>>((possible, codes) => new Set(codes.filter(code => possible.has(code))), new Set(Object.keys(countries)));
  if (countryGroups.length && common.size === 1) {
    const code = [...common][0];
    return { view: countries[code], label: countryNames[code], source: 'Visible country clues · provisional', provisional: true };
  }
  return { view: openingView, label: 'Portugal · Spain · France', source: countryGroups.length ? common.size === 0 ? 'Country clues differ · keeping the view broad' : 'Country clues remain ambiguous' : 'Waiting for geographic clues', provisional: true };
}
export function caseView(c: CaseRecord, selected?: string, final = false): View { return searchFocus(c, selected, final).view; }

/** Interpolate scale geometrically so an offline map moves continuously, just like a tile-map flight. */
export function interpolateView(from: View, to: View, progress: number): View {
  if (progress <= 0) return { ...from };
  if (progress >= 1) return { ...to };
  const t = Math.max(0, Math.min(1, progress)), eased = t * t * (3 - 2 * t);
  return { lat: from.lat + (to.lat - from.lat) * eased, lng: from.lng + (to.lng - from.lng) * eased,
    span: Math.exp(Math.log(from.span) + (Math.log(to.span) - Math.log(from.span)) * eased) };
}
