import { h, cx } from './rt';

/**
 * Aqui icon set — drawn on a 16px grid, 1.5px stroke, square caps, mitred joins.
 * Each entry is a list of SVG elements: ['p', d] path (stroked), ['f', d] filled path,
 * ['c', cx, cy, r] stroked circle, ['C', cx, cy, r] filled circle.
 */
export const ICONS: Record<string, any[]> = {
  // actors
  model: [['p', 'M1.5 8c1.8-3.2 4-4.5 6.5-4.5s4.7 1.3 6.5 4.5c-1.8 3.2-4 4.5-6.5 4.5S3.3 11.2 1.5 8z'], ['c', 8, 8, 2.25], ['C', 8, 8, 0.9]],
  solver: [['p', 'M8 2v12M4 14h8M2.5 4.5h11'], ['p', 'M2.5 4.5L1 9h3L2.5 4.5zM13.5 4.5L12 9h3l-1.5-4.5z']],
  team: [['c', 8, 5, 2.75], ['p', 'M2.5 14.5c.6-3 2.8-4.75 5.5-4.75s4.9 1.75 5.5 4.75']],
  // evidence kinds
  text: [['p', 'M2 2.5h12v11H2z'], ['p', 'M5 5.5h6M8 5.5v5.5']],
  object: [['p', 'M2 5V2h3M11 2h3v3M14 11v3h-3M5 14H2v-3'], ['p', 'M6 6h4v4H6z']],
  checklist: [['p', 'M7 4h7M7 8h7M7 12h7'], ['p', 'M1.75 4l1.25 1.25L5 3M1.75 8l1.25 1.25L5 7'], ['c', 3.25, 12, 1.1]],
  measure: [['c', 8, 8, 6], ['p', 'M8 2v6h6']],
  sun: [['c', 8, 8, 2.75], ['p', 'M8 1v2M8 13v2M1 8h2M13 8h2M3 3l1.4 1.4M11.6 11.6L13 13M13 3l-1.4 1.4M4.4 11.6L3 13']],
  compass: [['c', 8, 8, 6.25], ['f', 'M8 3.5l1.6 4.5H6.4L8 3.5z'], ['p', 'M6.4 8L8 12.5 9.6 8']],
  language: [['p', 'M2 2.5h12v8.5H8l-3 2.5V11H2z'], ['p', 'M5 6h6M5 8.5h3.5']],
  neighbour: [['p', 'M4.5 1.5h10v8h-10z'], ['p', 'M1.5 5.5v9h10'], ['p', 'M6.5 8l2.5-2.5 2 2 1.5-1.5 2 2']],
  region: [['p', 'M2 4l4-2 4 2 4-2v10l-4 2-4-2-4 2z'], ['p', 'M6 2v10M10 4v10']],
  name: [['p', 'M8 15V1.5'], ['p', 'M8 2.5h5.5l1.5 2-1.5 2H8M8 8H2.5L1 10l1.5 2H8']],
  contradiction: [['p', 'M2 5.5h10.5M10 3l2.5 2.5L10 8M14 10.5H3.5M6 8l-2.5 2.5L6 13']],
  infer: [['C', 8, 3.5, 1.6], ['C', 3.5, 12, 1.6], ['C', 12.5, 12, 1.6]],
  estimate: [['p', 'M2 6c1.5-1.5 3-1.5 4.5 0s3 1.5 4.5 0 2.5-1.2 3-1M2 10.5c1.5-1.5 3-1.5 4.5 0s3 1.5 4.5 0 2.5-1.2 3-1']],
  // stage status
  queued: [['c', 8, 8, 4.5]],
  running: [['C', 8, 8, 4.5]],
  done: [['p', 'M3 8.5l3 3 7-7']],
  skipped: [['p', 'M2 11.5c1.5-5 10.5-5 12 0'], ['p', 'M11.5 9.5l2.5 2 1-3'], ['c', 8, 12.5, 1.25]],
  failed: [['p', 'M3.5 3.5l9 9M12.5 3.5l-9 9']],
  timeout: [['p', 'M4 1.5h8M4 14.5h8M5 1.5c0 4 6 4.5 6 6.5s-6 2.5-6 6.5M11 1.5c0 4-6 4.5-6 6.5s6 2.5 6 6.5']],
  // polarity (filled shapes so they survive print and colour-blindness)
  support: [['f', 'M8 3l5.5 9h-11z']],
  contra: [['f', 'M8 13L2.5 4h11z']],
  neutral: [['C', 8, 8, 3.25]],
  // human loop and cost
  cost: [['p', 'M14.5 4.5v7H5.5L1.5 8l4-3.5z'], ['c', 5.75, 8, 1]],
  question: [['p', 'M2 2h12v12H2z'], ['p', 'M6 6.25c0-1.25.9-2 2-2s2 .75 2 1.9c0 1.6-2 1.6-2 3.1'], ['C', 8, 11.5, 0.8]],
  cue: [['p', 'M2 13.5h3l8.5-8.5-3-3L2 10.5z'], ['p', 'M9 3.5l3 3']],
  skip: [['p', 'M1.5 11c2-5.5 11-5.5 13 0'], ['p', 'M12 8.5l2.5 2.5L15.5 8']],
  clock: [['c', 8, 8, 6.25], ['p', 'M8 4.5V8l2.5 2']],
  key: [['p', 'M1.5 3.5h13v9h-13z'], ['p', 'M4 6.5h1M7.5 6.5h1M11 6.5h1M5 9.5h6']],
  // navigation and actions
  link: [['p', 'M9 2h5v5M14 2L7 9'], ['p', 'M12 10v4H2V4h4']],
  copy: [['p', 'M5.5 5.5h8v8h-8z'], ['p', 'M10.5 2.5h-8v8']],
  qr: [['p', 'M2 2h5v5H2zM9 2h5v5H9zM2 9h5v5H2z'], ['p', 'M9.5 9.5h1.5v1.5H9.5zM12.5 12.5H14V14h-1.5zM9.5 12.5H11V14H9.5zM12.5 9.5H14V11h-1.5z']],
  download: [['p', 'M8 1.5v9M4.5 7l3.5 3.5L11.5 7M2 12v2.5h12V12']],
  drop: [['p', 'M8 10V1.5M4.5 5L8 1.5 11.5 5'], ['p', 'M1.5 9.5v5h13v-5']],
  submit: [['p', 'M2 8h9.5M8 4.5L11.5 8 8 11.5'], ['p', 'M14 2v12']],
  layers: [['p', 'M8 2l6.5 3.5L8 9 1.5 5.5z'], ['p', 'M1.5 8.5L8 12l6.5-3.5'], ['p', 'M1.5 11.5L8 15l6.5-3.5']],
  hidden: [['p', 'M1.5 8c1.8-3.2 4-4.5 6.5-4.5s4.7 1.3 6.5 4.5c-1.8 3.2-4 4.5-6.5 4.5S3.3 11.2 1.5 8z'], ['p', 'M2.5 13.5l11-11']],
  crosshair: [['c', 8, 8, 5], ['p', 'M8 1v4M8 11v4M1 8h4M11 8h4']],
  camera: [['p', 'M1.5 4.5h3l1.5-2h4l1.5 2h3v9h-13z'], ['c', 8, 9, 2.5]],
  photo: [['p', 'M1.5 2.5h13v11h-13z'], ['p', 'M1.5 11l4-4 3 3 2-2 4 4'], ['C', 11, 5.5, 1.1]],
  play: [['f', 'M4 2.5l9 5.5-9 5.5z']],
  pause: [['f', 'M3.5 2.5h3v11h-3zM9.5 2.5h3v11h-3z']],
  back: [['f', 'M14 2.5v11l-6-5.5zM8 2.5v11L2 8z']],
  forward: [['f', 'M2 2.5v11l6-5.5zM8 2.5v11l6-5.5z']],
  chevronDown: [['p', 'M3.5 6l4.5 4.5L12.5 6']],
  chevronRight: [['p', 'M6 3.5l4.5 4.5L6 12.5']],
  close: [['p', 'M3.5 3.5l9 9M12.5 3.5l-9 9']],
  warning: [['p', 'M8 1.75l6.75 12H1.25z'], ['p', 'M8 6v3.75'], ['C', 8, 11.75, 0.8]],
  info: [['c', 8, 8, 6.25], ['p', 'M8 7v4.5'], ['C', 8, 4.75, 0.8]],
  lock: [['p', 'M3 7h10v7.5H3z'], ['p', 'M5 7V5a3 3 0 016 0v2']],
  gpu: [['p', 'M3.5 3.5h9v9h-9z'], ['p', 'M6 6h4v4H6zM6 1v2.5M10 1v2.5M6 12.5V15M10 12.5V15M1 6h2.5M1 10h2.5M12.5 6H15M12.5 10H15']],
  online: [['C', 8, 8, 2.5], ['p', 'M4 4a5.7 5.7 0 000 8M12 4a5.7 5.7 0 010 8']],
  offline: [['c', 8, 8, 2.5], ['p', 'M4 4a5.7 5.7 0 000 8M12 4a5.7 5.7 0 010 8M2 14L14 2']],
  clean: [['p', 'M3 1.5h7l3 3v10H3z'], ['p', 'M10 1.5v3h3']],
  water: [['p', 'M1 5.5c1.75-1.5 3.25-1.5 5 0s3.25 1.5 5 0 2.75-1.5 4 0M1 10.5c1.75-1.5 3.25-1.5 5 0s3.25 1.5 5 0 2.75-1.5 4 0']],
  skyline: [['p', 'M1 14.5h14M2 14.5V8h3v6.5M5 14.5V4h4v10.5M9 14.5V7h2.5V5H14v9.5']],
  mask: [['p', 'M1.5 9.5h13v5h-13z'], ['p', 'M3 14.5l4-5M7 14.5l4-5M11 14.5l3.5-4.4']],
  sector: [['p', 'M8 8L3 2.5a8 8 0 0110 0z'], ['c', 8, 8, 1]],
  zoom: [['c', 6.75, 6.75, 4.75], ['p', 'M10.25 10.25L14.5 14.5']],
  ruler: [['p', 'M1.5 5.5h13v5h-13z'], ['p', 'M4 5.5v2M6.5 5.5v3M9 5.5v2M11.5 5.5v3']],
  matrix: [['p', 'M2 2h12v12H2zM2 6h12M2 10h12M6 2v12M10 2v12']],
  log: [['p', 'M5 3.5h9.5M5 8h9.5M5 12.5h9.5'], ['C', 2.25, 3.5, 0.9], ['C', 2.25, 8, 0.9], ['C', 2.25, 12.5, 0.9]],
  bracket: [['p', 'M5 1.5H2.5v13H5'], ['p', 'M7 4.5h7M7 8h7M7 11.5h7']],
  pin: [['c', 8, 8, 6], ['f', 'M8 3.5l3.9 6.75H4.1z']],
  replay: [['p', 'M2.5 8a5.5 5.5 0 105.5-5.5H5'], ['p', 'M6.5 0.75L4.75 2.5 6.5 4.25']],
  plus: [['p', 'M8 2.5v11M2.5 8h11']],
  minus: [['p', 'M2.5 8h11']],
  file: [['p', 'M3 1.5h7l3 3v10H3z'], ['p', 'M10 1.5v3h3M5.5 8.5h5M5.5 11h5']],
  special: [['p', 'M2 3.5h12v9H2z'], ['p', 'M5 6l2.5 4M7.5 6L5 10M9.5 7h2c.9 0 1 1.5 0 1.5h-.75.75c1 0 1 1.5 0 1.5h-2']],
};

export interface IconProps { name: string; size?: number; title?: string; className?: string; style?: any }
/** One icon. Inherits currentColor; decorative unless a title is given. */
export function Icon({ name, size, title, className, style }: IconProps) {
  const els = ICONS[name] || ICONS.info;
  const kids = els.map((e: any[], i: number) => {
    if (e[0] === 'p') return h('path', { key: i, d: e[1], fill: 'none' });
    if (e[0] === 'f') return h('path', { key: i, d: e[1], fill: 'currentColor', stroke: 'none' });
    if (e[0] === 'c') return h('circle', { key: i, cx: e[1], cy: e[2], r: e[3], fill: 'none' });
    return h('circle', { key: i, cx: e[1], cy: e[2], r: e[3], fill: 'currentColor', stroke: 'none' });
  });
  return h('svg', {
    className: cx('aq-icon', className), viewBox: '0 0 16 16', width: size || undefined, height: size || undefined,
    stroke: 'currentColor', strokeWidth: 1.5, strokeLinecap: 'square', strokeLinejoin: 'miter',
    role: title ? 'img' : undefined, 'aria-hidden': title ? undefined : true, 'aria-label': title, style, focusable: 'false',
  }, title ? h('title', null, title) : null, ...kids);
}
