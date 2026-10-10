// Aqui — component types (documentation; props as the bundle reads them). Namespace: window.Aqui
import type * as React from 'react';

export interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'quiet' | 'skip';
  icon?: string; cost?: number; shortcut?: string; busy?: string; disabled?: boolean;
  pressed?: boolean; forceState?: 'hover' | 'focus' | 'active'; onClick?: () => void; children?: any; title?: string; className?: string;
}
/** The one button. Primary at most once per view; any action that costs points carries its cost tag. */
export declare function Button(props: ButtonProps): React.ReactElement;

export interface CostTagProps { multiplier: number; label?: string }
/** The cost tag: the multiplier an action will apply, shown before the click. */
export declare function CostTag(props: CostTagProps): React.ReactElement;

export interface KeyCapProps { children?: any }
/** A keyboard key. Shown next to every action that has a shortcut. */
export declare function KeyCap(props: KeyCapProps): React.ReactElement;

export interface BadgeProps { tone?: 'neutral' | 'model' | 'solver' | 'team' | 'cost' | 'support' | 'contra' | 'outline'; icon?: string; solid?: boolean; children?: any; title?: string }
/** A short label. Tone means something: actors, cost, polarity. Neutral by default. */
export declare function Badge(props: BadgeProps): React.ReactElement;

export interface StampProps { kind?: 'ruled-out' | 'confirmed' | 'submitted' | 'estimate'; children?: any }
/** A verdict stamp. At most one in view. Words, never colour alone. */
export declare function Stamp(props: StampProps): React.ReactElement;

export interface TabsProps { tabs: { id: string; label: string; count?: number; icon?: string }[]; value: string; onChange?: (id: string) => void; label?: string }
/** Tabs: arrow keys move, Enter selects. Counts in mono. */
export declare function Tabs(props: TabsProps): React.ReactElement;

export interface ToggleProps { label: string; on?: boolean; swatch?: string; icon?: string; disabled?: boolean; onChange?: (on: boolean) => void; hint?: string }
/** A switch. With a swatch it is a map/panorama layer toggle. */
export declare function Toggle(props: ToggleProps): React.ReactElement;

export interface SegmentedProps { options: { id: string; label: string; icon?: string }[]; value: string; label?: string; onChange?: (id: string) => void }
/** A segmented choice (radio group), e.g. Urban / Non-urban / Unknown. */
export declare function Segmented(props: SegmentedProps): React.ReactElement;

export interface TooltipProps { content: any; open?: boolean; children?: any; side?: 'top' | 'bottom' }
/** Hover or focus reveals a short explanation. Never holds the only copy of something important. */
export declare function Tooltip(props: TooltipProps): React.ReactElement;

export interface ToastProps { tone?: 'neutral' | 'cost' | 'contra' | 'team'; icon?: string; title: string; body?: any; action?: string }
/** A transient report of something that happened (and is in the log). */
export declare function Toast(props: ToastProps): React.ReactElement;

export interface DialogProps { title: string; children?: any; actions?: any; inline?: boolean; tone?: 'neutral' | 'cost' }
/** A modal decision. Used for Submit and for sending a cue: the cost is restated in the dialog. */
export declare function Dialog(props: DialogProps): React.ReactElement;

export interface EmptyStateProps { icon?: string; title: string; body?: any; action?: any }
/** What to do when there is nothing here yet. Direction, not mood. */
export declare function EmptyState(props: EmptyStateProps): React.ReactElement;

export interface WaitStateProps { what: string; who?: string; elapsed: number; deadline?: number; partial?: string; fallback?: string }
/** A real wait: names what is running, shows real elapsed time against its real deadline. No spinner, no fake percentage. */
export declare function WaitState(props: WaitStateProps): React.ReactElement;

export interface IconProps { name: string; size?: number; title?: string; className?: string; style?: any }
/** Aqui icon set — drawn on a 16px grid, 1.5px stroke, square caps, mitred joins. Each entry is a list of SVG elements: ['p', d] path (stroked), ['f', d] filled path, ['c', cx, cy, r] stroked circle, ['C', cx, cy, r] filled circle. /
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
export declare function Icon(props: IconProps): React.ReactElement;

export interface DensityProps { value?: 'console' | 'stage'; theme?: 'dark' | 'light' | 'stage'; className?: string; style?: any; children?: any }
/**  */
export declare function Density(props: DensityProps): React.ReactElement;

export interface WordmarkProps { size?: number; mark?: boolean; title?: string }
/** "aqui" — Newsreader letters; the tittle is a point inside a broken uncertainty ring (here, ± how sure). mark=true draws only the i. */
export declare function Wordmark(props: WordmarkProps): React.ReactElement;

export interface RunBarProps { c: any; special?: boolean; online?: boolean; tilesOffline?: boolean; replay?: number; showWordmark?: boolean }
/** The always-visible run bar: case, timers, multiplier, expected score, GPU, worker status. Built from the case's run record. */
export declare function RunBar(props: RunBarProps): React.ReactElement;

export interface TimerProps { label: string; used: number; budget: number; warnAt?: number; compact?: boolean }
/** Time used against a budget. Ink until 80%, then cost colour; over budget shows how far over. */
export declare function Timer(props: TimerProps): React.ReactElement;

export interface MultiplierChipProps { value: number; history?: { t: number; m: number; what: string }[]; open?: boolean }
/** The running multiplier for this panorama, always on screen. Opens to its history; every step is a log event. */
export declare function MultiplierChip(props: MultiplierChipProps): React.ReactElement;

export interface ScoreReadoutProps { expected: number; range?: [number, number]; max?: number; special?: boolean; urbanUnknown?: { urban: number; nonUrban: number }; size?: 'md' | 'xl' }
/** Expected score under current beliefs — always labelled an estimate, never a result. */
export declare function ScoreReadout(props: ScoreReadoutProps): React.ReactElement;

export interface GpuMeterProps { used: number; total?: number; models?: { name: string; gb: number }[]; compact?: boolean }
/** GPU memory in GB with the resident models as segments. Warns above 14 GB of 16. */
export declare function GpuMeter(props: GpuMeterProps): React.ReactElement;

export interface SystemBadgeProps { kind: 'worker-online' | 'worker-offline' | 'tiles-offline' | 'clean' | 'replay'; speed?: number }
/** System status in words: worker online/offline, map tiles offline, clean state verified, replay speed. */
export declare function SystemBadge(props: SystemBadgeProps): React.ReactElement;

export interface ModelChipProps { name: string; role?: string; actor?: 'model' | 'solver' | 'team'; local?: boolean; size?: 'sm' | 'md' }
/** Who produced something. Models say "local · open weights"; the solver says "code, not a model". */
export declare function ModelChip(props: ModelChipProps): React.ReactElement;

export interface ModelRosterProps { models: any[]; compact?: boolean; title?: string }
/** Every local model with its role and memory. State in words: resident, running, idle, standby (fallback). */
export declare function ModelRoster(props: ModelRosterProps): React.ReactElement;

export interface CaseCardProps { label: string; status: 'waiting' | 'processing' | 'needs-answer' | 'done' | 'submitted'; special?: boolean; multiplier?: number; expected?: number; used?: number; stage?: string; elapsed?: number; current?: boolean; gain?: number }
/** A sealed case in the queue. Only status crosses between cases: no image, no date, no content. */
export declare function CaseCard(props: CaseCardProps): React.ReactElement;

export interface ShortcutBarProps { keys: { k: string; label: string }[] }
/** Shortcut hints for the current mode, along the bottom of the console. */
export declare function ShortcutBar(props: ShortcutBarProps): React.ReactElement;

export interface CleanStateCheckProps { items?: { label: string; ok: boolean }[]; caseLabel?: string }
/** Shown when a case starts: proof it is sealed — new conversation, empty evidence, nothing carried over. */
export declare function CleanStateCheck(props: CleanStateCheckProps): React.ReactElement;

export interface DropZoneProps { state?: 'empty' | 'dragging' | 'valid' | 'warning' | 'error'; files?: FilenameParseProps[]; count?: number }
/** Intake: drop one or several JPGs. Any 2:1 image is accepted; other sizes are flagged; wrong ratios are refused with the reason. */
export declare function DropZone(props: DropZoneProps): React.ReactElement;

export interface FilenameParseProps { file: string; urban?: 'urban' | 'non-urban' | 'unknown'; source?: 'official' | 'inferred' | 'unknown'; special?: boolean; size?: [number, number]; status?: 'valid' | 'warning' | 'error'; message?: string; editable?: boolean }
/** The filename is the only side information: date, UTC time, shot counter. Shown split, with the Urban label, its source and the Special One flag. */
export declare function FilenameParse(props: FilenameParseProps): React.ReactElement;

export interface PanoramaStripProps {
  c: any; width?: number; layers?: Record<string, boolean>; selected?: string; ruler?: 'yaw' | 'bearing' | false; fov?: { yaw: number; fov: number };
  showRejected?: boolean; crop?: [number, number]; visibleBoxes?: string[]; fadedBoxes?: string[]; label?: boolean; labelMode?: 'all' | 'selected' | 'text';
}
/** The flat equirectangular panorama with overlay layers and the bearing ruler. Built from the case's evidence. */
export declare function PanoramaStrip(props: PanoramaStripProps): React.ReactElement;

export interface BearingRulerProps { width: number; mode?: 'yaw' | 'bearing'; offset?: number; err?: number; marks?: { yaw: number; label?: string; tone?: string }[]; fov?: { yaw: number; fov: number } }
/** Draws the scene as an equirectangular image into an SVG group. seg=true draws segmentation classes instead of colours. */
function EquiScene({ sc, W, H, seg }: { sc: Scene; W: number; H: number; seg?: boolean }) {
  const els: any[] = [];
  els.push(h('rect', { key: 'sky', x: 0, y: 0, width: W, height: H / 2 + 1, fill: seg ? SEG_VAR.sky : sc.sky }));
  els.push(h('rect', { key: 'gr', x: 0, y: H / 2, width: W, height: H / 2, fill: seg ? SEG_VAR[sc.groundSeg] : sc.ground }));
  if (!seg) for (const dd of (sc.horizon ? [4, 9, 20] : [2.2, 3.2, 4.6, 6.5, 9.5])) { const y = (90 + Math.atan2(1.7, dd) / D2R) / 180 * H; els.push(h('line', { key: 'pv' + dd, x1: 0, x2: W, y1: y, y2: y, stroke: '#00000014', strokeWidth: 1 })); }
  if (sc.horizon) {
    const top: [number, number][] = []; for (let y = 0; y <= 360; y += 2) top.push(yawPitchToXY(y === 360 ? 359.999 : y, sc.horizon(y), W, H));
    els.push(h('polygon', { key: 'hz', points: pts2([...top, [W, H / 2 + 1], [0, H / 2 + 1]]), fill: seg ? SEG_VAR.tree : sc.horizonFill }));
  }
  if (sc.sun && !seg) { const [x, y] = yawPitchToXY(sc.sun.yaw, sc.sun.el, W, H); els.push(h('circle', { key: 'sun', cx: x, cy: y, r: Math.max(2.5, W / 360 * 1.4), fill: '#f7f3e6' })); }
  const polys = [...sc.polys].sort((a, b) => b.depth - a.depth);
  polys.forEach((p, i) => {
    if (seg && (p.kind === 'window' || p.kind === 'door' || p.kind === 'sign' || p.fill === 'none')) return;
    for (const cp of equiPts(p.pts, W, H)) els.push(h('polygon', { key: 'p' + i + '_' + cp[0][0].toFixed(0), points: pts2(cp), fill: seg ? SEG_VAR[p.seg || 'building'] : p.fill, stroke: seg ? 'none' : p.stroke, strokeWidth: p.sw }));
  });
  sc.discs.forEach((d, i) => {
    const [yaw, pitch] = toYawPitch(d.c); const dist = Math.hypot(d.c[0], d.c[1]);
    const rx = Math.atan2(d.r, dist) / D2R / 360 * W, ry = Math.atan2(d.ry || d.r, dist) / D2R / 180 * H;
    const [x, y] = yawPitchToXY(yaw, pitch, W, H);
    for (const dx of [0, W, -W]) els.push(h('ellipse', { key: 'd' + i + dx, cx: x + dx, cy: y, rx, ry, fill: seg ? SEG_VAR.tree : d.fill }));
  });
  return h('g', { className: seg ? 'aq-seg-layer' : undefined }, els);
}

// ---------------------------------------------------------------------------
export interface BearingRulerProps { width: number; mode?: 'yaw' | 'bearing'; offset?: number; err?: number; marks?: { yaw: number; label?: string; tone?: string }[]; fov?: { yaw: number; fov: number } }
/** 0–360° ruler under the panorama. Camera yaw until the sun fixes north; then true bearings with the fix's ± error. */
export declare function BearingRuler(props: BearingRulerProps): React.ReactElement;

export interface Viewer360Props { c: any; yaw?: number; pitch?: number; fov?: number; width?: number; height?: number; selected?: string; synced?: boolean; showBoxes?: boolean }
/** The interactive 360° viewer frame (Pannellum in the app), kept in sync with the strip on yaw. */
export declare function Viewer360(props: Viewer360Props): React.ReactElement;

export interface ZoomCropProps { c: any; target: string; width?: number; height?: number; fov?: number; note?: string }
/** A full-resolution crop around one box, with its reading. Opens from a box or an evidence card. */
export declare function ZoomCrop(props: ZoomCropProps): React.ReactElement;

export interface LayerTogglesProps { layers: Record<string, boolean>; counts?: Record<string, string>; onChange?: (k: string, v: boolean) => void; columns?: number }
/** Overlay switches for the panorama, with counts; every layer comes from evidence in the log. */
export declare function LayerToggles(props: LayerTogglesProps): React.ReactElement;

export interface MatchViewProps { c: any; refIdx?: number; width?: number; height?: number; lines?: number; showRejected?: boolean }
/** Exact spot: query view and a reference photo side by side, keypoint matches drawn between them, inliers counted. */
export declare function MatchView(props: MatchViewProps): React.ReactElement;

export interface StageRowProps { stage: any; compact?: boolean; pass?: number }
/** One pipeline stage: status (icon + word), its models, real duration, memory. Running shows real elapsed against the stage deadline. */
export declare function StageRow(props: StageRowProps): React.ReactElement;

export interface StageTimelineProps { stages: any[]; compact?: boolean; title?: string; loopFrom?: string; loopTo?: string }
/** The stage list, data-driven: any number of stages, any model names. A bracket marks stages that ran again after an answer. */
export declare function StageTimeline(props: StageTimelineProps): React.ReactElement;

export interface EvidenceCardProps { e: any; names?: Record<string, string>; selected?: boolean; compact?: boolean; isNew?: boolean; crop?: any; showActor?: boolean }
/** One piece of evidence, in three registers kept apart: observation (bracketed, mono, what a model saw) → inference (italic serif, what follows) → estimate (≈ mono with range, what the solver takes from it). */
export declare function EvidenceCard(props: EvidenceCardProps): React.ReactElement;

export interface PolarityChipProps { name: string; pol: number }
/** Evidence → candidate: ▲ supports, ▼ contradicts, ● neutral. Glyph and word, never colour alone. */
export declare function PolarityChip(props: PolarityChipProps): React.ReactElement;

export interface ConfidenceMeterProps { value?: number | null; level?: 'high' | 'med' | 'low' | 'unknown'; showValue?: boolean }
/** Three cells + a word. Unknown is dashed and says "unknown" — never drawn as low. */
export declare function ConfidenceMeter(props: ConfidenceMeterProps): React.ReactElement;

export interface CorrelationBracketProps { label: string; cap?: number; note?: string; children?: any }
/** Groups evidence that shares one image encoder: drawn as one voice, with its capped combined weight. */
export declare function CorrelationBracket(props: CorrelationBracketProps): React.ReactElement;

export interface CaptionBarProps { headline: string; caption: string; actor?: 'model' | 'solver' | 'team'; source?: string; t?: number; speed?: number }
/** Plain-language caption built from a template per event type, e.g. "Reading signs: a postcode in a format only Portugal uses". */
export declare function CaptionBar(props: CaptionBarProps): React.ReactElement;

export interface LeaderLinesProps { links: [string, string][]; children?: any; className?: string; style?: any }
/** Draws leader lines between linked elements ([data-link] ids) — an evidence card to its pixels and to its map area. */
export declare function LeaderLines(props: LeaderLinesProps): React.ReactElement;

export interface CandidateRowProps { c: any; selected?: boolean; max?: number; showDelta?: boolean; ghost?: boolean }
/** A candidate: rank, name, level, estimate bar with its range, change since the last update, and support/contradict counts. */
export declare function CandidateRow(props: CandidateRowProps): React.ReactElement;

export interface CandidateListProps { candidates: any[]; selected?: string; title?: string; ruledOut?: any[]; showDelta?: boolean; caption?: string }
/** The ranked candidate list with "other" and the ruled-out rows underneath. Estimates, not calibrated probabilities. */
export declare function CandidateList(props: CandidateListProps): React.ReactElement;

export interface RuledOutRowProps { r: { name: string; level?: string; reason: string; by?: string[] }; byLabels?: Record<string, string>; stamp?: boolean }
/** A ruled-out place stays visible: struck through, with the reason and the evidence that decided it. */
export declare function RuledOutRow(props: RuledOutRowProps): React.ReactElement;

export interface FunnelProps { levels: { level: string; name: string; v: number }[]; current?: number }
/** Country → region → town → spot, each with its estimate; the map never zooms tighter than the level the evidence supports. */
export declare function Funnel(props: FunnelProps): React.ReactElement;

export interface EvidenceMatrixProps { evidence: any[]; candidates: string[]; names: Record<string, string>; groups?: any[]; selected?: string; dense?: boolean }
/** Evidence × candidate: what supports and what contradicts each place. Correlated rows share a bracket. */
export declare function EvidenceMatrix(props: EvidenceMatrixProps): React.ReactElement;

export interface MapViewProps {
  view: View; width?: number; height?: number; offline?: boolean; base?: 'auto' | 'outline' | 'town';
  heat?: { lat: number; lng: number; w: number; s: number }[]; samples?: number; refs?: { id: string; lat: number; lng: number; label?: string; accepted?: boolean }[];
  candidates?: { id: string; rank?: number; lat: number; lng: number; name?: string; ruledOut?: boolean; r?: number | null }[]; selected?: string;
  rings?: { lat: number; lng: number; r: number | null; label?: string; tone?: string }[];
  zones?: { key: string; region?: string; poly?: [number, number][]; rest?: boolean; point?: [number, number] | null; label?: string; chosen?: boolean; dim?: boolean }[];
  cone?: { lat: number; lng: number; bearing: number; err: number; len: number; label?: string };
  final?: { lat: number; lng: number; r: number | null };
  area?: { lat: number; lng: number; r: number; label: string };
  legend?: boolean; scale?: boolean; labels?: boolean; inset?: { view: View; box?: View; label?: string }; hoverRef?: string; dimOthers?: boolean; caption?: string;
}
/** The map (MapLibre in the app; bundled outlines when offline). Layer order keeps it readable: base < heat < zones < points < rings < pins < labels. */
export declare function MapView(props: MapViewProps): React.ReactElement;

export interface UncertaintyRingProps { r: number | null; source?: string; size?: number }
/** Known radius: a solid ring with ± metres and its source. Unknown: an open dashed ring with "?", never a dot — unknown is not small. */
export declare function UncertaintyRing(props: UncertaintyRingProps): React.ReactElement;

export interface SurveyMarkProps { x: number; y: number; size?: number }
/** The final pin: a surveyor's trig-point mark (triangle, centre dot, circle), not a teardrop. */
export declare function SurveyMark(props: SurveyMarkProps): React.ReactElement;

export interface MapLegendProps { items: string[] }
/** The map legend: only the layers on screen, each with its symbol. */
export declare function MapLegend(props: MapLegendProps): React.ReactElement;

export interface QuestionCardProps { q: any; evidence?: any[]; state?: 'open' | 'answered' | 'skipped'; cueLine?: boolean; hoverKey?: string; number?: number; brief?: boolean }
/** The agent's question: up to four options, the expected gain against the break-even, the cost on every answer, and a free Skip that changes nothing. */
export declare function QuestionCard(props: QuestionCardProps): React.ReactElement;

export interface QuestionOptionProps { o: any; state?: 'open' | 'chosen' | 'other' | 'skipped'; evidence?: any[]; cost?: number; hover?: boolean; showLinks?: boolean; brief?: boolean }
/** One option: key, label, one-line reason, evidence chips, representative point (never a camera position) and outbound links. */
export declare function QuestionOption(props: QuestionOptionProps): React.ReactElement;

export interface AnswerReceiptProps { kind: 'answered' | 'skipped'; q: any; before: any[]; after?: any[]; multiplierBefore: number; multiplierAfter?: number; t?: number }
/** What changed after the team's response. Answered: beliefs move and the multiplier ticks down. Skipped: nothing moves, and it says so. */
export declare function AnswerReceipt(props: AnswerReceiptProps): React.ReactElement;

export interface CueComposerProps { text?: string; confirm?: boolean; max?: number; sent?: boolean }
/** Free-text cue to the agent: counter, ×0.8 cost before sending, a check that blocks place names, hints and coordinates, then a confirm step. */
export declare function CueComposer(props: CueComposerProps): React.ReactElement;

export interface CoordinateBlockProps { a: any; showCopy?: boolean; size?: 'md' | 'lg' }
/** The coordinate, once, in mono with a true minus — always with its order, uncertainty, role, method and the multiplier when produced. */
export declare function CoordinateBlock(props: CoordinateBlockProps): React.ReactElement;

export interface AnswerSlotsProps { a: any; expanded?: boolean; special?: boolean; producedAt?: number }
/** Ten slots, normally one coordinate ten times: shown once with ×10 and the rank weights, expandable to the full list. */
export declare function AnswerSlots(props: AnswerSlotsProps): React.ReactElement;

export interface ChoiceNoteProps { a: any; mostLikelyName?: string; mostLikelyExpected?: number }
/** Says why the chosen coordinate differs from the most likely candidate — or that it doesn't. */
export declare function ChoiceNote(props: ChoiceNoteProps): React.ReactElement;

export interface ScoreCurveProps { urban?: 'urban' | 'non-urban' | 'unknown'; band?: [number, number]; expected?: number | { urban: number; nonUrban: number }; width?: number; height?: number; multiplier?: number }
/** θ against distance on a log axis (10 m – 100 km), both curves, marks at 25 m, 100 m, 1 km, 5 km, 10 km, and the current uncertainty band. */
export declare function ScoreCurve(props: ScoreCurveProps): React.ReactElement;

export interface EventLogProps { events: any[]; filter?: string; json?: number; height?: number; current?: number }
/** The JSON event log as a readable list; everything on screen derives from it. One row can expand to its raw JSON. */
export declare function EventLog(props: EventLogProps): React.ReactElement;

export interface ReplayScrubberProps { events: any[]; t: number; duration: number; speed?: 1 | 2 | 5; playing?: boolean }
/** Scrubber over the event log. Ticks are real events (shape = actor); the speed badge is always visible; timestamps stay real. */
export declare function ReplayScrubber(props: ReplayScrubberProps): React.ReactElement;

export interface ExportBarProps { confirm?: boolean; submitted?: boolean; a?: any }
/** Copy, export and submit. Submit asks once more and restates what will be sent. */
export declare function ExportBar(props: ExportBarProps): React.ReactElement;

export interface StackedBarProps { parts: { id: string; label?: string; v: number; color?: string; hatch?: boolean }[]; caption?: string; height?: number; labelMin?: number; title?: string }
/** One 100% bar, 2px gaps between segments, every segment labelled (inline when it fits, else in the legend). */
export declare function StackedBar(props: StackedBarProps): React.ReactElement;

export interface LanguageVoteProps { votes: { id: string; v: number }[]; voters?: number }
/** The language vote: one stacked bar across pt / gl / es / ca / eu / fr. Identity by label; the model hue alternates in two steps. */
export declare function LanguageVote(props: LanguageVoteProps): React.ReactElement;

export interface SceneSharesProps { shares: { id: string; v: number }[]; masked?: number }
/** Scene shares from segmentation: visible share of the image, not land cover. */
export declare function SceneShares(props: SceneSharesProps): React.ReactElement;

export interface CompassDialProps { yawToBearing: number | null; err?: number; sun?: { azimuth: number; elevation: number }; water?: number; size?: number; viewYaw?: number }
/** Image yaw 0, true north, the sun's azimuth and elevation, and the error of the fix. North unknown draws no N. */
export declare function CompassDial(props: CompassDialProps): React.ReactElement;

export interface EstimateBarsProps { rows: { name: string; v: number; lo?: number; hi?: number; other?: boolean; before?: number; note?: string }[]; tone?: 'model' | 'solver'; max?: number; title?: string; caption?: string; mode?: 'single' | 'beforeAfter' }
/** Horizontal estimate bars, top 5 plus "other", with ranges where known. Before/after mode for answers. */
export declare function EstimateBars(props: EstimateBarsProps): React.ReactElement;

export interface GainMeterProps { gain: number; breakEven?: number; cueLine?: boolean; max?: number }
/** Expected gain of asking against the break-even line (5.26% for ×0.95; 25% for a ×0.8 cue). */
export declare function GainMeter(props: GainMeterProps): React.ReactElement;

export declare const ICONS: Record<string, unknown[]>;
export declare const Samples: { CASE_A: any; CASE_B: any; ROSTER: any[]; QUEUE: any[]; LOG_A: any[] };
export declare const Screens: Record<string, () => React.ReactElement>;
declare global { interface Window { Aqui: { Button: typeof Button; CostTag: typeof CostTag; KeyCap: typeof KeyCap; Badge: typeof Badge; Stamp: typeof Stamp; Tabs: typeof Tabs; Toggle: typeof Toggle; Segmented: typeof Segmented; Tooltip: typeof Tooltip; Toast: typeof Toast; Dialog: typeof Dialog; EmptyState: typeof EmptyState; WaitState: typeof WaitState; Icon: typeof Icon; Density: typeof Density; Wordmark: typeof Wordmark; RunBar: typeof RunBar; Timer: typeof Timer; MultiplierChip: typeof MultiplierChip; ScoreReadout: typeof ScoreReadout; GpuMeter: typeof GpuMeter; SystemBadge: typeof SystemBadge; ModelChip: typeof ModelChip; ModelRoster: typeof ModelRoster; CaseCard: typeof CaseCard; ShortcutBar: typeof ShortcutBar; CleanStateCheck: typeof CleanStateCheck; DropZone: typeof DropZone; FilenameParse: typeof FilenameParse; PanoramaStrip: typeof PanoramaStrip; BearingRuler: typeof BearingRuler; Viewer360: typeof Viewer360; ZoomCrop: typeof ZoomCrop; LayerToggles: typeof LayerToggles; MatchView: typeof MatchView; StageRow: typeof StageRow; StageTimeline: typeof StageTimeline; EvidenceCard: typeof EvidenceCard; PolarityChip: typeof PolarityChip; ConfidenceMeter: typeof ConfidenceMeter; CorrelationBracket: typeof CorrelationBracket; CaptionBar: typeof CaptionBar; LeaderLines: typeof LeaderLines; CandidateRow: typeof CandidateRow; CandidateList: typeof CandidateList; RuledOutRow: typeof RuledOutRow; Funnel: typeof Funnel; EvidenceMatrix: typeof EvidenceMatrix; MapView: typeof MapView; UncertaintyRing: typeof UncertaintyRing; SurveyMark: typeof SurveyMark; MapLegend: typeof MapLegend; QuestionCard: typeof QuestionCard; QuestionOption: typeof QuestionOption; AnswerReceipt: typeof AnswerReceipt; CueComposer: typeof CueComposer; CoordinateBlock: typeof CoordinateBlock; AnswerSlots: typeof AnswerSlots; ChoiceNote: typeof ChoiceNote; ScoreCurve: typeof ScoreCurve; EventLog: typeof EventLog; ReplayScrubber: typeof ReplayScrubber; ExportBar: typeof ExportBar; StackedBar: typeof StackedBar; LanguageVote: typeof LanguageVote; SceneShares: typeof SceneShares; CompassDial: typeof CompassDial; EstimateBars: typeof EstimateBars; GainMeter: typeof GainMeter; ICONS: typeof ICONS; Samples: typeof Samples; Screens: typeof Screens } } }
