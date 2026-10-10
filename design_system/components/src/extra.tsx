import { h, Fragment, cx, useT, useDensity, useState, useEffect, useRef, fmtCoord, fmtDist } from './rt';
import { Icon } from './icons';
import { Button, Badge, Segmented, Toggle } from './base';
import { ModelChip } from './shell';
import { PerspScene, sceneFor } from './panorama';
import { persp, perspPoint, Cam, Pt3 } from './scene';

// ---------------------------------------------------------------------------
export interface FilenameParseProps { file: string; urban?: 'urban' | 'non-urban' | 'unknown'; source?: 'official' | 'inferred' | 'unknown'; special?: boolean; size?: [number, number]; status?: 'valid' | 'warning' | 'error'; message?: string; editable?: boolean }
const FN = /^IMG_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_(\d{2})_(\d{3})\.jpe?g$/i;
/** The filename is the only side information: date, UTC time, shot counter. Shown split, with the Urban label, its source and the Special One flag. */
export function FilenameParse({ file, urban = 'unknown', source = 'unknown', special, size = [6080, 3040], status, message, editable = true }: FilenameParseProps) {
  const T = useT();
  const m = FN.exec(file);
  const st = status || (!m ? 'warning' : size[0] / size[1] !== 2 ? 'error' : size[0] !== 6080 ? 'warning' : 'valid');
  return h('div', { className: cx('aq-fn', 'is-' + st) },
    h('div', { className: 'aq-fn-top' }, h(Icon, { name: st === 'valid' ? 'file' : st === 'warning' ? 'warning' : 'failed' }),
      m ? h('span', { className: cx('aq-fn-name', T.data) }, h('span', { className: 'aq-ink3' }, 'IMG_'), h('mark', null, m[1] + m[2] + m[3]), h('span', { className: 'aq-ink3' }, '_'), h('mark', null, m[4] + m[5] + m[6]), h('span', { className: 'aq-ink3' }, `_${m[7]}_`), h('mark', null, m[8]), h('span', { className: 'aq-ink3' }, '.jpg'))
        : h('span', { className: cx('aq-fn-name', T.data) }, file),
      h('span', { className: cx(T.dataSm, size[0] / size[1] !== 2 ? 'aq-c-contra' : size[0] !== 6080 ? 'aq-c-cost' : 'aq-ink3') }, `${size[0]}×${size[1]}`)),
    h('div', { className: 'aq-fn-row' }, m ? h('dl', { className: cx('aq-fn-parts', T.micro) },
      h('div', null, h('dt', null, 'Date'), h('dd', { className: T.data }, `${m[1]}-${m[2]}-${m[3]}`)), h('div', null, h('dt', null, 'Time'), h('dd', { className: T.data }, `${m[4]}:${m[5]}:${m[6]} UTC`)), h('div', null, h('dt', null, 'Shot'), h('dd', { className: T.data }, m[8]))) : null,
    st !== 'error' && editable ? h('div', { className: 'aq-fn-ctl' },
      h(Segmented, { label: 'Urban label', value: urban, options: [{ id: 'urban', label: 'Urban' }, { id: 'non-urban', label: 'Non-urban' }, { id: 'unknown', label: 'Unknown' }] }),
      h(Badge, { tone: source === 'official' ? 'neutral' : 'outline' }, `source: ${source}`),
      h(Toggle, { label: 'Special One ×3', on: !!special, icon: 'special' })) : null),
    message ? h('div', { className: cx('aq-fn-msg', T.body) }, message) : null);
}

export interface DropZoneProps { state?: 'empty' | 'dragging' | 'valid' | 'warning' | 'error'; files?: FilenameParseProps[]; count?: number }
/** Intake: drop one or several JPGs. Any 2:1 image is accepted; other sizes are flagged; wrong ratios are refused with the reason. */
export function DropZone({ state = 'empty', files = [], count = 6 }: DropZoneProps) {
  const T = useT();
  return h('div', { className: cx('aq-drop', 'is-' + state) },
    state === 'empty' || state === 'dragging' ? h('div', { className: 'aq-drop-target' },
      h(Icon, { name: 'drop' }), h('div', { className: T.heading }, state === 'dragging' ? `Release to add ${count} panoramas` : 'Drop the panoramas here'),
      h('div', { className: cx(T.body, 'aq-ink2') }, state === 'dragging' ? 'Each one becomes its own sealed case.' : 'One or several 360° JPGs, 2:1 equirectangular. Nothing else can be uploaded.'),
      state === 'empty' ? h(Button, { icon: 'file' }, 'Choose files') : null)
      : h('div', { className: 'aq-drop-list' }, files.map((f, i) => h(FilenameParse, { key: i, ...f }))));
}

// ---------------------------------------------------------------------------
export interface MatchViewProps { c: any; refIdx?: number; width?: number; height?: number; lines?: number; showRejected?: boolean }
/** Exact spot: query view and a reference photo side by side, keypoint matches drawn between them, inliers counted. */
export function MatchView({ c, refIdx = 0, width = 560, height = 220, lines = 36, showRejected = true }: MatchViewProps) {
  const T = useT();
  const stage = useDensity() === 'stage';
  const sc = sceneFor(c);
  const half = width / 2 - 4;
  const qCam: Cam = { pos: [0, 0, 1.7], yaw: 42, fov: 74, w: half, h: height };
  const refCams: Cam[] = [{ pos: [-13, -7, 1.6], yaw: 52, fov: 62, w: half, h: height }, { pos: [16, -6, 1.6], yaw: 18, fov: 66, w: half, h: height }, { pos: [-30, -24, 1.6], yaw: 50, fov: 50, w: half, h: height }];
  const rCam = refCams[refIdx] || refCams[0];
  const ref = c.spot.refs[refIdx];
  const kps = (sc.keypoints || []).filter((_, i) => i % 3 === 0);
  const pairs: any[] = [];
  for (const k of kps) { const a = perspPoint(k, qCam), b = perspPoint(k, rCam); if (a && b && a[0] > 2 && a[0] < half - 2 && b[0] > 2 && b[0] < half - 2 && a[1] > 2 && a[1] < height - 2 && b[1] > 2 && b[1] < height - 2) pairs.push([a, b]); }
  const nIn = Math.min(lines, pairs.length);
  const accepted = pairs.slice(0, nIn);
  const rejected: any[] = showRejected ? accepted.slice(0, 6).map((p, i) => [p[0], [Math.min(half - 4, Math.abs((p[1][0] + 70 * (i % 2 ? 1 : -1.3)) % half)), Math.min(height - 4, (p[1][1] + 40 + i * 13) % height)]]) : [];
  const lw = stage ? 2 : 1;
  return h('figure', { className: 'aq-match' },
    h('div', { className: 'aq-match-h' }, h('span', { className: T.label }, 'Query view'), h('span', { className: cx(T.micro, 'aq-ink3') }, 'from this panorama · yaw 42° · 74°'),
      h('span', { className: cx(T.label, 'aq-match-rh') }, `Reference ${ref.id}`), h('span', { className: cx(T.micro, 'aq-ink3') }, `geotagged · ${fmtDist(ref.dist)} from the candidate`)),
    h('svg', { viewBox: `0 0 ${width} ${height}`, width, height, role: 'img', 'aria-label': `Keypoint matches: ${ref.inliers} inliers of ${ref.matches}` },
      h('g', null, h(PerspScene, { sc, cam: qCam })), h('g', { transform: `translate(${half + 8},0)` }, h(PerspScene, { sc, cam: rCam })),
      h('rect', { x: half, y: 0, width: 8, height, className: 'aq-match-gap' }),
      rejected.map((p, i) => h('line', { key: 'r' + i, x1: p[0][0], y1: p[0][1], x2: p[1][0] + half + 8, y2: p[1][1], className: 'aq-match-out', strokeWidth: lw })),
      accepted.map((p, i) => h('g', { key: 'a' + i }, h('line', { x1: p[0][0], y1: p[0][1], x2: p[1][0] + half + 8, y2: p[1][1], className: 'aq-match-in', strokeWidth: lw }), h('circle', { cx: p[0][0], cy: p[0][1], r: stage ? 3.5 : 2, className: 'aq-match-kp' }), h('circle', { cx: p[1][0] + half + 8, cy: p[1][1], r: stage ? 3.5 : 2, className: 'aq-match-kp' })))),
    h('figcaption', { className: 'aq-match-cap' },
      h('span', { className: cx(T.readout, ref.accepted ? 'aq-c-support' : 'aq-c-contra') }, ref.inliers), h('span', { className: cx(T.body, 'aq-ink2') }, `inliers of ${ref.matches} matches`),
      h('span', { className: cx('aq-match-k', T.micro) }, h('i', { className: 'is-in' }), `accepted (sample of ${nIn})`), showRejected ? h('span', { className: cx('aq-match-k', T.micro) }, h('i', { className: 'is-out' }), 'rejected by geometry') : null,
      h(ModelChip, { name: 'ALIKED + LightGlue', actor: 'model', size: 'sm' })));
}

// ---------------------------------------------------------------------------
export interface LeaderLinesProps { links: [string, string][]; children?: any; className?: string; style?: any }
/** Draws leader lines between linked elements ([data-link] ids) — an evidence card to its pixels and to its map area. */
export function LeaderLines({ links, children, className, style }: LeaderLinesProps) {
  const ref = useRef(null);
  const [lines, setLines] = useState([] as any[]);
  useEffect(() => {
    const el: any = ref.current; if (!el) return;
    const run = () => {
      const box = el.getBoundingClientRect(); const out: any[] = [];
      for (const [a, b] of links) {
        const A = el.querySelector(`[data-leader="${a}"]`) || el.querySelector(`[data-link="${a}"]`), B = el.querySelector(`[data-leader="${b}"]`) || el.querySelectorAll(`[data-link="${b}"]`)[0];
        if (!A || !B || A === B) continue;
        const ra = A.getBoundingClientRect(), rb = B.getBoundingClientRect();
        const ax = ra.right < rb.left ? ra.right : ra.left > rb.right ? ra.left : ra.left + ra.width / 2, ay = ra.top + ra.height / 2;
        const bx = rb.left > ra.right ? rb.left : rb.right < ra.left ? rb.right : rb.left + rb.width / 2, by = rb.top + rb.height / 2;
        out.push([ax - box.left, ay - box.top, bx - box.left, by - box.top]);
      }
      setLines(out);
    };
    const id = setTimeout(run, 60); window.addEventListener('resize', run);
    return () => { clearTimeout(id); window.removeEventListener('resize', run); };
  }, [JSON.stringify(links)]);
  return h('div', { ref, className: cx('aq-leaders', className), style },
    children,
    h('svg', { className: 'aq-leaders-svg', 'aria-hidden': true }, lines.map((l, i) => { const mx = (l[0] + l[2]) / 2; return h('g', { key: i }, h('path', { d: `M${l[0]} ${l[1]}C${mx} ${l[1]} ${mx} ${l[3]} ${l[2]} ${l[3]}`, className: 'aq-leader-halo' }), h('path', { d: `M${l[0]} ${l[1]}C${mx} ${l[1]} ${mx} ${l[3]} ${l[2]} ${l[3]}`, className: 'aq-leader' }), h('circle', { cx: l[0], cy: l[1], r: 3, className: 'aq-leader-end' }), h('circle', { cx: l[2], cy: l[3], r: 3, className: 'aq-leader-end' })); })));
}
