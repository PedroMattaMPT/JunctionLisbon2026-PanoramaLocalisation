import React, { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import maplibregl, { type StyleSpecification, type Map as GLMap } from 'maplibre-gl';
import { Protocol } from 'pmtiles';
import { MapView, MapLegend, SurveyMark, projector } from '@ds/map';
import { Segmented, Toggle } from '@ds/base';
import { useDensity } from '@ds/rt';
import { REGIONS } from '@ds/geo-data';
import { arr, finite, point, positive, record, str, type CaseRecord, type Fields, type Question } from './model';
import { localAsset, type TileLayer } from './data';
import { questionView } from './bounds';
export { questionBounds, questionView } from './bounds';
import { Disclosure, mapTree, typeName, useWidth, type ElementProps } from './ui';
import { distance, roleText } from './format';
import { motionDuration, reducedMotion } from './motion';

const protocol = new Protocol(); maplibregl.addProtocol('pmtiles', protocol.tile);
export interface View { lat: number; lng: number; span: number }
export function caseView(c: CaseRecord, selected?: string, final = false): View {
  const candidate = c.candidates.find(v => v.id === selected) ?? c.candidates[0];
  const target = final && c.answer ? c.answer : candidate;
  if (target?.lat === undefined || target.lng === undefined) return { lat: 43, lng: -3, span: 20 };
  const radius = target.r;
  const spread = radius === null ? 14 : Math.max(radius * 8 / 111320, candidate?.level === 'region' && !final ? 5 : candidate?.level === 'country' && !final ? 16 : 0.001);
  return { lat: target.lat, lng: target.lng, span: spread };
}
/** The live server's base-map layers and the operator's choice ('outlines' draws no tiles). */
export interface TileChoice { layers: TileLayer[]; layer: string; setLayer(id: string): void }
export const TileContext = createContext<TileChoice>({ layers: [], layer: 'streets', setLayer: () => {} });
const shortLabel = (label: string) => label.length > 34 ? `${label.slice(0, 33)}…` : label;
export function questionZones(q?: Question) {
  const hasGeometry = q?.options.some(o => Array.isArray(record(o.zone).coordinates) || REGIONS.some(r => r.id === o.region));
  return (q?.options ?? []).flatMap(o => {
    const coords = arr(record(o.zone).coordinates)[0];
    const poly = arr(coords).flatMap(p => { const a = arr(p); return finite(a[0]) !== null && finite(a[1]) !== null ? [[a[1] as number, a[0] as number] as [number, number]] : []; });
    const region = REGIONS.some(r => r.id === o.region) ? o.region : undefined;
    // Place options (a point and a radius, no zone) get their lettered key and radius ring too.
    const place = !hasGeometry && !o.none && !!o.point;
    return poly.length || region || o.none && hasGeometry || place ? [{ key: o.key, poly: poly.length ? poly : undefined, region, rest: o.none, point: o.point, radius: place ? o.radius : undefined, label: shortLabel(o.label), chosen: q?.status === 'answered' && q.answer === o.key, dim: q?.status === 'answered' && q.answer !== o.key }] : [];
  });
}
function mapData(c: CaseRecord) {
  const cells = c.evidence.flatMap(e => e.kind === 'region' ? arr(e.payload.cells).map(record).filter(p => point(p) && positive(p.size_m) && finite(p.v) !== null) : []);
  const samples = c.evidence.flatMap(e => e.kind === 'geo_sample' ? arr(e.payload.points).flatMap(p => point(p) ?? []) : []);
  const refs = c.evidence.flatMap(e => {
    const r = e.kind === 'match' ? record(e.payload.reference) : e.payload;
    return ['neighbour', 'landmark_photo', 'match'].includes(e.kind) && point(r) ? [{ ...point(r)!, id: e.id, label: `${str(r.source, 'Reference')} · ${roleText(e.kind === 'landmark_photo' ? 'landmark' : 'camera')}`, accepted: typeof e.payload.accepted === 'boolean' ? e.payload.accepted : undefined }] : [];
  });
  const names = c.evidence.flatMap(e => e.kind === 'name_match' ? arr(e.payload.matches).map(record).filter(p => point(p)).map(p => ({ ...point(p)!, id: e.id, label: str(p.label), role: str(p.role) })) : []);
  return { cells, samples, refs, names };
}
function svgCell(p: Fields, project: (lat: number, lng: number) => [number, number]) {
  const half = (p.size_m as number) / 111320 / 2, lat = p.lat as number, lng = p.lng as number;
  const longitudeHalf = half / Math.cos(lat * Math.PI / 180);
  const a = project(lat + half, lng - longitudeHalf), b = project(lat - half, lng + longitudeHalf);
  return { x: a[0], y: a[1], width: b[0] - a[0], height: b[1] - a[1] };
}
function tileStyle(tile: string, element: HTMLElement): StyleSpecification {
  const css = getComputedStyle(element), token = (name: string) => css.getPropertyValue(`--${name}`).trim();
  const source = localAsset(tile); if (!source) throw new Error('Map tiles must be served locally.');
  const raster = /\{z\}/.test(tile) || import.meta.env.VITE_TILE_FORMAT === 'raster';
  const sources: StyleSpecification['sources'] = raster ? { local: { type: 'raster', tiles: [source], tileSize: 256 } } : { local: { type: 'vector', url: `pmtiles://${source}` } };
  return { version: 8, sources, layers: [
    { id: 'base', type: 'background', paint: { 'background-color': token('map-land') } },
    ...(raster ? [{ id: 'local-tiles', type: 'raster', source: 'local' } as const] : [
      { id: 'water', type: 'fill', source: 'local', 'source-layer': 'water', paint: { 'fill-color': token('map-water') } } as const,
      { id: 'buildings', type: 'fill', source: 'local', 'source-layer': 'building', paint: { 'fill-color': token('surface-3') } } as const,
      { id: 'roads', type: 'line', source: 'local', 'source-layer': 'transportation', paint: { 'line-color': token('map-border'), 'line-width': parseFloat(token('border-rule')) } } as const,
      { id: 'borders', type: 'line', source: 'local', 'source-layer': 'boundary', paint: { 'line-color': token('map-border-country'), 'line-width': parseFloat(token('border-hair')) } } as const,
    ]),
  ] };
}
function layerStyle(layers: TileLayer[], selected: string, element: HTMLElement): StyleSpecification {
  const css = getComputedStyle(element), token = (name: string) => css.getPropertyValue(`--${name}`).trim();
  const sources: StyleSpecification['sources'] = Object.fromEntries(layers.map(l => [`tiles-${l.id}`, { type: 'raster', tiles: [localAsset(l.url)!], tileSize: 256, maxzoom: l.max_zoom, attribution: l.attribution }]));
  return { version: 8, sources, layers: [
    { id: 'base', type: 'background', paint: { 'background-color': token('map-land') } },
    ...layers.map(l => ({ id: `tiles-${l.id}`, type: 'raster', source: `tiles-${l.id}`, layout: { visibility: l.id === selected ? 'visible' : 'none' } } as const)),
  ] };
}
function GeoOverlay({ map, c, selected, evidenceSelection, q, final, onSelect, width, height }: { map: GLMap; c: CaseRecord; selected?: string; evidenceSelection?: string; q?: Question; final: boolean; onSelect(id: string): void; width: number; height: number }) {
  const stage = useDensity() === 'stage', data = mapData(c), unit = parseFloat(getComputedStyle(map.getContainer()).getPropertyValue('--space-1')) * (stage ? 2 : 1);
  const project = (lat: number, lng: number): [number, number] => { const p = map.project([lng, lat]); return [p.x, p.y]; };
  const zones = questionZones(q), ring = (lat: number, lng: number, radius: number | null, id: string) => {
    const [x, y] = project(lat, lng), edge = project(lat, lng + (radius ?? 0) / (111320 * Math.cos(lat * Math.PI / 180)));
    const r = radius === null ? unit * 8 : Math.max(unit, Math.abs(edge[0] - x));
    return <g key={id} className={`aq-ring ${radius === null ? 'is-unknown' : 'is-solver'}`}><circle cx={x} cy={y} r={r} /><text x={x + r + unit} y={y} className="aq-map-label">{radius === null ? '? · radius unknown' : `± ${distance(radius)}`}</text></g>;
  };
  const asking = q?.status === 'open';
  const optionKeys = zones.map(z => {
    if (!z.point) return null; const [x, y] = project(z.point[0], z.point[1]);
    const r = z.radius ? Math.abs(project(z.point[0], z.point[1] + z.radius / (111320 * Math.cos(z.point[0] * Math.PI / 180)))[0] - x) : 0;
    return <g key={`zp-${z.key}`} className={`aq-zone-pt is-${z.key.toLowerCase()} ${z.dim ? 'is-dim' : ''}`} data-motion-target="zone">{r > unit ? <circle cx={x} cy={y} r={r} className={`app-option-ring is-${z.key.toLowerCase()}`} /> : null}<rect x={x - unit * 2.75} y={y - unit * 2.75} width={unit * 5.5} height={unit * 5.5} rx={2} className="aq-zone-key" /><text x={x} y={y + unit * 1.1} textAnchor="middle" className="aq-zone-letter">{z.key}</text><title>{z.key} · {z.label}{z.radius ? ` · within ${distance(z.radius)}` : ''}</title></g>;
  });
  const target = candidateTarget(c, selected, final), bearing = c.yawToBearing, err = c.yawToBearingErr;
  const cone = target && bearing !== null && err !== undefined ? (() => { const [x, y] = project(target.lat, target.lng), radius = width / 5, a = (bearing - err) * Math.PI / 180, b = (bearing + err) * Math.PI / 180; return <g className="aq-map-cone"><path d={`M${x} ${y}L${x + Math.sin(a) * radius} ${y - Math.cos(a) * radius}A${radius} ${radius} 0 0 1 ${x + Math.sin(b) * radius} ${y - Math.cos(b) * radius}Z`} /><title>Image yaw 0 · bearing {bearing}° ± {err}° from the current candidate</title></g>; })() : null;
  return <svg className="app-map-overlay" width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-label="Logged map evidence">
    <defs>{zones.map(z => <pattern id={`local-zone-${z.key}`} key={z.key} width={unit * 2} height={unit * 2} patternUnits="userSpaceOnUse" patternTransform={`rotate(${({ A: 45, B: -45, C: 0, D: 90 } as Record<string, number>)[z.key]})`}><line x1={0} x2={0} y1={0} y2={unit * 2} className={`aq-zone-hatch is-${z.key.toLowerCase()}`} /></pattern>)}</defs>
    <g data-motion-target="geo" data-dim={q?.status === 'open' || selected || final ? 'true' : undefined}>{data.cells.map((cell, i) => <rect key={i} {...svgCell(cell, project)} fill={`var(--heat-${Math.max(0, Math.min(5, Math.ceil((cell.v as number) * 5)))})`} />)}</g>
    {zones.map(z => { const path = z.poly?.map(([lat, lng]) => project(lat, lng)); if (!path) return null; return <g key={z.key} className={`aq-zone is-${z.key.toLowerCase()} ${z.chosen ? 'is-chosen' : ''} ${z.dim ? 'is-dim' : ''}`} data-motion-target="zone"><polygon points={path.map(p => p.join(',')).join(' ')} fill={`url(#local-zone-${z.key})`} className="aq-zone-line" /></g>; })}
    <g className="aq-map-samples">{data.samples.map((p, i) => { const [x, y] = project(p.lat, p.lng); return <circle key={i} cx={x} cy={y} r={unit / 2} />; })}</g>
    {data.refs.map(p => { const [x, y] = project(p.lat, p.lng); return <g className="aq-map-ref" key={p.id} data-link={p.id} data-leader={`map-${p.id}`} role="button" tabIndex={0} aria-label={p.label} onClick={() => onSelect(p.id)} onKeyDown={e => { if (e.key === 'Enter') onSelect(p.id); }}><rect x={x - unit} y={y - unit} width={unit * 2} height={unit * 2} /><title>{p.label}</title></g>; })}
    {cone}{asking ? null : c.candidates.flatMap(v => v.lat === undefined || v.lng === undefined ? [] : [ring(v.lat, v.lng, v.r, `ring-${v.id}`)])}
    {c.candidates.flatMap(v => { if (v.lat === undefined || v.lng === undefined) return []; const [x, y] = project(v.lat, v.lng); return <g key={v.id} className={`aq-pin ${v.id === selected ? 'is-sel' : ''}`} data-link={v.id} data-leader={evidenceSelection && [...v.evidence, ...v.supports].includes(evidenceSelection) ? `map-${evidenceSelection}` : undefined} data-dim={asking || selected && selected !== v.id ? 'true' : undefined} role="button" tabIndex={0} onClick={() => onSelect(v.id)} onKeyDown={e => { if (e.key === 'Enter') onSelect(v.id); }} aria-label={`${v.name}, ${roleText(v.role)}`}><circle cx={x} cy={y} r={unit * 2.5} className="aq-pin-dot" /><text x={x} y={y + unit} textAnchor="middle" className="aq-pin-n">{v.rank}</text></g>; })}
    {optionKeys}
    {final && c.answer && <>{ring(c.answer.lat, c.answer.lng, c.answer.r, 'final-ring')}<g data-motion-target="final-mark"><SurveyMark {...(() => { const [x, y] = project(c.answer!.lat, c.answer!.lng); return { x, y }; })()} size={unit * 8} /></g></>}
    {data.names.map((p, i) => { const [x, y] = project(p.lat, p.lng); return <text key={i} x={x} y={y} className="aq-map-label" data-link={p.id} data-leader={`map-${p.id}`}>{p.label} · {roleText(p.role)}</text>; })}
  </svg>;
}
export function EvidenceMap({ c, selected, evidenceSelection, onSelect, tileSource, final = false, q, animate = false, focusRevision = 0, compact = false }: { c: CaseRecord; selected?: string; evidenceSelection?: string; onSelect(id: string): void; tileSource?: string | null; final?: boolean; q?: Question; animate?: boolean; focusRevision?: number; compact?: boolean }) {
  const { ref, width } = useWidth<HTMLDivElement>(424), height = width * (final && !compact ? 0.95 : 0.78);
  const host = useRef<HTMLDivElement>(null), [map, setMap] = useState<GLMap>(), [, repaint] = useState(0), [failed, setFailed] = useState(false);
  const [showResolvedZones, setShowResolvedZones] = useState(false);
  const visibleQuestion = !compact || q?.status === 'open' || showResolvedZones ? q : undefined;
  useEffect(() => setShowResolvedZones(false), [c.id, q?.id]);
  const tiles = useContext(TileContext), live = tiles.layers.length > 0 && tiles.layer !== 'outlines';
  const tile = tiles.layers.length ? live ? tiles.layers[0].url : undefined : tileSource ?? str(import.meta.env.VITE_TILE_SOURCE);
  const layerKey = tiles.layers.map(l => l.url).join(' '), selectedLayer = useRef(tiles.layer); selectedLayer.current = tiles.layer;
  const [tileErrors, setTileErrors] = useState(0);
  const openView = visibleQuestion?.status === 'open' && !selected && !final ? questionView(visibleQuestion) : undefined;
  const view = openView ?? caseView(c, selected, final); const data = useMemo(() => mapData(c), [c.evidence]);
  const previousView = useRef(view);
  const target = candidateTarget(c, selected, final);
  const cone = target && c.yawToBearing !== null && c.yawToBearingErr !== undefined ? { ...target, bearing: (c.yawToBearing + 360) % 360, err: c.yawToBearingErr, len: width / 5, label: 'Image yaw 0 · measured bearing' } : undefined;
  useEffect(() => {
    if (!tile || !host.current) return;
    let gl: GLMap;
    const style = () => tiles.layers.length ? layerStyle(tiles.layers, selectedLayer.current, host.current!) : tileStyle(tile, host.current!);
    try {
      gl = new maplibregl.Map({ container: host.current, style: style(), center: [view.lng, view.lat], zoom: Math.log2(360 / view.span), attributionControl: false, pitchWithRotate: false, dragRotate: false });
      gl.on('load', () => { setMap(gl); setFailed(false); }); gl.on('move', () => repaint(v => v + 1));
      // A tile that fails (flaky venue network) leaves a gap; only a broken style falls back to the outlines.
      gl.on('error', (e: { tile?: unknown; sourceId?: string }) => { if (e.tile || e.sourceId) { setTileErrors(v => v + 1); return; } setFailed(true); setMap(undefined); });
      const theme = new MutationObserver(() => { if (gl.isStyleLoaded()) gl.setStyle(style()); }); theme.observe(document.documentElement, { attributes: true, subtree: true, attributeFilter: ['data-theme'] });
      return () => { theme.disconnect(); gl.remove(); setMap(undefined); };
    } catch { setFailed(true); }
  }, [tile, layerKey]);
  useEffect(() => { if (!map || !tiles.layers.length) return; for (const l of tiles.layers) if (map.getLayer(`tiles-${l.id}`)) map.setLayoutProperty(`tiles-${l.id}`, 'visibility', l.id === tiles.layer ? 'visible' : 'none'); setTileErrors(0); }, [map, tiles.layer, layerKey]);
  useEffect(() => { map?.resize(); }, [map, width]);
  useEffect(() => {
    const cinematic = motionDuration('cinematic'), quick = motionDuration('quick');
    const flight = Math.max(cinematic - quick * 2, Math.min(cinematic + motionDuration('deliberate'), cinematic - quick * 2 + Math.abs(Math.log2(previousView.current.span / view.span)) * quick));
    if (map && !failed) { const zoom = Math.log2(width * 360 / (512 * view.span)); map.flyTo({ center: [view.lng, view.lat], zoom, duration: animate && !reducedMotion() ? flight : 0, essential: false }); }
    else if (ref.current && animate && !reducedMotion()) {
      const old = previousView.current, scale = view.span / old.span, p = projector(view, width, height).p(old.lat, old.lng), dx = width / 2 - scale * p[0], dy = height / 2 - scale * p[1];
      ref.current.querySelector('svg > g')?.animate([{ transform: `translate(${dx}px, ${dy}px) scale(${scale})` }, { transform: 'none' }], { duration: flight, easing: getComputedStyle(ref.current).getPropertyValue('--ease-move').trim() });
    }
    previousView.current = view;
  }, [map, failed, view.lat, view.lng, view.span, focusRevision]);
  const p = projector(view, width, height);
  const candidatePins = c.candidates.flatMap(v => v.lat === undefined || v.lng === undefined ? [] : [{ ...v, lat: v.lat, lng: v.lng }]);
  const ringProps = candidatePins.map(v => ({ lat: v.lat, lng: v.lng, r: v.r, label: v.r === null ? 'Radius unknown' : `± ${distance(v.r)}` }));
  const props = { view, width, height, base: 'outline', offline: true, candidates: candidatePins.map(v => ({ ...v, name: v.id === (selected ?? candidatePins[0]?.id) ? v.name : undefined })), selected, refs: data.refs, rings: ringProps, zones: questionZones(visibleQuestion), cone, final: final && c.answer ? c.answer : undefined, legend: false, labels: true, caption: 'Logged candidate coordinates and uncertainty; map has no coordinate input' };
  const tree = MapView(props);
  const labels: ReactNode[] = [], unit = parseFloat(getComputedStyle(ref.current ?? document.documentElement).getPropertyValue('--space-1'));
  const layer = tiles.layers.find(l => l.id === tiles.layer);
  const attribution = live && !failed && layer ? <p className="app-map-attrib console-micro">{layer.attribution_url ? <a href={layer.attribution_url} target="_blank" rel="noreferrer">{layer.attribution}</a> : layer.attribution}{layer.id === 'satellite' ? ' · Powered by Esri' : ''}</p> : null;
  const layerToggle = tiles.layers.length > 0 ? <div className="app-map-layers"><Segmented label="Base map" value={tiles.layer} options={[...tiles.layers.map(l => ({ id: l.id, label: l.name })), { id: 'outlines', label: 'Outlines' }]} onChange={tiles.setLayer} />{live && tileErrors > 0 && <span className="console-micro aq-ink3">{tileErrors} tile{tileErrors === 1 ? '' : 's'} unavailable · points and zones still shown</span>}</div> : null;
  const legend = <MapLegend items={[...(data.cells.length ? ['heat'] : []), ...(data.samples.length ? ['samples'] : []), ...(data.refs.length ? ['refs'] : []), ...(candidatePins.length ? ['cand', ...(candidatePins.some(v => v.r === null) ? ['ringU'] : ['ring'])] : []), ...(questionZones(visibleQuestion).length ? ['zones'] : []), ...(cone ? ['cone'] : []), ...(final && c.answer ? ['final'] : [])]} />;
  return <div className="app-map" ref={ref} onClick={e => { const id = (e.target as Element).closest('[data-link]')?.getAttribute('data-link'); if (id) onSelect(id); }}>
    {layerToggle}
    {mapTree(tree, node => {
      if (node.type === 'svg' && node.props.role === 'img' && tile && !failed) return <div className="app-map-surface" style={{ height }}><div className="app-maplibre" ref={host} />{map && <GeoOverlay map={map} c={c} selected={selected} evidenceSelection={evidenceSelection} q={visibleQuestion} final={final} onSelect={onSelect} width={width} height={height} />}{attribution}</div>;
      if (node.props.className?.includes('aq-map-offline') && (compact || tile && !failed)) return null;
      if (typeName(node) === 'MapLabel' || node.props.className === 'aq-map-place is-country' || node.props.className === 'aq-map-waterlabel') { labels.push(React.cloneElement(node, { key: `label-${labels.length}` })); return null; }
      if (node.props['data-link']) {
        const candidate = c.candidates.find(v => v.id === node.props['data-link']);
        return React.cloneElement(node, { tabIndex: 0, role: 'button', 'data-leader': candidate && evidenceSelection && [...candidate.evidence, ...candidate.supports].includes(evidenceSelection) ? `map-${evidenceSelection}` : undefined, 'data-dim': selected && selected !== node.props['data-link'] ? 'true' : undefined, 'aria-label': candidate ? `${candidate.name}, ${roleText(candidate.role)}` : `Select ${node.props['data-link']}`, onKeyDown: (e: React.KeyboardEvent) => { if (e.key === 'Enter') onSelect(node.props['data-link']); } });
      }
      if (node.type === 'g' && node.key?.toString().startsWith('ref')) return React.cloneElement(node, { 'data-link': node.key.toString().slice(3), 'data-leader': `map-${node.key.toString().slice(3)}`, tabIndex: 0, role: 'button', 'aria-label': `Reference ${node.key.toString().slice(3)}`, onKeyDown: (e: React.KeyboardEvent) => { if (e.key === 'Enter') onSelect(node.key!.toString().slice(3)); } });
      if (node.props.clipPath && !map) {
        const original = arr(node.props.children).flat(2);
        const heat = <g key="logged-heat" data-motion-target="geo" data-dim={visibleQuestion?.status === 'open' || selected || final ? 'true' : undefined}>{data.cells.map((cell, i) => <rect key={i} {...svgCell(cell, p.p)} fill={`var(--heat-${Math.max(0, Math.min(5, Math.ceil((cell.v as number) * 5)))})`} />)}</g>;
        const samples = <g key="logged-samples" className="aq-map-samples">{data.samples.map((sample, i) => { const [x, y] = p.p(sample.lat, sample.lng); return <circle key={i} cx={x} cy={y} r={unit / 2} />; })}</g>;
        const names = <g key="logged-names">{data.names.map((name, i) => { const [x, y] = p.p(name.lat, name.lng); return <g key={i} data-link={name.id} data-leader={`map-${name.id}`} className="aq-map-ref"><circle cx={x} cy={y} r={unit} /><title>{name.label} · {roleText(name.role)}</title></g>; })}</g>;
        const layers = original.filter(v => React.isValidElement<ElementProps>(v));
        const base = layers.filter(v => { const key = String(v.key); return !/^(z|ref|ring|cand|final|fring|area|cone)/.test(key) && v.props.className !== 'aq-map-scale'; });
        const zones = layers.filter(v => /^z/.test(String(v.key)));
        const refs = layers.filter(v => /^ref/.test(String(v.key)));
        const rings = layers.filter(v => /^(ring|fring|area|cone)/.test(String(v.key)));
        const pins = layers.filter(v => /^cand/.test(String(v.key)));
        const mark = layers.filter(v => String(v.key) === 'final');
        const scale = layers.filter(v => v.props.className === 'aq-map-scale');
        return React.cloneElement(node, {}, base, heat, zones, samples, refs, names, rings, pins, mark, <g key="logged-labels">{labels}{data.names.map((name, i) => { const [x, y] = p.p(name.lat, name.lng); return <text key={i} x={x + unit} y={y} className="aq-map-label">{name.label} · {roleText(name.role)}</text>; })}</g>, scale);
      }
      return node;
    })}
    {compact ? <Disclosure title="Map key" aside={!tile || failed ? 'Local outlines' : layer ? layer.name : 'Local tiles'}>{legend}{q && q.status !== 'open' && questionZones(q).length > 0 && <Toggle label="Last question zones" on={showResolvedZones} onChange={setShowResolvedZones} />}<p className="console-micro aq-ink3">{!tile || failed ? 'Tiles unavailable; using bundled PT, ES and FR outlines.' : layer ? `${layer.name} tiles through the local caching proxy; a missing tile leaves a gap, never a wrong point.` : 'Locally served map tiles.'} The map has no coordinate input; the option links still open Google Maps and OSM.</p></Disclosure> : legend}
  </div>;
}
function candidateTarget(c: CaseRecord, selected?: string, final = false) {
  const target = final ? c.answer : c.candidates.find(v => v.id === selected) ?? c.candidates[0];
  return target?.lat !== undefined && target.lng !== undefined ? { lat: target.lat, lng: target.lng } : undefined;
}
