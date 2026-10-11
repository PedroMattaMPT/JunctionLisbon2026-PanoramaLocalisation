import { arr, finite, record, type Question } from './model';

/** South/west/north/east around a question's options: zone polygons (any depth), else their extent; place points with their radius. "None of these" adds nothing. */
export function questionBounds(q?: Question) {
  let s = 90, w = 180, n = -90, e = -180, any = false;
  const add = (lat: number, lng: number) => { if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return; s = Math.min(s, lat); n = Math.max(n, lat); w = Math.min(w, lng); e = Math.max(e, lng); any = true; };
  const walk = (v: unknown): void => { const a = arr(v); if (a.length >= 2 && finite(a[0]) !== null && finite(a[1]) !== null) add(a[1] as number, a[0] as number); else a.forEach(walk); };
  for (const o of q?.options ?? []) {
    if (o.none) continue;
    const coords = record(o.zone).coordinates;
    if (Array.isArray(coords)) walk(coords); else if (o.extent) { add(o.extent.south, o.extent.west); add(o.extent.north, o.extent.east); }
    if (o.point) {
      const [lat, lng] = o.point; add(lat, lng);
      if (o.radius && !o.zone && !o.extent) { const dlat = o.radius / 111320, dlng = o.radius / (111320 * Math.max(0.2, Math.cos(lat * Math.PI / 180))); add(lat - dlat, lng - dlng); add(lat + dlat, lng + dlng); }
    }
  }
  return any ? { south: s, west: w, north: n, east: e } : undefined;
}
/** The map view that shows every option of an open question. */
export function questionView(q?: Question): { lat: number; lng: number; span: number } | undefined {
  const b = questionBounds(q); if (!b) return;
  // span is the map's width in degrees; a 0.78-high map at ~40° N shows about 0.6 of it in latitude.
  return { lat: (b.south + b.north) / 2, lng: (b.west + b.east) / 2, span: Math.max(b.east - b.west, (b.north - b.south) * 1.75, 0.004) * 1.3 };
}
