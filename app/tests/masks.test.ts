import { describe, expect, it } from 'vitest';
import { readMaskPng, unpackMask, decodeMask } from '../src/masks';
import { deflateSync } from 'node:zlib';

function png(depth: number, color: number, rows: number[]) {
  const header = Buffer.alloc(13); header.writeUInt32BE(4, 0); header.writeUInt32BE(2, 4); header[8] = depth; header[9] = color;
  const chunk = (name: string, data: Uint8Array) => { const size = Buffer.alloc(4); size.writeUInt32BE(data.length); return Buffer.concat([size, Buffer.from(name), data, Buffer.alloc(4)]); };
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', header), chunk('IDAT', deflateSync(Buffer.from(rows))), chunk('IEND', new Uint8Array())]);
}
describe('class mask indices', () => {
  it('keeps palette indices even when palette entries could share colours', async () => {
    const result = await decodeMask(png(8, 3, [0, 0, 1, 2, 255, 0, 4, 5, 6, 7]));
    expect(result?.indices).toEqual(new Uint8Array([0, 1, 2, 255, 4, 5, 6, 7]));
  });
  it('unpacks 2-bit rows and reverses PNG filters across rows', () => {
    expect(unpackMask(4, 2, 2, new Uint8Array([0, 27, 2, 201])).indices).toEqual(new Uint8Array([0, 1, 2, 3, 3, 2, 1, 0]));
    for (let filter = 0; filter <= 4; filter++) {
      const rows = filter === 0 ? [0, 10, 20, 30, 40, 0, 50, 60, 70, 80] : filter === 1 ? [1, 10, 10, 10, 10, 1, 50, 10, 10, 10] : filter === 2 ? [2, 10, 20, 30, 40, 2, 40, 40, 40, 40] : filter === 3 ? [3, 10, 15, 20, 25, 3, 45, 25, 25, 25] : [4, 10, 10, 10, 10, 4, 40, 10, 10, 10];
      expect(unpackMask(4, 2, 8, new Uint8Array(rows)).indices).toEqual(new Uint8Array([10, 20, 30, 40, 50, 60, 70, 80]));
    }
  });
  it('does not reinterpret already colourised assets and refuses incomplete or oversized masks', () => {
    expect(readMaskPng(png(8, 6, []))).toBeNull(); expect(readMaskPng(new TextEncoder().encode('<svg/>'))).toBeNull();
    expect(() => readMaskPng(png(8, 0, []).subarray(0, 22))).toThrow('incomplete');
    expect(() => unpackMask(4, 2, 8, new Uint8Array(1))).toThrow('wrong size');
    const oversized = png(8, 0, []); oversized.writeUInt32BE(8192, 16); expect(() => readMaskPng(oversized)).toThrow('strip-sized');
  });
});
