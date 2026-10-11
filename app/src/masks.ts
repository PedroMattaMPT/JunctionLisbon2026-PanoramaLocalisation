import { record, str } from './model';

export const MASK_CLASSES = ['sky', 'building', 'grass', 'tree', 'road', 'water', 'ground', 'masked'] as const;
export interface IndexedMask { width: number; height: number; indices: Uint8Array }
interface PngMask { width: number; height: number; depth: number; compressed: Uint8Array }

// PNG class indices must survive palette colour collisions and browser colour management.
// Read index scanlines rather than trying to infer classes from decoded RGB colours.
export function readMaskPng(bytes: Uint8Array): PngMask | null {
  const signature = [137, 80, 78, 71, 13, 10, 26, 10];
  if (!signature.every((v, i) => bytes[i] === v)) return null;
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let width = 0, height = 0, depth = 0, indexed = false, total = 0;
  const parts: Uint8Array[] = [];
  for (let offset = 8; offset + 12 <= bytes.length;) {
    const length = view.getUint32(offset), end = offset + 12 + length;
    if (end > bytes.length) throw new Error('The segmentation PNG is incomplete.');
    const type = String.fromCharCode(...bytes.subarray(offset + 4, offset + 8));
    if (type === 'IHDR') {
      if (length !== 13) throw new Error('The segmentation PNG header is invalid.');
      width = view.getUint32(offset + 8); height = view.getUint32(offset + 12);
      depth = bytes[offset + 16]; const color = bytes[offset + 17];
      indexed = color === 3 || color === 0;
      if (!indexed) return null; // An already colourised PNG needs no index translation.
      if (!width || !height || width > 4096 || height > 2048 || width !== height * 2) throw new Error('The segmentation mask must be a strip-sized 2:1 image.');
      if (bytes[offset + 18] !== 0 || bytes[offset + 19] !== 0 || bytes[offset + 20] !== 0 || !(color === 3 ? [1, 2, 4, 8] : [8]).includes(depth)) throw new Error('Use a non-interlaced indexed PNG or an 8-bit grayscale class mask.');
    }
    if (type === 'IDAT') { parts.push(bytes.subarray(offset + 8, offset + 8 + length)); total += length; }
    offset = end;
    if (type === 'IEND') break;
  }
  if (!indexed || !parts.length) throw new Error('The segmentation PNG has no class data.');
  const compressed = new Uint8Array(total); let offset = 0;
  for (const part of parts) { compressed.set(part, offset); offset += part.length; }
  return { width, height, depth, compressed };
}
export function unpackMask(width: number, height: number, depth: number, scanlines: Uint8Array): IndexedMask {
  const stride = Math.ceil(width * depth / 8);
  if (scanlines.length !== height * (stride + 1)) throw new Error('The segmentation PNG scanlines have the wrong size.');
  const rows = new Uint8Array(height * stride), indices = new Uint8Array(width * height);
  const paeth = (a: number, b: number, c: number) => { const p = a + b - c, aa = Math.abs(p - a), bb = Math.abs(p - b), cc = Math.abs(p - c); return aa <= bb && aa <= cc ? a : bb <= cc ? b : c; };
  for (let y = 0; y < height; y++) {
    const filter = scanlines[y * (stride + 1)]; if (filter > 4) throw new Error('The segmentation PNG uses an invalid filter.');
    for (let x = 0; x < stride; x++) {
      const left = x ? rows[y * stride + x - 1] : 0, up = y ? rows[(y - 1) * stride + x] : 0, diagonal = x && y ? rows[(y - 1) * stride + x - 1] : 0;
      const predictor = [0, left, up, Math.floor((left + up) / 2), paeth(left, up, diagonal)][filter];
      rows[y * stride + x] = (scanlines[y * (stride + 1) + x + 1] + predictor) & 255;
    }
    for (let x = 0; x < width; x++) indices[y * width + x] = (rows[y * stride + Math.floor(x * depth / 8)] >> (8 - depth - x * depth % 8)) & ((1 << depth) - 1);
  }
  return { width, height, indices };
}
export async function decodeMask(bytes: Uint8Array): Promise<IndexedMask | null> {
  const png = readMaskPng(bytes); if (!png) return null;
  if (typeof DecompressionStream === 'undefined') throw new Error('This browser cannot decode class masks; scene shares remain available.');
  const expected = png.height * (Math.ceil(png.width * png.depth / 8) + 1), output = new Uint8Array(expected);
  const reader = new Blob([png.compressed]).stream().pipeThrough(new DecompressionStream('deflate')).getReader(); let offset = 0;
  try {
    for (;;) { const { done, value } = await reader.read(); if (done) break; if (offset + value.length > expected) throw new Error('The segmentation PNG exceeds its logged dimensions.'); output.set(value, offset); offset += value.length; }
  } finally { await reader.cancel(); }
  if (offset !== expected) throw new Error('The segmentation PNG is incomplete.');
  return unpackMask(png.width, png.height, png.depth, output);
}
export function paintMask(mask: IndexedMask, palette: unknown): string {
  const css = getComputedStyle(document.documentElement), swatch = document.createElement('canvas'); swatch.width = 1; swatch.height = 1;
  const swatchContext = swatch.getContext('2d', { willReadFrequently: true })!;
  const classes = Object.keys(record(palette)).length ? record(palette) : Object.fromEntries(MASK_CLASSES.map((name, index) => [index, name]));
  const colours = new Map<number, Uint8ClampedArray>();
  for (const [index, value] of Object.entries(classes)) {
    const name = str(value); if (!(MASK_CLASSES as readonly string[]).includes(name)) continue;
    swatchContext.clearRect(0, 0, 1, 1); swatchContext.fillStyle = css.getPropertyValue(`--seg-${name}`).trim(); swatchContext.fillRect(0, 0, 1, 1);
    colours.set(Number(index), swatchContext.getImageData(0, 0, 1, 1).data);
  }
  const canvas = document.createElement('canvas'); canvas.width = mask.width; canvas.height = mask.height;
  const ctx = canvas.getContext('2d')!, pixels = ctx.createImageData(mask.width, mask.height);
  mask.indices.forEach((index, i) => { const colour = colours.get(index); if (colour) pixels.data.set(colour, i * 4); }); // unmapped and 255 stay transparent
  ctx.putImageData(pixels, 0, 0); return canvas.toDataURL('image/png');
}
