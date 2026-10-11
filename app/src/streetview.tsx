import React, { useEffect, useRef, useState } from 'react';
import { Button, EmptyState, Toggle } from '@ds/base';
import { Viewer } from './panorama';
import { loadPanorama, type PanoramaImage } from './images';
import { streetImagery, type StreetPicture } from './data';
import type { CaseRecord } from './model';
import { emptyCase } from './reducer';
import { coordinates, distance } from './format';
import { Thinking } from './activity';
import { alignmentOffset, distanceWarning, streetBearing, streetYaw, wrap } from './streetview-model';
import { LocationLinks } from './location-links';

export type LocationView = 'map' | 'streetview' | 'compare';
const streetCase = emptyCase();
function useStreetImagery(point: { lat: number; lng: number }) {
  const [pictures, setPictures] = useState<StreetPicture[]>([]), [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(true), [error, setError] = useState(''), [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let alive = true;
    const abort = new AbortController(), timeout = setTimeout(() => abort.abort(), 30000);
    setPictures([]); setIndex(0); setLoading(true); setError('');
    void streetImagery(point.lat, point.lng, abort.signal).then(pictures => { if (alive) setPictures(pictures); }).catch(error => {
      if (alive) setError(abort.signal.aborted ? 'Street imagery took too long to respond.' : error instanceof Error ? error.message : 'Street imagery unavailable.');
    }).finally(() => { clearTimeout(timeout); if (alive) setLoading(false); });
    return () => { alive = false; clearTimeout(timeout); abort.abort(); };
  }, [point.lat, point.lng, attempt]);
  return { pictures, photo: pictures[index], index, setIndex, loading, error, retry: () => setAttempt(value => value + 1) };
}
function useStreetImage(photo?: StreetPicture) {
  const [state, setState] = useState<{ url?: string; image?: PanoramaImage; error: string }>({ error: '' });
  useEffect(() => {
    let alive = true, loaded: PanoramaImage | undefined;
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 15000);
    setState({ url: photo?.image_url, error: '' });
    if (photo) void fetch(photo.image_url, { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error('This street photo could not be loaded. Try another nearby picture.');
      const blob = await response.blob();
      if (blob.size > 25 * 1024 * 1024) throw new Error('This street photo is too large.');
      loaded = await loadPanorama(blob);
      if (alive) setState({ url: photo.image_url, image: loaded, error: '' }); else loaded.dispose();
    }).catch(error => { if (alive) setState({ url: photo.image_url, error: controller.signal.aborted ? 'The street photo took too long to load.' : error.message }); }).finally(() => clearTimeout(timeout));
    return () => { alive = false; clearTimeout(timeout); controller.abort(); loaded?.dispose(); };
  }, [photo?.image_url]);
  return state.url === photo?.image_url ? state : { error: '', image: undefined };
}
function sourceDate(value: string | number | null) {
  if (value === null) return 'Date unknown';
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? 'Date unknown' : date.toLocaleDateString('en-GB', { month: 'short', year: 'numeric', timeZone: 'UTC' });
}
function StreetPosition({ point, photo, bearing }: { point: { lat: number; lng: number }; photo: StreetPicture; bearing?: number }) {
  const dx = (photo.lng - point.lng) * 111320 * Math.cos(point.lat * Math.PI / 180), dy = (photo.lat - point.lat) * 111320;
  const scale = 62 / Math.max(25, Math.abs(dx), Math.abs(dy)), x = 90 + dx * scale, y = 90 - dy * scale;
  return <svg className="street-position" viewBox="0 0 180 180" role="img" aria-label={`Street photo ${Math.round(photo.distance_m)} metres from the estimate; north is up`}>
    <circle cx="90" cy="90" r="64" className="street-position-ring" /><path d="M90 14v152M14 90h152" className="street-position-grid" />
    <text x="90" y="10" textAnchor="middle">N</text><line x1="90" y1="90" x2={x} y2={y} className="street-position-line" />
    {bearing !== undefined && <path d={`M${x} ${y}l-14 -32h28Z`} transform={`rotate(${bearing},${x},${y})`} className="street-position-cone" />}
    <circle cx="90" cy="90" r="5" className="street-position-estimate" /><circle cx={x} cy={y} r="5" className="street-position-photo" />
  </svg>;
}

/** Local, read-only visual comparison; never writes events or changes the answer. */
export function StreetWorkspace({ c, image, point, mode, yaw, setYaw }: { c: CaseRecord; image?: PanoramaImage; point: { lat: number; lng: number }; mode: Exclude<LocationView, 'map'>; yaw: number; setYaw(yaw: number): void }) {
  const nearby = useStreetImagery(point), { photo } = nearby, street = useStreetImage(photo);
  const [unavailablePhotos, setUnavailablePhotos] = useState<string[]>([]);
  useEffect(() => { setUnavailablePhotos([]); }, [nearby.pictures]);
  useEffect(() => {
    if (!street.error || !photo || unavailablePhotos.includes(photo.image_url)) return;
    const failed = [...unavailablePhotos, photo.image_url];
    setUnavailablePhotos(failed);
    const next = nearby.pictures.findIndex(picture => !failed.includes(picture.image_url));
    if (next >= 0) nearby.setIndex(next);
  }, [street.error, photo, nearby.pictures, nearby.setIndex, unavailablePhotos]);
  const [streetAngle, setStreetAngle] = useState(180), [fov, setFov] = useState(90), [streetFov, setStreetFov] = useState(90);
  const [pitch, setPitch] = useState(0), [streetPitch, setStreetPitch] = useState(0);
  const [offset, setOffset] = useState<number>(), [linked, setLinked] = useState(false), [flicker, setFlicker] = useState(false);
  const ownYaw = useRef(yaw); ownYaw.current = yaw;
  const comparing = mode === 'compare', ready = !!street.image && !!image;
  useEffect(() => {
    setFlicker(false); setStreetFov(90); setStreetPitch(0);
    if (c.yawToBearing !== null && photo?.heading_deg != null) {
      const angle = streetYaw(ownYaw.current + c.yawToBearing, photo.heading_deg);
      setStreetAngle(angle); setOffset(alignmentOffset(ownYaw.current, angle)); setLinked(true);
    } else { setStreetAngle(180); setOffset(undefined); setLinked(false); }
  }, [photo?.id, c.id, c.yawToBearing]);
  useEffect(() => {
    const reset = () => setFlicker(false);
    const key = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest('input,textarea,[contenteditable="true"]')) return;
      // Modal review/help owns the keyboard; the comparison inside Details may use it.
      if (document.querySelector('[role="dialog"]:not(.focus-sheet)')) return;
      if (e.key.toLowerCase() === 'f' && comparing && ready) { e.preventDefault(); setFlicker(e.type === 'keydown'); }
      if (e.type === 'keydown' && (e.key === '[' || e.key === ']') && nearby.pictures.length > 1) { e.preventDefault(); nearby.setIndex(index => (index + (e.key === ']' ? 1 : -1) + nearby.pictures.length) % nearby.pictures.length); }
    };
    window.addEventListener('keydown', key); window.addEventListener('keyup', key); window.addEventListener('blur', reset);
    return () => { window.removeEventListener('keydown', key); window.removeEventListener('keyup', key); window.removeEventListener('blur', reset); };
  }, [comparing, ready, nearby.pictures.length]);
  const originalTurn = (angle: number) => { setYaw(angle); if (linked && offset !== undefined) setStreetAngle(wrap(angle + offset)); };
  const streetTurn = (angle: number) => { setStreetAngle(angle); if (linked && offset !== undefined) setYaw(wrap(angle - offset)); };
  // Arrow keys / strip selection can change the original outside the viewer.
  useEffect(() => { if (linked && offset !== undefined) setStreetAngle(wrap(yaw + offset)); }, [yaw, linked, offset]);
  const originalZoom = (value: number) => { setFov(value); if (linked) setStreetFov(value); };
  const streetZoom = (value: number) => { setStreetFov(value); if (linked) setFov(value); };
  const originalPitch = (value: number) => { setPitch(value); if (linked) setStreetPitch(value); };
  const referencePitch = (value: number) => { setStreetPitch(value); if (linked) setPitch(value); };
  const lock = () => { setOffset(alignmentOffset(yaw, streetAngle)); setLinked(true); setStreetFov(fov); setStreetPitch(pitch); };
  const bearing = photo?.heading_deg != null ? streetBearing(streetAngle, photo.heading_deg) : undefined;
  const unavailable = nearby.error || (street.error && unavailablePhotos.length === nearby.pictures.length ? 'Nearby street photos could not be loaded. Open Google Maps or Google Street View below.' : street.error);
  return <section className={`street-workspace ${comparing ? 'is-compare' : ''}`} aria-label={comparing ? 'Original panorama and street view comparison' : 'Street view at the estimate'}>
    <header className="street-heading"><div><h2 className="console-title">{comparing ? 'Does the scene match?' : 'At the estimated location'}</h2><p className="console-data-sm aq-ink3">{coordinates(point.lat, point.lng)}</p></div>{comparing && ready && <span className={`street-link-state console-label ${linked ? 'is-linked' : ''}`}>{linked ? 'Linked views' : 'Align the views'}</span>}</header>
    <div className={`street-pair ${flicker ? 'is-flickering' : ''}`}>
      {comparing && <div className="street-original"><header className="console-label"><span className="street-photo-dot" />Original photo<span className="console-data-sm aq-ink3">{Math.round(yaw)}°</span></header><Viewer c={c} image={image} yaw={yaw} pitch={pitch} hfov={fov} onYaw={originalTurn} onHfov={originalZoom} onPitch={originalPitch} aspect={0.68} showBoxes={false} /></div>}
      <div className="street-reference"><header className="console-label"><span className="street-reference-dot" />Street panorama<span className="console-data-sm aq-ink3">{bearing === undefined ? 'Heading unknown' : `${Math.round(bearing)}°`}</span></header>
        {street.image ? <Viewer c={streetCase} image={street.image} yaw={streetAngle} pitch={streetPitch} hfov={streetFov} onYaw={streetTurn} onHfov={streetZoom} onPitch={referencePitch} aspect={comparing ? 0.68 : 0.55} showBoxes={false} /> : <div className="street-empty">{nearby.loading || photo && !unavailable ? <><Thinking label="Loading street panorama" /><span className="street-skeleton" aria-hidden="true" /></> : <><EmptyState icon="camera" title={unavailable ? 'Street imagery unavailable' : 'No street panorama within 1 km'} body={unavailable || 'There may still be Google Street View coverage at this coordinate.'} /><Button variant="quiet" onClick={nearby.retry}>Try again</Button></>}</div>}
      </div>
    </div>
    {comparing && ready && <div className="street-tools"><Button variant={linked ? 'quiet' : 'primary'} onClick={lock}>{offset === undefined ? 'Lock alignment' : 'Re-align'}</Button><Toggle label="Link turning and zoom" on={linked} onChange={(value: boolean) => { if (value) lock(); else setLinked(false); }} /><button type="button" className="aq-btn aq-btn-quiet console-label" aria-pressed={flicker} onKeyDown={e => { if (['Enter', ' '].includes(e.key)) { e.preventDefault(); setFlicker(true); } }} onKeyUp={e => { if (['Enter', ' '].includes(e.key)) setFlicker(false); }} onPointerDown={e => { e.currentTarget.setPointerCapture(e.pointerId); setFlicker(true); }} onPointerUp={() => setFlicker(false)} onPointerCancel={() => setFlicker(false)} onBlur={() => setFlicker(false)}>Hold to flicker · F</button><span className="console-micro aq-ink3">{offset === undefined ? 'Turn both views to the same feature, then lock.' : 'Drag either view. Scroll to zoom.'}</span></div>}
    {photo && <div className="street-info"><StreetPosition point={point} photo={photo} bearing={bearing} /><div className="street-info-copy"><p className="console-heading">{photo.provider === 'mock' ? 'Invented mock image' : photo.provider === 'panoramax' ? 'Panoramax' : 'Mapillary'} <span className="console-body aq-ink2">· {distance(photo.distance_m)} from the estimate · {sourceDate(photo.captured_at)}</span></p>{distanceWarning(photo.distance_m) && <p className="console-body street-distance-warning">{distanceWarning(photo.distance_m)}</p>}<p className="console-micro aq-ink3">{photo.attribution} · {photo.license}{photo.page_url && <> · <a href={photo.page_url} target="_blank" rel="noopener noreferrer">View source ↗</a></>}</p>{nearby.pictures.length > 1 && <div className="street-nearby"><Button variant="quiet" icon="back" disabled={nearby.pictures.length < 2} onClick={() => nearby.setIndex(index => (index - 1 + nearby.pictures.length) % nearby.pictures.length)}>Previous</Button><span className="console-data-sm">{nearby.index + 1} / {nearby.pictures.length}</span><Button variant="quiet" icon="forward" onClick={() => nearby.setIndex(index => (index + 1) % nearby.pictures.length)}>Next</Button>{nearby.pictures.map((entry, index) => <button key={entry.id} className="street-nearby-photo console-data-sm" type="button" aria-label={`Nearby photo ${index + 1}, ${distance(entry.distance_m)} away`} aria-pressed={nearby.index === index} onClick={() => nearby.setIndex(index)}>{distance(entry.distance_m)}</button>)}</div>}</div></div>}
    <LocationLinks point={point} osm /><p className="console-micro aq-ink3 street-footnote">For your eyes only: nothing here is sent to the agent.</p>
  </section>;
}
