import React, { useEffect, useId, useRef, type ReactNode } from 'react';
import { Button, KeyCap, Segmented, Tabs } from '@ds/base';
import { Wordmark } from '@ds/shell';
import { QuestionOption } from '@ds/human';
import { CoordinateBlock } from '@ds/output';
import { LayerToggles } from '@ds/panorama';
import { Icon } from '@ds/icons';
import type { CaseRecord, Category, Option, Output, RunEvent } from './model';
import type { PanoramaImage } from './images';
import { distance, time } from './format';
import { DetectionFeed, Thinking } from './activity';
import { copyText, optionLinks } from './human';
import { Disclosure, Filename, Modal, Panel, UploadDropZone, mapTree } from './ui';
import { emptyCase, parseFilename } from './reducer';
import { Strip, Viewer, Crop, LoggedCompass } from './panorama';
import { focusOptions, plainLabel, uncertaintySentence } from './focus-model';
import { stageActivity } from './analysis-model';
import { CandidateLocation } from './candidate-location';
import { OptionProbability } from './human';

export interface CasePill { key: string; label: string; status: string; special: boolean }
export function FocusBar({ cases, active, atSetup, multiplier, session, connected, connection, menu, onCase, onSetup, candidateCount = 0, onCandidates }: {
  cases: CasePill[]; active?: string; atSetup: boolean; multiplier: number; session: number; connected: boolean;
  connection: ReactNode; menu: ReactNode; onCase(key: string): void; onSetup(): void;
  candidateCount?: number; onCandidates?(): void;
}) {
  const menuRef = useRef<HTMLDetailsElement>(null);
  useEffect(() => { const close = (event: PointerEvent) => { if (menuRef.current?.open && !menuRef.current.contains(event.target as Node)) menuRef.current.open = false; }; document.addEventListener('pointerdown', close); return () => document.removeEventListener('pointerdown', close); }, []);
  return <nav className="focus-bar" aria-label="Cases">
    <Wordmark size={24} />
    <Button variant="quiet" icon={atSetup ? 'layers' : 'back'} pressed={atSetup} onClick={onSetup}>{atSetup ? 'Cases & queue' : 'Back to cases'}</Button>
    <div className="focus-case-pills">{cases.map((entry, index) => <button key={entry.key} type="button" className={`focus-case is-${entry.status}`} aria-current={active === entry.key ? 'page' : undefined} aria-label={`${entry.label}: ${entry.status === 'question' ? 'needs an answer' : entry.status}${entry.special ? ', Special One' : ''}`} onClick={() => onCase(entry.key)}>
      {entry.special && <span aria-hidden="true">★</span>}<span>{index + 1}</span><span key={entry.status} className="focus-case-state" aria-hidden="true">{({ waiting: '·', working: '●', question: '?', done: '✓', submitted: '✓', invalid: '!' } as Record<string, string>)[entry.status]}</span>
    </button>)}</div>
    {!atSetup && candidateCount > 0 && onCandidates && <Button className="focus-candidate-shortcut" variant="secondary" icon="pin" onClick={onCandidates}>Candidate answers ({candidateCount})</Button>}
    <div className="focus-bar-end">
      <output className={`focus-multiplier console-data ${multiplier < 1 ? 'aq-c-cost' : ''}`} aria-label={`Current case multiplier ${multiplier.toFixed(2)}`}>×{multiplier.toFixed(2)}</output>
      <span className="console-data-sm focus-session" role="timer" aria-label="Session elapsed out of sixty minutes">{time(session)} / 60:00</span>
      <Disclosure title={<><span className={`focus-connection-dot ${connected ? 'is-online' : ''}`} aria-hidden="true" />Agent</>} className="focus-connection app-disclosure-float">{connection}</Disclosure>
      <details ref={menuRef} className="app-disclosure app-disclosure-float focus-menu"><summary aria-label="More">⋯</summary><div className="app-disclosure-body app-stack" onClick={e => { if ((e.target as HTMLElement).closest('button:not([disabled])')) { const element = e.currentTarget.closest('details'); if (element) element.open = false; } }}>{menu}</div></details>
    </div>
  </nav>;
}
export function DetailsLink({ onClick }: { onClick(): void }) { return <Button variant="quiet" shortcut="I" onClick={onClick}>Details</Button>; }
export function FocusPhoto({ c, image, yaw, setYaw, selected, onSelect, layers, view, setView, busy = false }: {
  c: CaseRecord; image?: PanoramaImage; yaw: number; setYaw(yaw: number): void; selected?: string;
  onSelect(id: string): void; layers: Record<string, boolean>; view: 'panorama' | '360'; setView(view: 'panorama' | '360'): void; busy?: boolean;
}) {
  return <section className="focus-photo" aria-label="Panorama"><header><span className="console-label">Panorama</span><Segmented label="Photo view" value={view} options={[{ id: 'panorama', label: 'Strip' }, { id: '360', label: '360°' }]} onChange={setView} /></header>
    <div className={`focus-photo-frame ${busy ? 'is-scanning' : ''}`}>{view === 'panorama' ? <Strip c={c} image={image} yaw={yaw} layers={layers} selected={selected} onSelect={onSelect} onYaw={setYaw} focus /> : <Viewer c={c} image={image} yaw={yaw} selected={selected} onYaw={setYaw} aspect={0.5} />}{busy && image && <div className="focus-scan-overlay" aria-hidden="true"><span /><i /><b /></div>}</div>
  </section>;
}
function FocusOption({ option, label, size, disabled, onAnswer, onHighlight, onError }: {
  option: Option; label: string; size: string; disabled: boolean; onAnswer(id: string): void;
  onHighlight(id?: string): void; onError(message: string): void;
}) {
  const id = useId(), links = optionLinks(option), wording = option.reason && !/^Reason not logged$/.test(option.reason);
  // Keep the DS colour/hatch and radio frame; long wording remains verbatim on focus/hover.
  const tree = QuestionOption({ o: option, brief: true, showLinks: false });
  return <div className="focus-option-wrap" onMouseEnter={() => onHighlight(option.id)} onMouseLeave={e => { if (!e.currentTarget.contains(document.activeElement)) onHighlight(); }} onFocus={() => onHighlight(option.id)} onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) onHighlight(); }}>
    {mapTree(tree, node => {
      if (node.props.className?.split(' ').includes('aq-qopt')) return React.cloneElement(node, { 'aria-disabled': disabled, 'aria-describedby': wording ? id : undefined, 'aria-label': `${option.key}: ${label}${size ? `, ${size}` : ''}`, 'data-option-id': option.id, onClick: () => { if (!disabled) onAnswer(option.id); }, onKeyDown: (e: React.KeyboardEvent) => { if (!disabled && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); onAnswer(option.id); } } });
      if (node.props.className === 'aq-qopt-b') return React.cloneElement(node, {}, <span className="focus-option-label console-heading">{label}</span>, size && <span className="focus-option-size console-data-sm aq-ink2">{size}</span>, <OptionProbability option={option} />);
      if (node.props.className === 'aq-qopt-act') return <span className="focus-option-shortcut"><KeyCap>{String('ABCD'.indexOf(option.key) + 1)}</KeyCap></span>;
      return node;
    })}
    {Object.keys(links).length > 0 && <div className="focus-option-links">{Object.entries(links).map(([name, url]) => <button key={name} type="button" className="focus-link-icon" aria-label={`Copy ${name.replaceAll('_', ' ')} link for ${label}`} title={`Copy ${name.replaceAll('_', ' ')} link`} onClick={() => void copyText(url).catch(error => onError(String(error.message)))}><Icon name={/street/i.test(name) ? 'camera' : /osm/i.test(name) ? 'map' : 'link'} /></button>)}</div>}
    {wording && <div id={id} role="tooltip" className="focus-option-wording console-body">{option.reason}</div>}
  </div>;
}
export function FocusQuestion({ c, disabled, readOnly, onAnswer, onSkip, onSkipAll, skippingAll, onHighlight, onError, onDetails }: {
  c: CaseRecord; disabled: boolean; readOnly: boolean; onAnswer(id: string): void; onSkip(): void;
  onSkipAll?: () => void; skippingAll?: boolean; onHighlight(id?: string): void; onError(message: string): void; onDetails(): void;
}) {
  const q = c.question!, costId = useId();
  return <section className="focus-question" aria-labelledby="focus-question-text">
    <header><span className="console-label aq-ink2">Question {c.questions.indexOf(q) + 1}</span>{q.gain !== null && <span className="console-micro aq-ink3">{q.gain > q.breakEven ? 'Worth asking' : 'Estimated gain'} ({q.gain >= 0 ? '+' : '−'}{Math.round(Math.abs(q.gain) * 100)}%)</span>}<DetailsLink onClick={onDetails} /></header>
    <h1 id="focus-question-text" className="console-title" aria-live="polite">{q.text}</h1>
    <div role="radiogroup" aria-label="Options" aria-describedby={costId} className="focus-options">{focusOptions(q).map(({ option, label, size }) => <FocusOption key={option.id} option={option} label={label} size={size} disabled={disabled} onAnswer={onAnswer} onHighlight={onHighlight} onError={onError} />)}</div>
    <div className="focus-question-footer"><Button variant="skip" icon="skip" shortcut="S" disabled={disabled} onClick={onSkip}>Skip</Button><p id={costId} className="console-body aq-ink2">An answer costs ×{q.cost.toFixed(2)}. Skip changes nothing.</p></div>
    <p className="console-micro aq-ink3">Agent probabilities are estimates.</p>
    {readOnly && <p className="console-micro aq-ink3">Replay · read-only</p>}
    {onSkipAll && <Button variant="quiet" disabled={disabled || skippingAll} onClick={onSkipAll}>{skippingAll ? 'Skipping remaining questions' : 'Skip all remaining questions'}</Button>}
  </section>;
}
export function FocusCandidates({ c, selected, onSelect, onAll }: { c: CaseRecord; selected?: string; onSelect(id: string): void; onAll?(): void }) {
  if (!c.candidates.length) return null;
  const leading = c.candidates.slice(0, 3);
  return <section className="focus-candidates" aria-label="Candidate answers">
    <header><div><h2 className="console-title">Candidate answers</h2><p className="console-micro aq-ink3">Ranked by relative support</p></div>{onAll && <Button variant="quiet" onClick={onAll}>View all {c.candidates.length}</Button>}</header>
    <div className="focus-candidate-grid">{leading.map(candidate => <article className="focus-candidate" data-link={candidate.id} data-selected={candidate.id === selected ? 'true' : undefined} key={candidate.id}>
      <button type="button" className="focus-candidate-select" aria-pressed={candidate.id === selected} aria-label={`Inspect candidate ${candidate.rank}: ${plainLabel(candidate.name)}`} onClick={() => onSelect(candidate.id)}>
        <span className="focus-candidate-rank console-data-sm">{candidate.rank}</span><span className="focus-candidate-main"><span className="console-heading">{plainLabel(candidate.name, candidate.role === 'camera' ? 'Reference photo' : 'Area estimate')}</span><span className="console-micro aq-ink3">{candidate.v === null ? 'Support unavailable' : `${Math.round(candidate.v * 100)}% support`}</span></span><Icon name="forward" />
        {candidate.v !== null && <span className="focus-support" role="img" aria-label={`Relative support ${candidate.v.toFixed(2)}`}><b style={{ width: `${Math.max(0, Math.min(1, candidate.v)) * 100}%` }} /></span>}
      </button>
      <CandidateLocation candidate={candidate} />
      <p className="focus-candidate-role console-micro aq-ink3">{{ camera: 'Camera location', area: 'Area centre', landmark: 'Landmark point' }[candidate.role] ?? 'Location'}{candidate.r !== null ? ` · ± ${distance(candidate.r)}` : ''}</p>
    </article>)}</div>
    {leading.some(v => v.role !== 'camera') && <p className="console-micro aq-ink3">Area centres and landmarks may differ from the camera position.</p>}
  </section>;
}
const steps = [
  { label: 'Read', ids: ['prepare', 'views', 'detect', 'read'] }, { label: 'Describe', ids: ['describe', 'measure'] },
  { label: 'Retrieve', ids: ['retrieve', 'geo', 'geoclip', 'landmarks', 'names'] }, { label: 'Fuse', ids: ['fuse', 'fusion'] }, { label: 'Ask', ids: ['ask', 'spot'] },
];
export function FocusWorking({ c, event, image, selected, onDetails, onSelect }: { c: CaseRecord; event?: RunEvent; image?: PanoramaImage; selected?: string; onDetails(): void; onSelect(id: string): void }) {
  const running = c.stages.filter(s => s.status === 'running'), stage = running.find(s => s.id === event?.stage) ?? running[0], evidence = c.evidence.find(e => e.id === selected);
  const busy = running.length > 0 || event?.type === 'stage.started';
  return <section className="focus-working"><div className="focus-activity">{busy ? <Thinking /> : <span className="console-heading">{c.finished ? 'Analysis finished' : 'Waiting for the next step'}</span>}{stage?.dur != null && <span className="console-data-sm aq-ink3">{Math.floor(stage.dur)} s</span>}<DetailsLink onClick={onDetails} /></div>
    <ol className="focus-stepper" aria-label="Run progress">{steps.map(step => { const rows = c.stages.filter(s => step.ids.includes(s.id)), running = rows.some(s => s.status === 'running'), done = rows.length > 0 && rows.every(s => s.status !== 'running'); return <li key={step.label} className={running ? 'is-running' : done ? 'is-done' : ''} aria-current={running ? 'step' : undefined}><span aria-hidden="true">{running ? '●' : done ? '✓' : '·'}</span>{step.label}</li>; })}</ol>
    {running.length > 0 && <div className="investigation-stages" aria-label="Current analysis tasks">{running.map(s => <div className="investigation-stage" key={s.id}><div><p className="console-body" role="status">{stageActivity(s)}</p><span className="console-micro aq-ink3">{s.name} · {Math.floor(s.dur ?? 0)} s elapsed</span></div>{s.progress?.completed !== null && s.progress?.completed !== undefined && s.progress.total !== null && <span className="console-data-sm investigation-progress">{s.progress.completed} / {s.progress.total} views</span>}</div>)}</div>}
    <DetectionFeed c={c} selected={selected} onSelect={onSelect} />{evidence?.box && image && <div className="focus-selected-crop"><Crop c={c} image={image} evidence={evidence} /></div>}
  </section>;
}
export function FocusAnswer({ a, onCopy, onSubmit, canSubmit, onDetails, review }: { a: Output; onCopy(): void; onSubmit(): void; canSubmit: boolean; onDetails(): void; review?: ReactNode }) {
  const number = (value: number) => Math.round(value * (a.special ? 3 : 1)).toLocaleString('en-US');
  return <section className="focus-answer-content"><h1 className="narrative-title">Best estimate{a.special && <span className="focus-special" aria-label="Special One">★</span>}</h1>
    {mapTree(CoordinateBlock({ a, showCopy: false, size: 'lg' }), node => node.props.className?.split(' ').includes('aq-coord-meta') || node.props.className?.includes('aq-coord-r') ? null : node)}
    <p className="console-body aq-ink2">{uncertaintySentence(a)}</p>
    {a.mostLikely === false && <p className="console-body aq-ink2">Chosen for its estimated score; it differs from the leading candidate.</p>}
    {(a.expected !== null || a.split) && <p className="console-body focus-score">Score estimate {a.split ? <>≈ {number(a.split.urban)} (urban) or ≈ {number(a.split.nonUrban)} (non-urban)</> : <>≈ {number(a.expected!)} ({a.category})</>}{a.special && <span className="console-micro aq-ink3"> · ×3</span>}</p>}
    <p className="console-body aq-ink2">×{a.multiplier.toFixed(2)} after {a.penalty.answered_questions} {a.penalty.answered_questions === 1 ? 'answer' : 'answers'}{a.penalty.cues > 0 ? `, ${a.penalty.cues} ${a.penalty.cues === 1 ? 'cue' : 'cues'}` : ''}{a.penalty.conversions > 0 ? `, ${a.penalty.conversions} ${a.penalty.conversions === 1 ? 'conversion' : 'conversions'}` : ''}</p>
    <Button variant="primary" icon="copy" onClick={onCopy}>Copy lat, lng</Button><Button variant="quiet" icon="submit" shortcut="⇧⏎" disabled={!canSubmit} onClick={onSubmit}>Submit answer</Button><DetailsLink onClick={onDetails} />
    {review}
  </section>;
}
export function FocusReplay({ events, t, speed, playing, onSeek, onPlay, onSpeed }: { events: RunEvent[]; t: number; speed: 1 | 2 | 5; playing: boolean; onSeek(t: number): void; onPlay(): void; onSpeed(speed: 1 | 2 | 5): void }) {
  const next = (direction: number) => { const target = direction > 0 ? events.find(e => e.t > t + 0.0001) : [...events].reverse().find(e => e.t < t - 0.0001); if (target) onSeek(target.t); };
  return <div className="focus-replay"><span className="console-micro aq-ink3">Replay</span><button type="button" className="aq-btn aq-btn-quiet" aria-label="Previous event" onClick={() => next(-1)}><Icon name="back" /></button><Button variant="quiet" icon={playing ? 'pause' : 'play'} onClick={onPlay}>{playing ? 'Pause' : 'Play'}</Button><button type="button" className="aq-btn aq-btn-quiet" aria-label="Next event" onClick={() => next(1)}><Icon name="forward" /></button><Segmented label="Replay speed" value={String(speed)} options={[1, 2, 5].map(v => ({ id: String(v), label: `${v}×` }))} onChange={(v: string) => onSpeed(Number(v) as 1 | 2 | 5)} /><span className="console-data-sm aq-ink3">{time(t)} / {time(events.at(-1)?.t ?? 0)}</span></div>;
}
export const detailTabs = ['evidence', 'candidates', 'questions', 'stages', 'matrix', 'log', 'run'] as const;
export type DetailTab = typeof detailTabs[number] | 'compare';
export function FocusDetails({ tab, onTab, onClose, children, compare }: { tab: DetailTab; onTab(tab: DetailTab): void; onClose(): void; children: ReactNode; compare: boolean }) {
  const ref = useRef<HTMLElement>(null), title = useId();
  useEffect(() => {
    const old = document.activeElement as HTMLElement;
    ref.current?.querySelector<HTMLElement>('button')?.focus();
    return () => { if (old?.isConnected) old.focus(); };
  }, []);
  useEffect(() => {
    // A selected row disappears when its comparison replaces the list.
    // Keep keyboard focus inside the sheet without moving a focused tab/input.
    if (ref.current && !ref.current.contains(document.activeElement)) ref.current.querySelector<HTMLElement>('button')?.focus();
  }, [tab]);
  const trap = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape' || e.key.toLowerCase() === 'i' && !(e.target as HTMLElement).closest('input,textarea,[contenteditable="true"]')) { e.stopPropagation(); e.preventDefault(); onClose(); }
    if (e.key !== 'Tab') return;
    const elements = [...ref.current!.querySelectorAll<HTMLElement>('button:not([disabled]),a[href],input,textarea,summary,[tabindex="0"]')].filter(el => el.getClientRects().length > 0 && el.getAttribute('aria-hidden') !== 'true');
    const first = elements[0], last = elements.at(-1);
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
  };
  return <div className="focus-sheet-backdrop" onClick={e => { if (e.target === e.currentTarget) onClose(); }}><aside ref={ref} className="focus-sheet" role="dialog" aria-modal="true" aria-labelledby={title} onKeyDown={trap}>
    <header className="focus-sheet-header"><h2 id={title} className="narrative-title">Details</h2><Button variant="quiet" icon="close" onClick={onClose}>Close details</Button></header>
    <Tabs tabs={[...detailTabs.map(id => ({ id, label: id[0].toUpperCase() + id.slice(1) })), ...(compare ? [{ id: 'compare', label: 'Compare' }] : [])]} value={tab} onChange={onTab} label="Details views" />
    <div role="tabpanel" aria-label={`${tab} details`} className="focus-sheet-body app-stack">{children}</div>
  </aside></div>;
}
export function FocusRunTools({ c, image, yaw, layers, setLayers }: { c: CaseRecord; image?: PanoramaImage; yaw: number; layers: Record<string, boolean>; setLayers(layers: Record<string, boolean>): void }) {
  return <Panel title="Layers and bearings"><p className="console-data-sm aq-ink3">{image ? `${image.width}×${image.height}` : 'Image not available'} · image yaw {Math.round(yaw)}°</p><LayerToggles layers={layers} counts={{ boxes: String(c.detections.length), text: String(c.texts.length), sectors: c.viewCount === undefined ? 'not logged' : String(c.viewCount) }} onChange={(key: string, value: boolean) => setLayers({ ...layers, [key]: value })} /><LoggedCompass c={c} yaw={yaw} /></Panel>;
}

interface IntakeFile {
  key: string; label: string; file?: File; image?: PanoramaImage; category: Category; categorySource: string; special: boolean; error?: string; runId?: string;
}
export interface QueueEntry extends CasePill { filename?: string; position?: number; error?: string }
const queueLabels: Record<string, string> = { ready: 'Ready to start', queued: 'Queued', working: 'Analysing', question: 'Needs your answer', done: 'Answer ready', submitted: 'Submitted', invalid: 'Check image', failed: 'Run failed', replay: 'Saved replay' };
const queueIcons: Record<string, string> = { ready: 'photo', queued: 'clock', working: 'model', question: 'question', done: 'done', submitted: 'done', invalid: 'warning', failed: 'warning', replay: 'replay' };
export function QueueTutorial({ onClose }: { onClose(): void }) {
  return <div className="focus-queue-tutorial"><Modal title="How the queue works" onClose={onClose} actions={<Button variant="primary" onClick={onClose}>Got it</Button>}>
    <p className="console-body">A separate investigation for every panorama, with one agent working through the queue.</p>
    <ol className="focus-tutorial-steps">
      <li><span aria-hidden="true">1</span><div><h3 className="console-heading">Prepare your cases</h3><p>Add up to six 360° JPEG panoramas. You can mark one as the Special One for ×3 scoring before you start.</p></div></li>
      <li><span aria-hidden="true">2</span><div><h3 className="console-heading">Start the queue</h3><p>The agent analyses one case at a time. The others wait, with their queue positions shown here. Open a queued case to move it to the front; the current case keeps running.</p></div></li>
      <li><span aria-hidden="true">3</span><div><h3 className="console-heading">Follow the clues</h3><p>Open a case to watch detections and the map. If the agent asks a question, answer it or skip for free so the queue can continue.</p></div></li>
      <li><span aria-hidden="true">4</span><div><h3 className="console-heading">Come back any time</h3><p>Use “Back to cases” to check progress or add more panoramas. Analysis continues while you are here. Open a completed case to review its answer.</p></div></li>
    </ol>
    <p className="console-micro aq-ink3"><Icon name="lock" /> Every case keeps its own images and evidence.</p>
  </Modal></div>;
}
export function FocusIntake({ files, queue, worker, connected, pending, active, workerContent, onHelp, onChoose, onFiles, onStart, onCheck, onCategory, onSource, onSpecial, onRemove, onOpen }: {
  files: IntakeFile[]; queue: QueueEntry[]; worker?: string; connected: boolean; pending: boolean; active?: string; workerContent: ReactNode; onHelp(): void;
  onChoose(): void; onFiles(files: File[]): void; onStart(): void; onCheck(): void;
  onCategory(key: string, category: Category): void; onSource(key: string, source: string): void; onSpecial(key: string, special: boolean): void; onRemove(key: string): void; onOpen(key: string): void;
}) {
  const lockedSpecial = files.some(file => file.special && file.runId);
  const prepared = files.filter(file => !file.runId), ready = prepared.filter(file => file.image && !file.error).length;
  const started = queue.some(entry => !['ready', 'invalid'].includes(entry.status));
  const working = queue.filter(entry => ['working', 'question'].includes(entry.status)).length, waiting = queue.filter(entry => entry.status === 'queued').length;
  const completed = queue.filter(entry => ['done', 'submitted'].includes(entry.status)).length;
  return <main className="focus-intake">
    <header className="focus-intake-heading"><div><span className="console-label aq-c-model">Your investigation desk</span><h1 className="narrative-title">Start the cases</h1><p className="console-body aq-ink2">From a panorama to a place. Prepare your images, follow the clues, and find the best location.</p></div><span className="console-data-sm focus-intake-capacity">{queue.length} / 6 cases</span></header>
    <ol className="focus-intake-journey" aria-label="Investigation steps">
      <li><Icon name="photo" /><div><strong className="console-heading">Add a panorama</strong><p>Each image gets its own case.</p></div><span aria-hidden="true">01</span></li>
      <li><Icon name="model" /><div><strong className="console-heading">Watch the clues appear</strong><p>Detections guide the map closer.</p></div><span aria-hidden="true">02</span></li>
      <li><Icon name="crosshair" /><div><strong className="console-heading">Review the location</strong><p>See the estimate and its uncertainty.</p></div><span aria-hidden="true">03</span></li>
    </ol>
    <div className={`focus-intake-grid ${started ? 'has-started' : ''}`}><section className="focus-intake-preparation" aria-labelledby="prepare-cases-title">
    <header className="focus-section-heading"><div><h2 id="prepare-cases-title" className="console-title">Your panoramas</h2><p className="console-body aq-ink2">Add up to six images to this session.</p></div><Icon name="drop" /></header>
    {queue.length < 6 ? <div className="focus-intake-drop" onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); onFiles([...e.dataTransfer.files]); }}><UploadDropZone onChoose={onChoose} /></div> : <p className="console-body focus-intake-full"><Icon name="done" /> All six case slots are filled. Open a case from your queue to follow its progress.</p>}
    <div className="focus-intake-files">{prepared.map(entry => { const warning = entry.error ?? entry.image?.warning ?? (!parseFilename(entry.file?.name ?? '').date ? 'Filename does not parse; the image is still accepted.' : undefined); return <section className="focus-intake-file" id={`prepare-${entry.key}`} tabIndex={-1} aria-label={`Prepare ${entry.label}`} key={entry.key}>
      <div className="focus-file-row"><span className={`console-heading ${warning ? 'aq-c-cost' : 'aq-c-support'}`} title={warning} aria-label={warning ? `Warning: ${warning}` : 'Valid image'}>{warning ? '!' : '✓'}</span><span className="console-data-sm focus-file-name">{entry.file?.name ?? entry.label}</span><span className="console-data-sm aq-ink3">{entry.image ? `${entry.image.width}×${entry.image.height}` : ''}{entry.file ? ` · ${(entry.file.size / (1024 * 1024)).toFixed(1)} MB` : ''}</span>
        <label className="focus-special-radio console-label"><input type="radio" name="focus-special-one" checked={entry.special} disabled={!!entry.runId || !!entry.error || lockedSpecial} onChange={() => onSpecial(entry.key, true)} aria-label={`Special One: ${entry.file?.name ?? entry.label}`} /><span aria-hidden="true">★</span> Special One</label>
        <Button variant="quiet" icon="close" onClick={() => onRemove(entry.key)}>Remove</Button>
      </div>
      {entry.error && <p role="alert" className="console-body aq-c-cost">{entry.error}</p>}
      <Disclosure title="Advanced"><Filename file={entry.file?.name ?? entry.label} urban={entry.category} source={entry.categorySource} special={entry.special} size={entry.image ? [entry.image.width, entry.image.height] : undefined} status={entry.error ? 'error' : warning ? 'warning' : 'valid'} message={warning} editable={false} />
        {!entry.runId && !entry.error && <><Segmented label={`${entry.label} Urban label`} value={entry.category} options={[{ id: 'unknown', label: 'Unknown' }, { id: 'urban', label: 'Urban' }, { id: 'non-urban', label: 'Non-urban' }]} onChange={(v: Category) => onCategory(entry.key, v)} />{entry.category !== 'unknown' && <Segmented label={`${entry.label} Label source`} value={entry.categorySource} options={[{ id: 'inferred', label: 'Inferred' }, { id: 'official', label: 'Official (revealed)' }]} onChange={(v: string) => onSource(entry.key, v)} />}{entry.special && <Button variant="quiet" onClick={() => onSpecial(entry.key, false)}>Unmark Special One</Button>}</>}
        {entry.image && <Panel title="Local preview"><Strip c={{ ...emptyCase(), file: entry.file?.name ?? '', size: [entry.image.width, entry.image.height] }} image={entry.image} yaw={0} layers={{}} onSelect={() => {}} onYaw={() => {}} focus /></Panel>}
      </Disclosure>
    </section>; })}</div>
    <div className="focus-intake-note"><span aria-hidden="true">★</span><div><h3 className="console-heading">One case can be your Special One</h3><p className="console-body aq-ink2">Mark it before starting for ×3 scoring. Every panorama is investigated independently.</p></div></div>
    <footer className="focus-intake-footer"><Button variant="primary" icon="play" disabled={pending || !connected || !ready} busy={pending ? 'Starting' : undefined} onClick={onStart}>{started ? `Add ${ready || 'new'} case${ready === 1 ? '' : 's'} to queue` : ready ? `Start ${ready} case${ready === 1 ? '' : 's'}` : 'Start the cases'}</Button><p className="console-micro aq-ink3">{ready ? `${ready} panorama${ready === 1 ? '' : 's'} ready${waiting || working ? ' · joins the existing queue' : ''}.` : queue.length === 6 ? 'Your session is full.' : 'Choose a panorama to begin.'}</p></footer>
    </section>
    <aside className="focus-intake-queue" aria-labelledby="cases-queue-title">
      <header className="focus-section-heading"><div><h2 id="cases-queue-title" className="console-title">Your queue</h2><p className="console-body aq-ink2">One agent, one case at a time.</p></div><button type="button" className="focus-queue-info" aria-label="How the queue works" title="How the queue works" onClick={onHelp}><Icon name="info" /></button></header>
      <div className="focus-queue-worker" role="status"><span className={`focus-connection-dot ${connected ? 'is-online' : ''}`} aria-hidden="true" /><span className="console-label">{!connected ? 'Agent disconnected' : worker && worker !== 'online' && worker !== 'replay' ? `Agent ${worker}` : 'Agent connected'}</span>{!connected && <Button variant="quiet" onClick={onCheck}>Reconnect</Button>}</div>
      {queue.length ? <>
        <div className="focus-queue-counts" aria-label="Queue summary"><span><b className="console-data">{started ? working : ready}</b> {started ? 'active' : 'ready'}</span><span><b className="console-data">{waiting}</b> queued</span><span><b className="console-data">{completed}</b> complete</span></div>
        <ol className="focus-queue-list">{queue.map((entry, index) => <li key={entry.key} className={`focus-queue-entry is-${entry.status}`}>
          <span className="focus-queue-number console-data-sm" aria-hidden="true">{String(index + 1).padStart(2, '0')}</span><div className="focus-queue-case"><div className="focus-queue-case-heading"><strong className="console-heading">{entry.label}</strong>{entry.special && <span className="console-label aq-c-solver">★ ×3</span>}</div>{entry.filename && <span className="console-micro aq-ink3 focus-queue-filename">{entry.filename}</span>}<span className="console-label focus-queue-status"><Icon name={queueIcons[entry.status] ?? 'info'} />{queueLabels[entry.status] ?? entry.status}{entry.status === 'queued' && entry.position !== undefined ? ` · #${entry.position} in queue` : ''}</span>{entry.error && <p className="console-micro aq-c-cost">{entry.error}</p>}</div>
          <Button variant="quiet" icon="chevronRight" onClick={() => { onOpen(entry.key); if (['ready', 'invalid'].includes(entry.status)) { const preparation = document.getElementById(`prepare-${entry.key}`); preparation?.focus({ preventScroll: true }); preparation?.scrollIntoView({ block: 'center', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' }); } }}>{entry.status === 'ready' || entry.status === 'invalid' ? 'Edit' : entry.status === 'question' ? 'Answer' : ['done', 'submitted'].includes(entry.status) ? 'Review' : 'Open'}<span className="app-sr-only"> {entry.label}</span></Button>
        </li>)}</ol>
        {active && queue.some(entry => entry.key === active && !['ready', 'invalid'].includes(entry.status)) && <Button variant="quiet" icon="forward" onClick={() => onOpen(active)}>Return to current case</Button>}
      </> : <div className="focus-queue-empty"><div className="focus-queue-empty-slots" aria-hidden="true"><span><Icon name="photo" /></span><span><Icon name="photo" /></span><span><Icon name="photo" /></span></div><h3 className="console-heading">Your next discovery starts here</h3><p className="console-body aq-ink2">Add a panorama to your session. After you start, this is where you can follow every case and see what needs your attention.</p><Button variant="quiet" icon="info" onClick={onHelp}>Take a quick tour</Button></div>}
      {workerContent}
      <p className="console-micro aq-ink3 focus-queue-reassurance"><Icon name="lock" /> You can return here while the agent works. Your cases keep progressing.</p>
    </aside></div>
  </main>;
}
