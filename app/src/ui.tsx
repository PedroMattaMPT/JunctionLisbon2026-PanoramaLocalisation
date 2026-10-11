import React, { useEffect, useRef, useState, type ReactNode, type ReactElement } from 'react';
import { Badge, Button, Dialog, EmptyState } from '@ds/base';
import { RunBar, GpuMeter, ScoreReadout, CaseCard, ModelRoster } from '@ds/shell';
import { CandidateRow, CandidateList, EvidenceMatrix, Funnel } from '@ds/beliefs';
import { EventLog, ReplayScrubber, ExportBar, CoordinateBlock, AnswerSlots } from '@ds/output';
import { CaptionBar, StageRow, StageTimeline } from '@ds/reasoning';
import { useDensity, useT } from '@ds/rt';
import { Icon } from '@ds/icons';
import { LeaderLines, FilenameParse } from '@ds/extra';
import { DropZone } from '@ds/extra';
import { arr, finite, record, str, type CaseRecord, type Candidate, type Output, type RunEvent } from './model';
import type { WorkerStatus } from './data';
import { captionFor } from './captions';
import { coordinates, distance, modelName, roleText, time } from './format';
import { parseFilename } from './reducer';
import { CandidateLocation } from './candidate-location';

// Adapt element props and missing runtime slots; never change a DS component or stylesheet.
export type ElementProps = Record<string, any>;
export function mapTree(node: ReactNode, visit: (node: ReactElement<ElementProps>) => ReactNode): ReactNode {
  if (Array.isArray(node)) return node.map((n, i) => { const result = mapTree(n, visit); return React.isValidElement(result) && result.key === null ? React.cloneElement(result, { key: i }) : result; });
  if (!React.isValidElement<ElementProps>(node)) return node;
  const updated = node.props.children !== undefined ? React.cloneElement(node, {}, mapTree(node.props.children, visit)) : node;
  const result = visit(updated);
  return React.isValidElement(result) && result.key === null && node.key !== null ? React.cloneElement(result, { key: node.key }) : result;
}
export const typeName = (element: ReactElement<ElementProps>) => typeof element.type === 'function' ? element.type.name : '';
export function useWidth<T extends HTMLElement>(initial = 560) {
  const ref = useRef<T>(null); const [width, setWidth] = useState(initial);
  useEffect(() => { if (!ref.current) return; const observer = new ResizeObserver(entries => setWidth(Math.max(1, entries[0].contentRect.width))); observer.observe(ref.current); return () => observer.disconnect(); }, []);
  return { ref, width };
}
export function Panel({ title, aside, children, className = '' }: { title?: string; aside?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={`aq-panel ${className}`}>{title && <header className="aq-panel-h"><h2 className="console-title">{title}</h2>{aside}</header>}{children}</section>;
}
// Native disclosure keeps the complete content in the page and supplies keyboard semantics.
export function Disclosure({ title, aside, children, className = '', open, onOpenChange }: { title: ReactNode; aside?: ReactNode; children: ReactNode; className?: string; open?: boolean; onOpenChange?(open: boolean): void }) {
  const ref = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    if (!className.includes('app-disclosure-float')) return;
    const close = (e: PointerEvent) => { if (ref.current?.open && !ref.current.contains(e.target as Node)) ref.current.open = false; };
    document.addEventListener('pointerdown', close); return () => document.removeEventListener('pointerdown', close);
  }, [className]);
  return <details ref={ref} className={`app-disclosure ${className}`} open={open} onToggle={e => onOpenChange?.(e.currentTarget.open)} onKeyDown={e => {
    if (e.key === 'Escape' && e.currentTarget.open) { e.stopPropagation(); e.currentTarget.open = false; e.currentTarget.querySelector('summary')?.focus(); }
  }}>
    <summary className="console-label"><Icon name="chevronRight" /><span>{title}</span>{aside && <span className="console-micro aq-ink3 app-disclosure-aside">{aside}</span>}</summary>
    <div className="app-disclosure-body app-stack">{children}</div>
  </details>;
}
export function LinkedView({ links, revision, children }: { links: [string, string][]; revision: number; children: ReactNode }) {
  const [scroll, setScroll] = useState(0);
  // The showcase measures only on selection/resize; event arrival and column scrolling also move anchors.
  const marker = `layout-${revision}-${scroll}`;
  return <>{mapTree(LeaderLines({ className: 'app-console', links: [...links, [marker, marker]], children }), node => node.props.className?.includes('app-console') ? React.cloneElement(node, { onScrollCapture: () => setScroll(value => value + 1) }) : node)}</>;
}
export function QueueCard(props: ElementProps) {
  return <>{mapTree(CaseCard(props), node => node.props.className?.includes('aq-case-m') && props.status !== 'waiting' ? null : node)}</>;
}
export function UploadDropZone({ onChoose }: { onChoose(): void }) {
  return <>{mapTree(DropZone({ count: 6 }), node => node.type === Button ? React.cloneElement(node, { onClick: onChoose }) : node)}</>;
}
// The two VLM rows are named by where they run, never by model, whatever name the server reports.
const vlmLabel: Record<string, string> = { 'vlm-plugin': 'VLM (API)', qwen: 'VLM (Local)' };
export function LoggedRoster({ status, models }: { status?: WorkerStatus; models: ElementProps[] }) {
  const reported = status?.models.length ? status.models : null;
  const displayModels = (reported ?? models).map(model => ({ ...model, name: (reported && vlmLabel[str(model.id)]) || modelName(str(model.name)) }));
  const hosted = !!reported?.some(model => str(model.id) === 'vlm-plugin' && model.state !== 'disabled');
  return <>{mapTree(ModelRoster({ models: displayModels, compact: true, title: status?.mock ? 'Mock pipeline · no models running' : hosted ? 'Model roles' : 'Local model roles' }), node => typeof node.props.children === 'string' && node.props.children.startsWith('all open weights') ? (!reported ? React.cloneElement(node, {}, status?.mock ? 'Scripted evidence · no inference package' : 'Residency and memory not reported') : hosted ? React.cloneElement(node, {}, node.props.children.replace('all open weights', 'open weights + hosted VLM')) : node) : node)}</>;
}
export function Filename(props: ElementProps) {
  const parsed = parseFilename(props.file);
  return <>{mapTree(FilenameParse(props), node => {
    if (node.props.className?.includes('aq-fn-parts') && !parsed.date) return null;
    if (node.props.className === 'aq-fn-top' && !props.size) return React.cloneElement(node, {}, React.Children.toArray(node.props.children).slice(0, -1), <span className="console-data-sm aq-ink3">Size not decoded</span>);
    return node;
  })}</>;
}
function LoggedStageRow(props: ElementProps) {
  const s = props.stage;
  return <>{mapTree(StageRow(props), node => node.props.className === 'aq-stage-dl' ? React.cloneElement(node, {}, React.Children.toArray(node.props.children)[0], <span className="console-micro aq-ink3">{Math.round(s.dur)} s of {s.deadline} s deadline{s.fallback ? `; fallback ${s.fallback}` : ''}</span>) : node)}</>;
}
export function StageList(props: ElementProps) {
  return <>{mapTree(StageTimeline(props), node => node.type === StageRow ? <LoggedStageRow {...node.props} /> : node)}</>;
}
export function Narrowing({ c }: { c: CaseRecord }) {
  const levels: { level: string; name: string; v: number }[] = [];
  for (const event of c.events) {
    if (event.type !== 'candidates.updated' || event.actor === 'model') continue;
    const candidates = arr(event.payload.candidates).map(record).sort((a, b) => (finite(b.weight) ?? 0) - (finite(a.weight) ?? 0)), total = candidates.reduce((sum, v) => sum + Math.max(0, finite(v.weight) ?? 0), 0);
    const top = candidates[0]; if (!top || !['country', 'region', 'town', 'spot'].includes(str(top.level)) || !total) continue;
    const level = { level: str(top.level), name: str(top.name, str(top.label)), v: Math.max(0, finite(top.weight) ?? 0) / total };
    if (levels.at(-1)?.level === level.level) levels[levels.length - 1] = level; else levels.push(level);
  }
  return levels.length ? <><Funnel levels={levels} /><p className="console-micro aq-ink3">Logged narrowing · support share.</p></> : null;
}
export function RunHeader({ c, status, connected, speed, session }: { c: CaseRecord; status?: WorkerStatus; connected: boolean; speed?: number; session: number }) {
  const stage = useDensity() === 'stage';
  const T = useT();
  const record = { ...c, run: { ...c.run, session, gpu: status?.gpu.used_gb ?? null, gpuMax: status?.gpu.total_gb ?? 16 } };
  const diagnostics: ReactNode[] = [];
  const tree = mapTree(RunBar({ c: record, online: connected, replay: speed, showWordmark: stage, tilesOffline: stage && !status?.tile_source && !import.meta.env.VITE_TILE_SOURCE }), node => {
    if (status?.mock && typeName(node) === 'SystemBadge' && node.props.kind === 'worker-online') return <Badge tone="outline" icon="online">Mock worker online</Badge>;
    if (typeName(node) === 'Timer' && node.props.label === 'This panorama') return <div className="aq-timer" role="timer" aria-label={`This panorama: ${time(c.run.used)} elapsed`}><div className={`aq-timer-l ${T.micro}`}><Icon name="clock" />This panorama</div><div className="aq-timer-v"><span className={T.readout}>{time(c.run.used)}</span><span className={`${T.micro} aq-ink3`}>elapsed</span></div></div>;
    if (stage && (node.type === GpuMeter || node.type === ScoreReadout || typeName(node) === 'Timer' && node.props.label === 'Session')) return null;
    if (!stage && (node.type === ScoreReadout || node.type === GpuMeter)) {
      const detail = node.type === ScoreReadout
        ? c.run.expected === null && !c.run.split ? <p className="console-body aq-ink3">Score estimate unavailable: uncertainty unknown.</p> : <EstimatedScore expected={c.run.expected} urbanUnknown={c.run.split} special={c.special} />
        : status?.gpu.used_gb == null ? <p className="console-body aq-ink3">GPU memory not reported.</p> : node;
      diagnostics.push(<React.Fragment key={diagnostics.length}>{detail}</React.Fragment>); return null;
    }
    if (node.props.className === 'aq-runbar' && !stage) return React.cloneElement(node, {}, node.props.children, <Disclosure title="Run details" className="app-run-details app-disclosure-float"><div className="app-detail-metrics">{diagnostics}</div><p className="console-data-sm aq-ink3 app-break">{c.file || 'Panorama filename not logged'}</p><p className="console-micro aq-ink3">Worker and model residency are available in Tools → System states.</p></Disclosure>);
    return node;
  });
  return <>{tree}</>;
}
export function EstimatedScore(props: ElementProps) {
  return <>{mapTree(ScoreReadout(props), node => props.urbanUnknown && node.props.className?.includes('aq-score-l') ? React.cloneElement(node, {}, `Expected score · estimate · Urban label unknown${props.special ? ' · ×3 Special One' : ''}`) : node)}</>;
}
export function Caption({ event, speed }: { event?: RunEvent; speed?: number }) {
  return <CaptionBar {...(event ? captionFor(event) : { headline: 'Ready for a panorama', caption: 'Upload a JPEG or open a sealed run log.', actor: 'solver', source: 'Solver', t: 0 })} speed={speed} />;
}
function SupportRow(props: ElementProps) {
  const c = props.c as Candidate;
  return <div className="app-candidate">{mapTree(CandidateRow({ ...props, showDelta: c.delta !== null && props.showDelta !== false }), node => {
    if (props.compact && node.props.className === 'aq-cand-meta') return null;
    if (props.compact && node.props.className?.includes('aq-cand-v')) return React.cloneElement(node, {}, c.v === null ? 'unknown' : c.v.toFixed(2));
    if (node.props.className?.includes('aq-cand-c') && (c.sup === undefined || c.con === undefined)) return <span className="console-micro aq-ink3">evidence links not logged</span>;
    if (node.props.className?.includes('aq-cand-bar')) {
      if (c.v === null) return <span className="console-micro aq-ink3">support unknown</span>;
      return React.cloneElement(node, { 'aria-label': `support ${c.v.toFixed(2)}${c.lo !== undefined && c.hi !== undefined ? `, range ${c.lo.toFixed(2)} to ${c.hi.toFixed(2)}` : ''}` });
    }
    return node;
  })}<CandidateLocation candidate={c} /><p className="console-micro aq-ink3 app-candidate-role">{roleText(c.role)} · {c.r === null ? 'uncertainty unknown' : `± ${distance(c.r)}`}{props.compact ? '' : ` · ${String(c.details.extent_source ?? c.source ?? 'source not logged')}`}.</p></div>;
}
export function Candidates({ c, selected, onSelect, compact = false }: { c: CaseRecord; selected?: string; onSelect(id: string): void; compact?: boolean }) {
  const tree = CandidateList({ candidates: compact ? c.candidates.slice(0, 3) : c.candidates, selected, ruledOut: compact ? [] : c.ruledOut, title: 'Candidate answers', caption: compact ? 'Relative support' : 'Support · weight ÷ total weight · two decimals' });
  return <div onClick={e => { const id = (e.target as HTMLElement).closest('[data-link]')?.getAttribute('data-link'); if (id) onSelect(id); }} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { const id = (e.target as HTMLElement).closest('[data-link]')?.getAttribute('data-link'); if (id) { e.preventDefault(); onSelect(id); } } }}>
    {c.candidates.length ? mapTree(tree, node => node.type === CandidateRow ? <SupportRow {...node.props} compact={compact} max={node.props.max || 1} /> : node) : <EmptyState icon="pin" title="Candidates will appear here" body="The solver has not logged any candidate support." />}
    {!compact && c.candidates.length > 0 && <p className="console-micro aq-ink3 app-pad">Support is unnormalised fusion weight shown as a share; it is not a calibrated estimate of location.</p>}
  </div>;
}
export function Matrix({ c, candidate, selected, onSelect }: { c: CaseRecord; candidate?: string; selected?: string; onSelect(id: string): void }) {
  // The showcase totals count correlated rows more than once. The app supplies a corrected footer.
  const cols = candidate ? [candidate] : c.matrix.candidates;
  return <div className="app-matrix" onClick={e => { const id = (e.target as HTMLElement).closest('[data-link]')?.getAttribute('data-link'); if (id) onSelect(id); }}>
    {mapTree(EvidenceMatrix({ evidence: c.evidence, candidates: cols, names: c.matrix.names, groups: c.groups, selected }), node => {
      if (node.props.className?.includes('aq-mx-foot')) return React.cloneElement(node, {}, <><span className="console-micro aq-ink3">Sources (correlated rows count once)</span>{cols.map(id => {
        const supported = new Set(c.evidence.filter(e => (e.pol[id] ?? 0) > 0).map(e => e.group ?? e.id));
        const contradicted = new Set(c.evidence.filter(e => (e.pol[id] ?? 0) < 0).map(e => e.group ?? e.id));
        return <span className="console-data-sm" key={id}><span className="aq-c-support">{supported.size}</span> / <span className="aq-c-contra">{contradicted.size}</span></span>;
      })}</>);
      if (node.props['data-link']) return React.cloneElement(node, { tabIndex: 0, onKeyDown: (e: React.KeyboardEvent) => { if (e.key === 'Enter') onSelect(node.props['data-link']); } });
      return node;
    })}
  </div>;
}
export function Log({ events }: { events: RunEvent[] }) {
  const [filter, setFilter] = useState('all'), [selected, setSelected] = useState<number>();
  const rows = events.map(e => ({ ...e, model: e.model ? modelName(e.model, str(e.payload.kind)) : e.model, actor: e.actor === 'agent' ? 'solver' : e.actor, text: captionFor(e).caption }));
  return <>{mapTree(EventLog({ events: rows, filter }), node => {
    if (typeName(node) === 'Tabs') return React.cloneElement(node, { onChange: setFilter });
    if (node.type === 'li' && node.props.className?.includes('aq-log-r')) return React.cloneElement(node, { tabIndex: 0, onClick: () => setSelected(Number(node.key)), onKeyDown: (e: React.KeyboardEvent) => { if (e.key === 'Enter') setSelected(Number(node.key)); } });
    return node;
  })}{selected !== undefined && <pre className="aq-raw console-data-sm">{JSON.stringify(rows.filter(e => filter === 'all' || e.actor === filter)[selected], (key, value) => ['model', 'vlm', 'worded_by'].includes(key) && typeof value === 'string' ? modelName(value) : value, 2)}</pre>}</>;
}
export function ReplayControls({ events, t, speed, playing, onSeek, onPlay, onSpeed, compact = false }: { events: RunEvent[]; t: number; speed: 1 | 2 | 5; playing: boolean; onSeek(t: number): void; onPlay(): void; onSpeed(s: 1 | 2 | 5): void; compact?: boolean }) {
  const duration = events.at(-1)?.t || 1;
  const next = (direction: number) => { const times = [...new Set(events.map(e => e.t))]; onSeek(direction > 0 ? times.find(time => time > t) ?? duration : times.reverse().find(time => time < t) ?? 0); };
  const timeline: ReactNode[] = [];
  return <>{mapTree(ReplayScrubber({ events: events.map(e => ({ ...e, actor: e.actor === 'agent' ? 'solver' : e.actor })), t, duration, speed, playing }), node => {
    if (node.type === Button) return React.cloneElement(node, { onClick: node.props.icon === 'back' ? () => next(-1) : node.props.icon === 'forward' ? () => next(1) : onPlay });
    if (node.type === 'button' && node.props.role === 'radio') return React.cloneElement(node, { onClick: () => onSpeed(Number(node.key) as 1 | 2 | 5) });
    if (node.props.role === 'slider') {
      const slider = React.cloneElement(node, { 'aria-label': 'Replay time', onClick: (e: React.MouseEvent<HTMLDivElement>) => { const bounds = e.currentTarget.getBoundingClientRect(); onSeek(Math.max(0, Math.min(duration, (e.clientX - bounds.left) / bounds.width * duration))); }, onKeyDown: (e: React.KeyboardEvent) => { if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { e.preventDefault(); next(e.key === 'ArrowRight' ? 1 : -1); } else if (e.key === 'Home' || e.key === 'End') { e.preventDefault(); onSeek(e.key === 'Home' ? 0 : duration); } } });
      if (compact) { timeline.push(React.cloneElement(slider, { key: 'timeline-track' })); return null; } return slider;
    }
    if (compact && node.props.className?.includes('aq-scrub-legend')) { timeline.push(React.cloneElement(node, { key: 'timeline-legend' })); return null; }
    if (compact && node.props.className === 'aq-scrub') return React.cloneElement(node, {}, React.Children.map(node.props.children, child => React.isValidElement<ElementProps>(child) && child.props.className === 'aq-scrub-ctl' ? React.cloneElement(child, {}, child.props.children, <Disclosure title="Timeline" className="app-replay-details app-disclosure-float">{timeline}</Disclosure>) : child));
    return node;
  })}</>;
}
export function Coordinate({ a, onCopy, showCopy = true, size = 'md' }: { a: Output; onCopy(json?: boolean): void; showCopy?: boolean; size?: 'md' | 'lg' }) {
  return <>{mapTree(CoordinateBlock({ a, showCopy, size }), node => node.type === Button ? React.cloneElement(node, { onClick: () => onCopy(node.props.children === 'Copy as JSON') }) : node)}<p className="console-body aq-ink2">{roleText(a.role)}.</p></>;
}
export function Slots({ a }: { a: Output }) {
  const same = a.coordinates.length === 10 && a.coordinates.every(c => c.lat === a.lat && c.lng === a.lng);
  if (same) return <AnswerSlots a={a} producedAt={a.t} />;
  return <Panel title="Logged answer slots"><table className="aq-table console-data"><tbody>{a.coordinates.map(c => <tr key={c.rank}><td>{c.rank}</td><td>{coordinates(c.lat, c.lng)}</td><td>×{a.multiplier.toFixed(2)}</td><td>{time(a.t)}</td></tr>)}</tbody></table></Panel>;
}
export function Exports({ onCopy, onExport, onSubmit, canSubmit }: { onCopy(): void; onExport(): void; onSubmit(): void; canSubmit: boolean }) {
  return <>{mapTree(ExportBar({}), node => node.type === Button ? React.cloneElement(node, { disabled: node.props.icon === 'submit' && !canSubmit, onClick: node.props.icon === 'copy' ? onCopy : node.props.icon === 'download' ? onExport : onSubmit }) : node)}</>;
}
export function Modal({ title, children, actions, onClose }: { title: string; children: ReactNode; actions: ReactNode; onClose(): void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { const old = document.activeElement as HTMLElement; const element = ref.current!; const focusables = () => [...element.querySelectorAll<HTMLElement>('button:not([disabled]),textarea,input,a[href],[tabindex="0"]')]; focusables()[0]?.focus();
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.preventDefault(); onClose(); } if (e.key === 'Tab') { const list = focusables(), first = list[0], last = list.at(-1); if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); } } };
    element.addEventListener('keydown', key); return () => { element.removeEventListener('keydown', key); old?.focus(); };
  }, [onClose]);
  return <div ref={ref}><Dialog title={title} actions={actions}>{children}</Dialog></div>;
}
export function LiveStage({ c }: { c: CaseRecord }) {
  const stage = c.stages.find(s => s.status === 'running');
  return stage ? <ol className="aq-timeline-l aq-nowline" aria-live="polite"><LoggedStageRow stage={stage} /></ol> : null;
}
