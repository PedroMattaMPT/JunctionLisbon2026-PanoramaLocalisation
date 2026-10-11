import type { Box } from './model';
export interface PanoramaImage {
  width: number; height: number; original: ImageBitmap | HTMLImageElement;
  canvas: HTMLCanvasElement; stripUrl: string; localFile?: File; warning?: string; dispose(): void;
}
const MAX_BYTES = 40 * 1024 * 1024;
async function decode(blob: Blob): Promise<ImageBitmap | HTMLImageElement> {
  if (typeof createImageBitmap === 'function' && blob.type !== 'image/svg+xml') return createImageBitmap(blob, { imageOrientation: 'none' });
  const url = URL.createObjectURL(blob); const image = new Image(); image.src = url;
  try { await image.decode(); return image; } finally { URL.revokeObjectURL(url); }
}
export async function loadPanorama(blob: Blob, localFile?: File): Promise<PanoramaImage> {
  if (blob.size > MAX_BYTES) throw new Error('The panorama exceeds the local 40 MB file limit.');
  if (localFile) {
    const bytes = new Uint8Array(await blob.slice(0, 3).arrayBuffer());
    if (bytes[0] !== 255 || bytes[1] !== 216 || bytes[2] !== 255) throw new Error('This file is not a JPEG; its decoded content must be a 2:1 panorama.');
  }
  const image = await decode(blob); const width = image instanceof HTMLImageElement ? image.naturalWidth : image.width, height = image instanceof HTMLImageElement ? image.naturalHeight : image.height;
  const release = () => { if ('close' in image) image.close(); };
  if (width / height !== 2) { release(); throw new Error(`Decoded size ${width}×${height} is not 2:1; this panorama was refused.`); }
  if (width * height > 48_000_000) { release(); throw new Error('Decoded image exceeds the 48 million pixel limit.'); }
  // One decode, one bounded texture and one downscaled strip. Original pixels stay available for crops.
  const canvas = document.createElement('canvas'); canvas.width = Math.min(4096, width); canvas.height = canvas.width / 2;
  canvas.getContext('2d', { willReadFrequently: true })!.drawImage(image, 0, 0, canvas.width, canvas.height);
  const strip = document.createElement('canvas'); strip.width = Math.min(1600, width); strip.height = strip.width / 2;
  strip.getContext('2d')!.drawImage(canvas, 0, 0, strip.width, strip.height);
  const stripBlob = await new Promise<Blob>((resolve, reject) => strip.toBlob(b => b ? resolve(b) : reject(new Error('The panorama preview could not be prepared.')), 'image/jpeg', 0.9));
  const stripUrl = URL.createObjectURL(stripBlob);
  return { width, height, original: image, canvas, stripUrl, localFile, warning: width === 6080 && height === 3040 ? undefined : `Decoded size ${width}×${height}; accepted as 2:1, expected 6080×3040.`, dispose: () => { release(); URL.revokeObjectURL(stripUrl); canvas.width = 0; strip.width = 0; } };
}
export function angularCrop(image: PanoramaImage, box: Box): HTMLCanvasElement {
  const output = document.createElement('canvas');
  const sx = ((box.yaw - box.w / 2) / 360 * image.width % image.width + image.width) % image.width;
  const sy = Math.max(0, (90 - box.pitch - box.h / 2) / 180 * image.height);
  const sw = box.w / 360 * image.width, sh = Math.min(image.height, (90 - box.pitch + box.h / 2) / 180 * image.height) - sy;
  output.width = Math.max(1, Math.min(1600, Math.round(sw))); output.height = Math.max(1, Math.round(output.width * sh / sw));
  const ctx = output.getContext('2d')!; const first = Math.min(sw, image.width - sx);
  ctx.drawImage(image.original, sx, sy, first, sh, 0, 0, output.width * first / sw, output.height);
  if (first < sw) ctx.drawImage(image.original, 0, sy, sw - first, sh, output.width * first / sw, 0, output.width * (sw - first) / sw, output.height);
  return output;
}
