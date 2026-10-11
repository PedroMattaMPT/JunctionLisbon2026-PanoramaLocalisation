import { afterEach, expect, it, vi } from 'vitest';
import { alignmentOffset, angleDelta, distanceWarning, streetBearing, streetYaw, wrap } from '../src/streetview-model';
import { streetImagery } from '../src/data';

afterEach(() => vi.unstubAllGlobals());
it('maps compass bearings to the existing image-yaw convention, across north and the seam', () => {
  expect(streetYaw(90, 90)).toBe(180);
  expect(streetYaw(0, 90)).toBe(90);
  expect(streetBearing(90, 90)).toBe(0);
  expect(streetBearing(streetYaw(359, 4), 4)).toBe(359);
  expect(wrap(-1)).toBe(359);
  expect(angleDelta(2, 358)).toBe(4);
});
it('preserves alignment when either panorama crosses the seam', () => {
  const offset = alignmentOffset(350, 10);
  expect(offset).toBe(20);
  expect(wrap(355 + offset)).toBe(15);
  expect(wrap(5 - offset)).toBe(345);
});
it('warns about nearby pictures without claiming an exact camera position', () => {
  expect(distanceWarning(50)).toBe('');
  expect(distanceWarning(240)).toContain('240 m away');
  expect(distanceWarning(1001)).toContain('No street panorama within 1 km');
});
it('requests coordinates only and accepts only the local image proxy with a safe source link', async () => {
  const valid = { provider: 'panoramax', id: 'sample', lat: 48.85, lng: 2.35, distance_m: 12,
    captured_at: '2025-07-08', heading_deg: 209, image_url: '/api/streetview/image/panoramax/sample/sd', page_url: 'https://panoramax.xyz/#pic=sample', attribution: 'Producer', license: 'CC-BY-SA' };
  const request = vi.fn(async () => new Response(JSON.stringify({ pictures: [valid,
    { ...valid, image_url: 'https://external.example/photo.jpg' }, { ...valid, distance_m: 1001 },
    { ...valid, page_url: 'javascript:alert(1)' }] })));
  vi.stubGlobal('fetch', request);
  const signal = new AbortController().signal, photos = await streetImagery(48.85, 2.35, signal);
  expect(photos).toHaveLength(2);
  expect(photos[0].image_url).toBe(valid.image_url);
  expect(photos[1].page_url).toBeNull();
  expect(request.mock.calls[0]).toEqual(['/api/streetview/nearest?lat=48.85&lng=2.35', { signal }]);
});
it('leaves offline failure actionable', async () => {
  vi.stubGlobal('fetch', async () => new Response('', { status: 503 }));
  await expect(streetImagery(38.7, -9.1, new AbortController().signal)).rejects.toThrow('Google Street View');
});
it('distinguishes an unreachable imagery provider from an empty coverage search', async () => {
  vi.stubGlobal('fetch', async () => new Response(JSON.stringify({ pictures: [], unavailable: ['panoramax'] })));
  await expect(streetImagery(38.7, -9.1, new AbortController().signal)).rejects.toThrow('could not be reached');
  vi.stubGlobal('fetch', async () => new Response(JSON.stringify({ pictures: [], unavailable: [] })));
  await expect(streetImagery(38.7, -9.1, new AbortController().signal)).resolves.toEqual([]);
});
