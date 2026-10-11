import React, { useEffect, useMemo, useRef, useState } from 'react';
import 'pannellum';
import { PanoramaStrip, Viewer360, ZoomCrop, LayerToggles } from '@ds/panorama';
import { EmptyState, Segmented } from '@ds/base';
import { CompassDial } from '@ds/charts';
import { useDensity } from '@ds/rt';
import { angularCrop, type PanoramaImage } from './images';
import { localAsset } from './data';
import { record, str, type CaseRecord, type Evidence } from './model';
import { mapTree, typeName, useWidth, Panel, Disclosure } from './ui';
import { decodeMask, paintMask, type IndexedMask } from './masks';

const unknownNumber = { toFixed: () => 'unknown', toString: () => 'unknown' };
export function imageCase(c: CaseRecord, image?: PanoramaImage) {
  return { ...c, size: image ? [image.width, image.height] : c.size, yawToBearingErr: c.yawToBearingErr ?? unknownNumber, detections: [
    ...c.detections.map(d => ({ ...d, kept: d.kept !== false, score: d.score ?? unknownNumber })),
    ...c.evidence.filter(e => e.box && e.kind === 'checklist').map(e => ({ ...e.box, id: e.id, label: str(e.payload.item), kept: true, score: unknownNumber })),
  ], texts: c.texts.map(t => ({ ...t, conf: t.conf ?? unknownNumber })) };
}
export function Strip({ c, image, selected, yaw, layers, onSelect, onYaw }: { c: CaseRecord; image?: PanoramaImage; selected?: string; yaw: number; layers: Record<string, boolean>; onSelect(id: string): void; onYaw(yaw: number): void }) {
  const { ref, width } = useWidth<HTMLDivElement>(); const stage = useDensity() === 'stage';
  const mask = useMask(c.maskUrl, c.maskPalette);
  const safeLayers = { ...layers, mask: layers.mask && c.photographerMask !== undefined, sectors: layers.sectors && c.viewCount === 8, seg: false, sun: layers.sun && c.sun?.yaw !== undefined };
  const tree = PanoramaStrip({ c: imageCase(c, image), width, selected, fov: { yaw, fov: 90 }, layers: safeLayers, ruler: c.yawToBearing !== null ? 'bearing' : 'yaw', labelMode: width > 1000 ? 'all' : 'selected' });
  return <div ref={ref} className="app-strip" data-motion-target="intake" onClick={e => {
    const target = e.target as Element, id = target.closest('[data-link]')?.getAttribute('data-link');
    if (id) onSelect(id); else { const svg = target.closest('svg'); if (svg) { const bounds = svg.getBoundingClientRect(); onYaw((e.clientX - bounds.left) / bounds.width * 360); } }
  }}>{image ? mapTree(tree, node => {
    if (typeName(node) === 'EquiScene') return <image href={image.stripUrl} x={0} y={0} width={width} height={width / 2} preserveAspectRatio="none" />;
    if (typeName(node) === 'BearingRuler' && c.yawToBearingErr === undefined) return React.cloneElement(node, { err: unknownNumber });
    if (node.props.className === 'aq-ov-mask') return React.cloneElement(node, { y: width / 2 * (1 - c.photographerMask!), height: width / 2 * c.photographerMask! });
    if (node.props.className === 'aq-ov-maskline') return React.cloneElement(node, { y1: width / 2 * (1 - c.photographerMask!), y2: width / 2 * (1 - c.photographerMask!) });
    if (node.key === 'maskt') return React.cloneElement(node, { y: width / 2 * (1 - c.photographerMask!) + parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--space-4')) }, 'Photographer area · masked, retained for the run');
    if (node.props.className?.includes('aq-ov-box') || node.props.className?.includes('aq-ov-text')) {
      const id = node.props['data-link']; const evidence = c.evidence.find(e => e.id === id);
      const box = React.cloneElement(node, { tabIndex: 0, role: 'button', 'aria-label': evidence?.obs ?? id, onKeyDown: (e: React.KeyboardEvent) => { if (e.key === 'Enter') onSelect(id); }, 'data-motion-id': id, 'data-box-kept': evidence?.payload.kept === false ? 'false' : 'true', 'data-dim': selected && selected !== id ? 'true' : undefined });
      const b = evidence?.box, shift = b && b.yaw < b.w / 2 ? width : b && b.yaw + b.w / 2 > 360 ? -width : 0;
      return shift ? <g key={node.key}>{box}{React.cloneElement(box, { transform: `translate(${shift},0)`, tabIndex: -1, 'aria-hidden': true })}</g> : box;
    }
    if (node.type === 'svg' && node.props.className === 'aq-pano-svg') {
      const children = React.Children.toArray(node.props.children);
      return React.cloneElement(node, {}, children.slice(0, 2), layers.seg && mask.url ? <image className="app-seg-tint" data-motion-target="measure" href={mask.url} width={width} height={width / 2} /> : null, children.slice(2));
    }
    return node;
  }) : <><EmptyState icon="photo" title="Panorama file not available for this log" body="Open this run’s JPEG to link the evidence to pixels." /><div className={stage ? 'stage-label aq-ink3' : 'console-micro aq-ink3'}>No image positions are drawn until the panorama is available.</div></>}{layers.seg && mask.error && <p className="console-micro aq-ink3" role="status">Segmentation tint unavailable: {mask.error} Scene shares remain available.</p>}</div>;
}
function useMask(input?: string, palette?: Record<string, unknown>) {
  const [state, setState] = useState<{ url?: string; error?: string }>({});
  useEffect(() => {
    let alive = true, decoded: IndexedMask | null = null;
    const abort = new AbortController(), asset = localAsset(input);
    setState({}); if (!asset) return;
    const paint = () => { if (alive && decoded) setState({ url: paintMask(decoded, palette) }); };
    const observer = new MutationObserver(paint); observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    void fetch(asset, { signal: abort.signal }).then(async response => {
      if (!response.ok) throw new Error('The mask file could not be loaded.');
      const bytes = new Uint8Array(await response.arrayBuffer()); if (bytes.length > 40 * 1024 * 1024) throw new Error('The mask exceeds the local file limit.');
      decoded = await decodeMask(bytes); if (alive) setState({ url: decoded ? paintMask(decoded, palette) : asset });
    }).catch(error => { if (alive && !abort.signal.aborted) setState({ error: error instanceof Error ? error.message : 'The mask could not be decoded.' }); });
    return () => { alive = false; abort.abort(); observer.disconnect(); };
  }, [input, palette]);
  return state;
}
function LoggedCompass(props: { c: CaseRecord; yaw: number }) {
  const { c, yaw } = props;
  return <>{mapTree(CompassDial({ yawToBearing: c.yawToBearing, err: c.yawToBearingErr, sun: c.sun, viewYaw: yaw }), node => {
    if (c.yawToBearing !== null && c.yawToBearingErr === undefined) {
      if (node.props.className === 'aq-dial-err') return null;
      if (node.type === 'svg') return React.cloneElement(node, { 'aria-label': `Image yaw 0 points to bearing ${c.yawToBearing}°; bearing error unknown` });
      if (node.props.className === 'aq-dial-cap') return React.cloneElement(node, {}, <span className="console-data">yaw 0 at {c.yawToBearing}° · bearing error unknown</span>);
    }
    return node;
  })}</>;
}
interface PannellumViewer {
  getYaw(): number; setYaw(yaw: number, animate?: boolean): void; setPitch(pitch: number, animate?: boolean): void;
  getHfov(): number; on(event: string, callback: () => void): void; destroy(): void;
  setUpdate(update: boolean): void; resize(): void;
}
declare global { interface Window { pannellum: { viewer(container: HTMLElement, config: Record<string, unknown>): PannellumViewer } } }
export function Viewer({ c, image, yaw, pitch = 0, selected, onYaw }: { c: CaseRecord; image?: PanoramaImage; yaw: number; pitch?: number; selected?: string; onYaw(yaw: number): void }) {
  const { ref, width } = useWidth<HTMLDivElement>(360); const host = useRef<HTMLDivElement>(null), viewer = useRef<PannellumViewer>();
  const onYawRef = useRef(onYaw); onYawRef.current = onYaw;
  const [failure, setFailure] = useState(false); const height = width * 0.58;
  useEffect(() => {
    if (!image || !host.current) return;
    setFailure(false);
    try {
      const v = window.pannellum.viewer(host.current, { type: 'equirectangular', panorama: image.canvas, dynamic: true, dynamicUpdate: true, autoLoad: true, showControls: false, yaw: yaw - 180, pitch, hfov: 90, autoRotate: false, compass: false, ignoreGPanoXMP: true, mouseZoom: true, keyboardZoom: false, disableKeyboardCtrl: true });
      viewer.current = v;
      v.on('load', () => v.setUpdate(false)); // upload the decoded canvas once, then render only on interaction
      const sync = () => onYawRef.current((v.getYaw() + 180 + 360) % 360);
      v.on('mouseup', sync); v.on('touchend', sync); v.on('animatefinished', sync); v.on('error', () => setFailure(true));
      // Pannellum emits movement events at rest; pointer movement samples only while dragging.
      let dragging = false;
      const down = () => { dragging = true; }, up = () => { dragging = false; sync(); }, move = () => { if (dragging) sync(); };
      const el = host.current; el.addEventListener('pointerdown', down); el.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
      return () => { el.removeEventListener('pointerdown', down); el.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); v.destroy(); viewer.current = undefined; };
    } catch { setFailure(true); }
  }, [image]);
  useEffect(() => { if (viewer.current && Math.abs(((viewer.current.getYaw() + 180 + 360) % 360) - yaw) > 0.2) viewer.current.setYaw(yaw - 180, false); }, [yaw]);
  useEffect(() => { viewer.current?.setPitch(pitch, false); }, [pitch]);
  useEffect(() => { viewer.current?.resize(); }, [width]);
  // Keep the original Viewer360 frame, captions, crosshair and logged overlays.
  const tree = Viewer360({ c: imageCase(c, image), yaw: Math.round(yaw * 10) / 10, pitch, width, height, selected, showBoxes: true });
  return <div ref={ref} className="app-viewer" tabIndex={0} aria-label="360° view; use arrow keys to turn" onKeyDown={e => { if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.preventDefault(); onYaw((yaw + (e.key === 'ArrowRight' ? 5 : -5) + 360) % 360); } }}>
    {mapTree(tree, node => {
      if (node.type === 'svg' && node.props.role === 'img') return <div className="app-viewer-image" style={{ height }}><div ref={host} className="app-pannellum" />{image && !failure ? <svg className="app-viewer-overlay" viewBox={`0 0 ${width} ${height}`} width={width} height={height}>{mapTree(node.props.children, child => typeName(child) === 'PerspScene' ? null : child)}</svg> : <EmptyState icon="camera" title={failure ? '360° viewer unavailable' : 'No panorama loaded'} body={failure ? 'The panorama strip and its crops are still available.' : 'Open this run’s JPEG to turn the view.'} />}</div>;
      return node;
    })}
  </div>;
}
export function Crop({ c, image, evidence }: { c: CaseRecord; image?: PanoramaImage; evidence?: Evidence }) {
  const { ref, width } = useWidth<HTMLDivElement>(200);
  const canvas = useMemo(() => image && evidence?.box ? angularCrop(image, evidence.box) : undefined, [image, evidence?.id, evidence?.box]);
  const target = evidence?.id ?? '';
  const cropUrl = localAsset(evidence?.payload.crop_url);
  const height = canvas ? Math.min(width * 0.65, width * canvas.height / canvas.width) : width * 0.65;
  const url = useMemo(() => canvas?.toDataURL('image/jpeg', 0.95), [canvas]);
  const tree = ZoomCrop({ c: imageCase(c, image), target, width, height });
  return <div ref={ref} data-motion-target="read">{evidence?.box && (image || cropUrl) ? mapTree(tree, node => node.type === 'svg' ? React.cloneElement(node, {}, <image href={cropUrl ?? url} width={width} height={height} preserveAspectRatio="xMidYMid meet" />, <rect x={0} y={0} width={width} height={height} className="aq-crop-box" fill="none" />) : node) : <EmptyState icon="zoom" title={evidence ? 'Position not logged' : 'Select a reading'} body={evidence ? 'No crop is drawn without a logged box and this panorama.' : 'Its pixels and source will appear here.'} />}</div>;
}
export function PanoramaColumn({ c, image, yaw, setYaw, selected, onSelect, layers, setLayers, showLayers, setShowLayers, view, setView, showCrop, setShowCrop }: { c: CaseRecord; image?: PanoramaImage; yaw: number; setYaw(n: number): void; selected?: string; onSelect(id: string): void; layers: Record<string, boolean>; setLayers(layers: Record<string, boolean>): void; showLayers: boolean; setShowLayers(open: boolean): void; view: 'panorama' | '360'; setView(view: 'panorama' | '360'): void; showCrop: boolean; setShowCrop(open: boolean): void }) {
  const selectedEvidence = c.evidence.find(e => e.id === selected);
  return <><Panel title="Panorama" aside={<Segmented label="Photo view" value={view} options={[{ id: 'panorama', label: 'Panorama' }, { id: '360', label: '360° view' }]} onChange={setView} />}>
    {view === 'panorama' ? <Strip c={c} image={image} yaw={yaw} layers={layers} selected={selected} onSelect={onSelect} onYaw={setYaw} /> : <Viewer c={c} image={image} yaw={yaw} selected={selected} onYaw={setYaw} />}
  </Panel>
  {selectedEvidence && <Disclosure title="Selected pixels" aside={selectedEvidence.kind.replace(/_/g, ' ')} open={showCrop} onOpenChange={setShowCrop}><Crop c={c} image={image} evidence={selectedEvidence} /></Disclosure>}
  <Disclosure title="Layers and bearings" aside="L" open={showLayers} onOpenChange={setShowLayers}>
    <p className="console-data-sm aq-ink3">{image ? `${image.width}×${image.height}` : 'Image not available'} · image yaw {Math.round(yaw)}°</p>
    <LayerToggles layers={layers} counts={{ boxes: String(c.detections.length), text: String(c.texts.length), sectors: c.viewCount === undefined ? 'not logged' : String(c.viewCount) }} onChange={(k: string, v: boolean) => setLayers({ ...layers, [k]: v })} />
    <LoggedCompass c={c} yaw={yaw} />
  </Disclosure></>;
}
export function referenceFor(e: Evidence) { return e.kind === 'match' ? record(e.payload.reference) : e.payload; }

/** A rectilinear query view sampled from the already decoded panorama, on demand. */
export function perspectiveImage(image: PanoramaImage, yaw: number, fov: number, width = 500, height = 320): string {
  const src = image.canvas.getContext('2d')!.getImageData(0, 0, image.canvas.width, image.canvas.height);
  const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
  const ctx = canvas.getContext('2d')!, output = ctx.createImageData(width, height), focal = width / 2 / Math.tan(fov * Math.PI / 360);
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const dx = (x - width / 2) / focal, dy = (height / 2 - y) / focal;
    const a = (yaw * Math.PI / 180 + Math.atan2(dx, 1) + Math.PI * 2) % (Math.PI * 2), p = Math.atan2(dy, Math.hypot(dx, 1));
    const sx = Math.floor(a / (Math.PI * 2) * src.width) % src.width, sy = Math.max(0, Math.min(src.height - 1, Math.floor((Math.PI / 2 - p) / Math.PI * src.height)));
    const s = (sy * src.width + sx) * 4, d = (y * width + x) * 4;
    output.data[d] = src.data[s]; output.data[d + 1] = src.data[s + 1]; output.data[d + 2] = src.data[s + 2]; output.data[d + 3] = 255;
  }
  ctx.putImageData(output, 0, 0); return canvas.toDataURL('image/jpeg', 0.95);
}
