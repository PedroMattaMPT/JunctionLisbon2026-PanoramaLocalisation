import { h, Fragment, cx, useT, useDensity, useId, fmtDist, fmtCoord } from './rt';
import { Icon } from './icons';
import { REGIONS } from './geo-data';
import { COUNTRIES } from './geo-countries';
import { PerspScene } from './panorama';
import { urbanScene } from './scene';

// ---------- geometry ----------
function decode(str: string): [number, number][] {
  const out: [number, number][] = []; let i = 0, lat = 0, lng = 0;
  const next = () => { let r = 0, s = 0, b; do { b = str.charCodeAt(i++) - 63; r |= (b & 0x1f) << s; s += 5; } while (b >= 0x20); return r & 1 ? ~(r >> 1) : r >> 1; };
  while (i < str.length) { lat += next(); lng += next(); out.push([lng / 1e3, lat / 1e3]); }
  return out;
}
const CACHE: Record<string, [number, number][][]> = {};
const ringsOf = (key: string, r: string[]) => (CACHE[key] ||= r.map(decode));
export const M_PER_DEG = 111320;

export interface View { lat: number; lng: number; span: number }
export function projector(view: View, W: number, H: number) {
  const cos = Math.cos(view.lat * Math.PI / 180); const k = W / (view.span * cos);
  const p = (lat: number, lng: number): [number, number] => [W / 2 + (lng - view.lng) * cos * k, H / 2 + (view.lat - lat) * k];
  const mpp = M_PER_DEG / k; // metres per pixel
  return { p, k, mpp, cos };
}
const path = (pts: [number, number][], P: (lat: number, lng: number) => [number, number]) => 'M' + pts.map(([lng, lat]) => { const [x, y] = P(lat, lng); return x.toFixed(1) + ' ' + y.toFixed(1); }).join('L') + 'Z';

// Porto riverfront, schematic (offline base at town zoom): river banks and a few streets (lat, lng)
const DOURO_N: [number, number][] = [[41.1478, -8.6760], [41.1452, -8.6560], [41.1436, -8.6420], [41.1424, -8.6300], [41.1412, -8.6210], [41.1405, -8.6140], [41.1404, -8.6090], [41.1409, -8.6020], [41.1418, -8.5940], [41.1436, -8.5850], [41.1462, -8.5760], [41.1490, -8.5660]];
const DOURO_S: [number, number][] = [[41.1438, -8.6760], [41.1418, -8.6560], [41.1400, -8.6420], [41.1388, -8.6300], [41.1380, -8.6210], [41.1384, -8.6140], [41.1385, -8.6090], [41.1388, -8.6020], [41.1396, -8.5940], [41.1412, -8.5850], [41.1440, -8.5760], [41.1468, -8.5660]];
const STREETS: [number, number][][] = [
  [[41.1412, -8.6300], [41.1420, -8.6220], [41.1416, -8.6160], [41.1411, -8.6120], [41.1412, -8.6060]],
  [[41.1411, -8.6130], [41.1440, -8.6118], [41.1468, -8.6110], [41.1500, -8.6100]],
  [[41.1416, -8.6160], [41.1450, -8.6170], [41.1480, -8.6190]],
  [[41.1430, -8.6230], [41.1460, -8.6260], [41.1490, -8.6280]],
  [[41.1404, -8.6094], [41.1385, -8.6094]],
  [[41.1379, -8.6200], [41.1372, -8.6120], [41.1370, -8.6040], [41.1362, -8.5960]],
  [[41.1372, -8.6120], [41.1340, -8.6110], [41.1310, -8.6100]],
  [[41.1500, -8.6200], [41.1470, -8.6050], [41.1460, -8.5980]],
];
// building blocks (schematic): a deterministic grid either side of the river, kept clear of the main streets
const riverLat = (lng: number, bank: [number, number][]) => { for (let i = 0; i < bank.length - 1; i++) { const [la0, ln0] = bank[i], [la1, ln1] = bank[i + 1]; if (lng >= ln0 && lng <= ln1) return la0 + (la1 - la0) * (lng - ln0) / (ln1 - ln0); } return bank[0][0]; };
const BLOCKS: [number, number, number, number][] = (() => { const out: [number, number, number, number][] = []; let seed = 11; const r = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
  for (let lng = -8.640; lng < -8.592; lng += 0.00092) for (let lat = 41.1300; lat < 41.1530; lat += 0.00068) {
    const n = riverLat(lng, DOURO_N), sth = riverLat(lng, DOURO_S); const w = 0.00066 + r() * 0.00012, hh = 0.00046 + r() * 0.0001;
    if (lat < n + 0.0001 && lat + hh > sth - 0.0001) continue; if (Math.abs(lng + 8.6127) < 0.0005 || Math.abs(lng + 8.6094) < 0.0003) continue; if (r() < 0.12) continue;
    out.push([lat, lng, lat + hh, lng + w]); }
  return out; })();
const TOWN_LABELS = [{ t: 'Ribeira', lat: 41.1428, lng: -8.6122 }, { t: 'Miragaia', lat: 41.1448, lng: -8.6215 }, { t: 'Vila Nova de Gaia', lat: 41.1352, lng: -8.6150 }, { t: 'Sé', lat: 41.1460, lng: -8.6085 }];

// ---------- the component ----------
export interface MapViewProps {
  view: View; width?: number; height?: number; offline?: boolean; base?: 'auto' | 'outline' | 'town';
  heat?: { lat: number; lng: number; w: number; s: number }[]; samples?: number; refs?: { id: string; lat: number; lng: number; label?: string; accepted?: boolean }[];
  candidates?: { id: string; rank?: number; lat: number; lng: number; name?: string; ruledOut?: boolean; r?: number | null }[]; selected?: string;
  rings?: { lat: number; lng: number; r: number | null; label?: string; tone?: string }[];
  zones?: { key: string; region?: string; poly?: [number, number][]; rest?: boolean; point?: [number, number] | null; label?: string; chosen?: boolean; dim?: boolean }[];
  cone?: { lat: number; lng: number; bearing: number; err: number; len: number; label?: string };
  final?: { lat: number; lng: number; r: number | null };
  area?: { lat: number; lng: number; r: number; label: string };
  legend?: boolean; scale?: boolean; labels?: boolean; inset?: { view: View; box?: View; label?: string }; hoverRef?: string; dimOthers?: boolean; caption?: string;
}
/** The map (MapLibre in the app; bundled outlines when offline). Layer order keeps it readable: base < heat < zones < points < rings < pins < labels. */
export function MapView(props: MapViewProps) {
  const { view, width = 420, height = 360, offline, heat, samples = 0, refs = [], candidates = [], selected, rings = [], zones = [], cone, final, area, legend = true, scale = true, labels = true, inset, hoverRef, dimOthers, caption } = props;
  const T = useT();
  const stage = useDensity() === 'stage';
  const uid = useId().replace(/:/g, '');
  const W = width, H = height;
  const { p, mpp } = projector(view, W, H);
  const base = props.base === 'auto' || !props.base ? (view.span < 0.2 ? 'town' : 'outline') : props.base;
  const s = stage ? 1.8 : 1;
  const L: any[] = [];

  // --- base ---
  L.push(h('rect', { key: 'water', x: 0, y: 0, width: W, height: H, className: 'aq-map-water' }));
  if (base === 'outline') {
    for (const c of COUNTRIES) { const rs = ringsOf('c' + c.id + c.name, c.r); L.push(h('path', { key: 'c' + c.name, d: rs.map(r => path(r, p)).join(''), className: c.focus ? 'aq-map-land' : 'aq-map-land-out' })); }
    for (const r of REGIONS) { const rs = ringsOf('r' + r.id + r.name, r.r); L.push(h('path', { key: 'r' + r.id + r.name, d: rs.map(q => path(q, p)).join(''), className: 'aq-map-region' })); }
    for (const c of COUNTRIES.filter(c => c.focus)) { const rs = ringsOf('c' + c.id + c.name, c.r); L.push(h('path', { key: 'cb' + c.name, d: rs.map(r => path(r, p)).join(''), className: 'aq-map-country' })); }
  } else {
    L.push(h('rect', { key: 'land', x: 0, y: 0, width: W, height: H, className: 'aq-map-land' }));
    const river = [...DOURO_N, ...[...DOURO_S].reverse()].map(([la, ln]) => p(la, ln));
    BLOCKS.forEach((b, i) => { const [x0, y0] = p(b[2], b[1]), [x1, y1] = p(b[0], b[3]); if (x1 < 0 || x0 > W || y1 < 0 || y0 > H) return; L.push(h('rect', { key: 'bk' + i, x: x0, y: y0, width: x1 - x0, height: y1 - y0, className: 'aq-map-block' })); });
    L.push(h('polygon', { key: 'douro', points: river.map(q => q.join(',')).join(' '), className: 'aq-map-river' }));
    STREETS.forEach((st, i) => L.push(h('polyline', { key: 'st' + i, points: st.map(([la, ln]) => p(la, ln).join(',')).join(' '), className: 'aq-map-street', strokeWidth: (stage ? 6 : 3.5) * Math.min(1.6, 0.012 / view.span) })));
  }
  // graticule
  const step = view.span > 6 ? 2 : view.span > 1.5 ? 1 : view.span > 0.2 ? 0.1 : 0.005;
  const latMin = view.lat - (H / W) * view.span, latMax = view.lat + (H / W) * view.span;
  for (let g = Math.ceil((view.lng - view.span) / step) * step; g < view.lng + view.span; g += step) { const [x] = p(view.lat, g); L.push(h('line', { key: 'gx' + g.toFixed(4), x1: x, x2: x, y1: 0, y2: H, className: 'aq-map-grat' })); }
  for (let g = Math.ceil(latMin / step) * step; g < latMax; g += step) { const [, y] = p(g, view.lng); L.push(h('line', { key: 'gy' + g.toFixed(4), x1: 0, x2: W, y1: y, y2: y, className: 'aq-map-grat' })); }

  // --- heat (cells, one hue, transparent low end) ---
  if (heat && heat.length) {
    const cell = stage ? 22 : 12; const cells: any[] = [];
    for (let x = 0; x < W; x += cell) for (let y = 0; y < H; y += cell) {
      const lng = view.lng + (x + cell / 2 - W / 2) / (W / view.span); const lat = view.lat - (y + cell / 2 - H / 2) / (W / (view.span * Math.cos(view.lat * Math.PI / 180)));
      let v = 0; for (const b of heat) { const d2 = ((lat - b.lat) ** 2 + ((lng - b.lng) * Math.cos(view.lat * Math.PI / 180)) ** 2) / (b.s * b.s); v += b.w * Math.exp(-d2 / 2); }
      const stepN = Math.min(5, Math.floor(v * 5.5)); if (stepN <= 0) continue;
      cells.push(h('rect', { key: x + '_' + y, x: x + 0.5, y: y + 0.5, width: cell - 1, height: cell - 1, fill: `var(--heat-${stepN})` }));
    }
    L.push(h('g', { key: 'heat', className: cx('aq-map-heat', dimOthers && 'is-dim') }, cells));
  }
  // --- zones (question options): outline + hatch + letter + representative point ---
  if (zones.length) {
    const defs = zones.map(z => h('pattern', { key: z.key, id: `zh${uid}${z.key}`, width: (z.rest ? 12 : 7) * s, height: (z.rest ? 12 : 7) * s, patternUnits: 'userSpaceOnUse', patternTransform: `rotate(${({ A: 45, B: -45, C: 0, D: 90 } as any)[z.key]})` }, h('line', { x1: 0, y1: 0, x2: 0, y2: (z.rest ? 12 : 7) * s, className: `aq-zone-hatch is-${z.key.toLowerCase()}`, strokeWidth: (z.rest ? 1 : 1.5) * s })));
    L.push(h('defs', { key: 'zdefs' }, defs));
    const shapes = zones.filter(z => !z.rest).map(z => {
      const d = z.region ? (() => { const r = REGIONS.find(q => q.id === z.region)!; return ringsOf('r' + r.id + r.name, r.r).map(q => path(q, p)).join(''); })() : z.poly ? path(z.poly.map(([la, ln]) => [ln, la] as [number, number]), p) : '';
      return { z, d };
    });
    zones.forEach(z => {
      const d = z.rest ? `M0 0H${W}V${H}H0Z` + shapes.map(x => x.d).join('') : shapes.find(x => x.z === z)!.d;
      L.push(h('g', { key: 'z' + z.key, className: cx('aq-zone', 'is-' + z.key.toLowerCase(), z.rest && 'is-rest', z.chosen && 'is-chosen', z.dim && 'is-dim') },
        h('path', { d, fill: `url(#zh${uid}${z.key})`, fillRule: 'evenodd', className: 'aq-zone-fill' }), z.rest ? null : h('path', { d, className: 'aq-zone-line', strokeWidth: (z.chosen ? 3 : 1.75) * s })));
    });
    zones.forEach(z => {
      const zp = z.point ? p(z.point[0], z.point[1]) : null; const inView = zp && zp[0] > 8 && zp[0] < W - 30 && zp[1] > 8 && zp[1] < H - 30;
      if (z.point && inView) { const [x, y] = zp!; L.push(h('g', { key: 'zp' + z.key, className: cx('aq-zone-pt', 'is-' + z.key.toLowerCase()) },
        h('rect', { x: x - 11 * s, y: y - 11 * s, width: 22 * s, height: 22 * s, rx: 2, className: 'aq-zone-key' }), h('text', { x, y: y + 4.5 * s, textAnchor: 'middle', className: 'aq-zone-letter', style: { fontSize: 13 * s } }, z.key),
        labels ? h(MapLabel, { x: x + 15 * s, y: y + 4 * s, text: (z.label || '').replace(/^[A-D] · /, '') }) : null)); }
      else if (z.rest) { L.push(h('g', { key: 'zr', className: cx('aq-zone-pt', 'is-' + z.key.toLowerCase()) }, h('rect', { x: 10, y: H - 40 * s, width: 22 * s, height: 22 * s, rx: 2, className: 'aq-zone-key' }), h('text', { x: 10 + 11 * s, y: H - 40 * s + 15.5 * s, textAnchor: 'middle', className: 'aq-zone-letter', style: { fontSize: 13 * s } }, z.key), h(MapLabel, { x: 16 + 22 * s, y: H - 25 * s, text: (z.label || 'Everywhere else').replace(/^[A-D] · /, '') }))); }
    });
  }
  // linked evidence area (e.g. postcode area)
  if (area) { const [x, y] = p(area.lat, area.lng); const r = area.r / mpp; L.push(h('g', { key: 'area', className: 'aq-map-area' }, h('circle', { cx: x, cy: y, r, strokeWidth: 2 * s }), labels ? h(MapLabel, { x: x + r + 4, y: y - r + 10, text: area.label }) : null)); }
  // view cone
  if (cone) { const [x, y] = p(cone.lat, cone.lng); const a1 = (cone.bearing - cone.err) * Math.PI / 180, a2 = (cone.bearing + cone.err) * Math.PI / 180; const Lc = cone.len * s;
    L.push(h('g', { key: 'cone', className: 'aq-map-cone' }, h('path', { d: `M${x} ${y}L${x + Math.sin(a1) * Lc} ${y - Math.cos(a1) * Lc}A${Lc} ${Lc} 0 0 1 ${x + Math.sin(a2) * Lc} ${y - Math.cos(a2) * Lc}Z` }),
      h('line', { x1: x, y1: y, x2: x + Math.sin(cone.bearing * Math.PI / 180) * Lc, y2: y - Math.cos(cone.bearing * Math.PI / 180) * Lc }),
      cone.label && labels ? h(MapLabel, { x: x + Math.sin(cone.bearing * Math.PI / 180) * Lc * 0.6 + 6, y: y - Math.cos(cone.bearing * Math.PI / 180) * Lc * 0.6, text: cone.label }) : null)); }
  // sampled points
  if (samples && heat) { const pts: any[] = []; let seed = 7; const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
    for (let i = 0; i < samples; i++) { const b = heat[Math.floor(rnd() * heat.length)]; const u = rnd(), v2 = rnd(); const rr = Math.sqrt(-2 * Math.log(u + 1e-9)) * b.s * 0.9; const th = 2 * Math.PI * v2; const [x, y] = p(b.lat + rr * Math.sin(th), b.lng + rr * Math.cos(th) / Math.cos(view.lat * Math.PI / 180)); pts.push(h('circle', { key: i, cx: x, cy: y, r: 1.6 * s })); }
    L.push(h('g', { key: 'samples', className: cx('aq-map-samples', dimOthers && 'is-dim') }, pts)); }
  // reference photos
  let thumb: any = null;
  refs.forEach(r => { const [x, y] = p(r.lat, r.lng); const hv = hoverRef === r.id;
    L.push(h('g', { key: 'ref' + r.id, className: cx('aq-map-ref', r.accepted === false && 'is-rejected', hv && 'is-hover', dimOthers && 'is-dim') }, h('rect', { x: x - 4 * s, y: y - 4 * s, width: 8 * s, height: 8 * s, strokeWidth: 1.5 * s })));
    if (hv) { const tx = x > W / 2 ? 12 : W - 136, ty = 28;
      thumb = h('g', { key: 'thumb', className: 'aq-map-thumb' }, h('line', { x1: x, y1: y, x2: x > W / 2 ? tx + 124 : tx, y2: ty + 76, className: 'aq-map-thumb-ln' }), h('rect', { x: tx, y: ty, width: 124, height: 76, rx: 2 }), h('svg', { x: tx + 2, y: ty + 2, width: 120, height: 72, viewBox: '0 0 120 72' }, h(PerspScene, { sc: urbanScene(), cam: { pos: [-13, -7, 1.6], yaw: 52, fov: 62, w: 120, h: 72 } })), h(MapLabel, { x: tx, y: ty - 6, text: r.label || 'reference photo' })); } });
  // rings
  const ringEl = (key: string, lat: number, lng: number, r: number | null, label?: string, tone = 'solver') => {
    const [x, y] = p(lat, lng);
    if (r == null) { const R = 34 * s; return h('g', { key, className: 'aq-ring is-unknown' }, h('circle', { cx: x, cy: y, r: R, strokeWidth: 1.75 * s }), h('circle', { cx: x, cy: y, r: R * 0.55, strokeWidth: 1 * s, className: 'aq-ring-inner' }), h('text', { x: x + R * 0.71 + 4, y: y - R * 0.71, className: 'aq-ring-q', style: { fontSize: 14 * s } }, '?'), labels ? h(MapLabel, { x: x + R + 6, y: y + 4, text: label || '± unknown radius' }) : null); }
    const R = r / mpp; const tiny = R < 4;
    return h('g', { key, className: cx('aq-ring', 'is-' + tone, tiny && 'is-tiny') }, h('circle', { cx: x, cy: y, r: Math.max(R, 4), strokeWidth: 1.75 * s }), labels ? h(MapLabel, { x: x + Math.max(R, 4) + 5, y: y - Math.max(R, 4) * 0.7, text: (label || `± ${fmtDist(r)}`) + (tiny ? ' (smaller than a pixel here)' : '') }) : null);
  };
  rings.forEach((r, i) => L.push(ringEl('ring' + i, r.lat, r.lng, r.r, r.label, r.tone)));
  // candidate pins
  candidates.forEach(c => { const [x, y] = p(c.lat, c.lng); const sel = selected === c.id; const R = 9 * s;
    L.push(h('g', { key: 'cand' + c.id, className: cx('aq-pin', sel && 'is-sel', c.ruledOut && 'is-out'), 'data-link': c.id },
      h('circle', { cx: x, cy: y, r: R + 2, className: 'aq-pin-halo' }), h('circle', { cx: x, cy: y, r: R, className: 'aq-pin-dot' }),
      c.ruledOut ? h('line', { x1: x - R, y1: y + R, x2: x + R, y2: y - R, className: 'aq-pin-strike' }) : h('text', { x, y: y + 4 * s, textAnchor: 'middle', className: 'aq-pin-n', style: { fontSize: 11 * s } }, c.rank),
      sel ? h('circle', { cx: x, cy: y, r: R + 5 * s, className: 'aq-pin-sel', strokeWidth: 2 * s }) : null,
      labels && c.name ? h(MapLabel, { x: x + R + 5, y: y + 4, text: c.name }) : null)); });
  // final surveyor's mark
  if (final) { L.push(ringEl('fring', final.lat, final.lng, final.r, final.r == null ? undefined : `± ${fmtDist(final.r)}`)); const [x, y] = p(final.lat, final.lng); L.push(h(SurveyMark, { key: 'final', x, y, size: 30 * s })); }

  if (thumb) L.push(thumb);
  // scale bar
  let scaleEl = null;
  if (scale) { const target = 100 * s * mpp; const nice = [5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000]; const m = nice.reduce((a, b) => Math.abs(b - target) < Math.abs(a - target) ? b : a); const px = m / mpp;
    scaleEl = h('g', { className: 'aq-map-scale', transform: `translate(${W - px - 14}, ${H - 16 * s})` }, h('rect', { x: -6, y: -16 * s, width: px + 12, height: 22 * s, rx: 2, className: 'aq-map-scale-bg' }), h('path', { d: `M0 0V-5H${px}V0M${px / 2} 0V-3`, strokeWidth: 1.5 * s, fill: 'none' }), h('text', { x: px / 2, y: -7 * s, textAnchor: 'middle', style: { fontSize: 10.5 * s } }, fmtDist(m))); }
  // town labels
  if (base === 'town' && labels) TOWN_LABELS.forEach(l => { const [x, y] = p(l.lat, l.lng); if (x > 0 && x < W && y > 0 && y < H) L.push(h('text', { key: 'tl' + l.t, x, y, textAnchor: 'middle', className: 'aq-map-place', style: { fontSize: 11 * s } }, l.t)); });
  if (base === 'town' && labels) { const [x, y] = view.span < 0.012 ? p(41.13935, view.lng - view.span * 0.28) : p(41.1394, -8.6265); L.push(h('text', { key: 'douro', x, y, textAnchor: 'middle', className: 'aq-map-waterlabel', style: { fontSize: 13 * s } }, 'Douro'));
    if (view.span < 0.012) { const [qx, qy] = p(41.14072, view.lng + view.span * 0.33); L.push(h('text', { key: 'cais', x: qx, y: qy, textAnchor: 'middle', className: 'aq-map-place', style: { fontSize: 10.5 * s } }, 'Cais da Ribeira')); } }
  if (base === 'outline' && labels) [{ t: 'Portugal', lat: 39.6, lng: -8.0 }, { t: 'España', lat: 40.2, lng: -3.7 }, { t: 'France', lat: 46.6, lng: 2.4 }, { t: 'Atlantic', lat: 41.5, lng: -11.4, water: true }].forEach(l => { const [x, y] = p(l.lat, l.lng); if (x > 20 && x < W - 20 && y > 10 && y < H - 10) L.push(h('text', { key: 'cl' + l.t, x, y, textAnchor: 'middle', className: l.water ? 'aq-map-waterlabel' : 'aq-map-place is-country', style: { fontSize: (l.water ? 13 : 12) * s } }, l.t)); });

  return h('figure', { className: cx('aq-map', offline && 'is-offline', base === 'town' && 'is-town'), style: { width: W } },
    h('svg', { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: 'img', 'aria-label': caption || 'Map' },
      h('clipPath', { id: 'mc' + uid }, h('rect', { x: 0, y: 0, width: W, height: H })), h('g', { clipPath: `url(#mc${uid})` }, L, scaleEl)),
    inset ? h(Inset, inset) : null,
    offline ? h('div', { className: cx('aq-map-offline', T.micro) }, h(Icon, { name: 'offline' }), base === 'town' ? 'Tiles offline · bundled schematic streets' : 'Tiles offline · bundled outlines of PT, ES, FR with district borders') : null,
    legend ? h(MapLegend, { items: legendItems(props) }) : null);
}

function legendItems(pr: MapViewProps) {
  const it: string[] = [];
  if (pr.heat) it.push('heat'); if (pr.samples) it.push('samples'); if (pr.refs && pr.refs.length) it.push('refs'); if (pr.candidates && pr.candidates.length) it.push('cand');
  if (pr.candidates && pr.candidates.some(c => c.ruledOut)) it.push('out');
  if ((pr.rings || []).some(r => r.r != null) || (pr.final && pr.final.r != null)) it.push('ring'); if ((pr.rings || []).some(r => r.r == null) || (pr.final && pr.final.r == null)) it.push('ringU');
  if (pr.final) it.push('final'); if (pr.cone) it.push('cone'); if (pr.zones && pr.zones.length) it.push('zones');
  return it;
}

function MapLabel({ x, y, text }: { x: number; y: number; text: string }) {
  return h('text', { x, y, className: 'aq-map-label' }, text);
}

export interface SurveyMarkProps { x: number; y: number; size?: number }
/** The final pin: a surveyor's trig-point mark (triangle, centre dot, circle), not a teardrop. */
export function SurveyMark({ x, y, size = 30 }: SurveyMarkProps) {
  const r = size / 2, t = r * 0.62;
  const tri = `M${x} ${y - t}L${x + t * 0.866} ${y + t * 0.5}L${x - t * 0.866} ${y + t * 0.5}Z`;
  return h('g', { className: 'aq-mark' }, h('circle', { cx: x, cy: y, r: r + 2, className: 'aq-mark-halo' }), h('circle', { cx: x, cy: y, r, className: 'aq-mark-c' }), h('path', { d: tri, className: 'aq-mark-t' }), h('circle', { cx: x, cy: y, r: Math.max(1.6, size * 0.07), className: 'aq-mark-d' }),
    h('path', { d: `M${x - r - 6} ${y}h5M${x + r + 1} ${y}h5M${x} ${y - r - 6}v5M${x} ${y + r + 1}v5`, className: 'aq-mark-ticks' }));
}

export interface UncertaintyRingProps { r: number | null; source?: string; size?: number }
/** Known radius: a solid ring with ± metres and its source. Unknown: an open dashed ring with "?", never a dot — unknown is not small. */
export function UncertaintyRing({ r, source, size }: UncertaintyRingProps) {
  const T = useT();
  const stage = useDensity() === 'stage';
  const S = size || (stage ? 120 : 72); const c = S / 2;
  return h('figure', { className: 'aq-uring' },
    h('svg', { viewBox: `0 0 ${S} ${S}`, width: S, height: S, 'aria-hidden': true },
      r == null ? h(Fragment, null, h('circle', { cx: c, cy: c, r: c - 4, className: 'aq-ring-shape is-unknown' }), h('circle', { cx: c, cy: c, r: (c - 4) * 0.55, className: 'aq-ring-shape is-inner' }), h('text', { x: c, y: c + 5, textAnchor: 'middle', className: 'aq-ring-q2' }, '?'))
        : h(Fragment, null, h('circle', { cx: c, cy: c, r: c - 4, className: 'aq-ring-shape' }), h('circle', { cx: c, cy: c, r: 2.5, className: 'aq-ring-dot' }), h('line', { x1: c, y1: c, x2: S - 4, y2: c, className: 'aq-ring-rad' }))),
    h('figcaption', null, h('div', { className: T.data }, r == null ? '± unknown' : `± ${fmtDist(r)}`), h('div', { className: cx(T.micro, 'aq-ink3') }, r == null ? 'no bound yet · not zero' : source || '')));
}

function Inset({ view, box, label }: { view: View; box?: View; label?: string }) {
  const W = 132, H = 112; const { p } = projector(view, W, H);
  const L: any[] = [h('rect', { key: 'w', x: 0, y: 0, width: W, height: H, className: 'aq-map-water' })];
  for (const c of COUNTRIES) { const rs = ringsOf('c' + c.id + c.name, c.r); L.push(h('path', { key: c.name, d: rs.map(r => path(r, p)).join(''), className: c.focus ? 'aq-map-land' : 'aq-map-land-out' })); }
  if (box) { const [x0, y0] = p(box.lat + box.span * 0.4, box.lng - box.span / 2), [x1, y1] = p(box.lat - box.span * 0.4, box.lng + box.span / 2); L.push(h('rect', { key: 'b', x: x0, y: y0, width: Math.max(4, x1 - x0), height: Math.max(4, y1 - y0), className: 'aq-inset-box' })); }
  return h('div', { className: 'aq-inset' }, h('svg', { viewBox: `0 0 ${W} ${H}`, width: W, height: H }, L), label ? h('div', { className: 'aq-inset-l console-micro' }, label) : null);
}

// ---------------------------------------------------------------------------
const LEG: Record<string, [string, string]> = {
  heat: ['heat', 'Pixel-geolocation heat'], samples: ['samples', 'Sampled points'], refs: ['refs', 'Reference photos (GPS)'], cand: ['cand', 'Candidates, by rank'], out: ['out', 'Ruled out'],
  ring: ['ring', 'Uncertainty, known radius'], ringU: ['ringU', 'Uncertainty, radius unknown'], final: ['final', 'Best estimate (surveyor’s mark)'], cone: ['cone', 'Measured bearing ± error'], zones: ['zones', 'Zones A–D · key = representative point, not a camera position'],
};
export interface MapLegendProps { items: string[] }
/** The map legend: only the layers on screen, each with its symbol. */
export function MapLegend({ items }: MapLegendProps) {
  const T = useT();
  return h('ul', { className: cx('aq-legend', T.micro) }, items.map(k => h('li', { key: k }, h('svg', { viewBox: '0 0 18 14', width: 18, height: 14, 'aria-hidden': true }, legendSym(k)), LEG[k][1])));
}
function legendSym(k: string) {
  switch (k) {
    case 'heat': return h(Fragment, null, [1, 3, 5].map((s, i) => h('rect', { key: i, x: i * 6, y: 3, width: 5, height: 8, fill: `var(--heat-${s})` })));
    case 'samples': return h(Fragment, null, h('circle', { cx: 4, cy: 7, r: 1.6, className: 'aq-lg-sample' }), h('circle', { cx: 10, cy: 4, r: 1.6, className: 'aq-lg-sample' }), h('circle', { cx: 14, cy: 9, r: 1.6, className: 'aq-lg-sample' }));
    case 'refs': return h('rect', { x: 5, y: 3, width: 8, height: 8, className: 'aq-lg-ref' });
    case 'cand': return h(Fragment, null, h('circle', { cx: 9, cy: 7, r: 6, className: 'aq-lg-cand' }), h('text', { x: 9, y: 10, textAnchor: 'middle', className: 'aq-lg-candn' }, '1'));
    case 'out': return h(Fragment, null, h('circle', { cx: 9, cy: 7, r: 6, className: 'aq-lg-out' }), h('line', { x1: 4, y1: 12, x2: 14, y2: 2, className: 'aq-lg-outl' }));
    case 'ring': return h('circle', { cx: 9, cy: 7, r: 5.5, className: 'aq-lg-ring' });
    case 'ringU': return h('circle', { cx: 9, cy: 7, r: 5.5, className: 'aq-lg-ringu' });
    case 'final': return h('path', { d: 'M9 2l5 9H4z', className: 'aq-lg-final' });
    case 'cone': return h('path', { d: 'M2 12L16 3V12Z', className: 'aq-lg-cone' });
    default: return h(Fragment, null, h('rect', { x: 1, y: 3, width: 7, height: 8, className: 'aq-lg-za' }), h('rect', { x: 10, y: 3, width: 7, height: 8, className: 'aq-lg-zb' }));
  }
}
