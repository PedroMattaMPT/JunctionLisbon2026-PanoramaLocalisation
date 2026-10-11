import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Density, Badge, Button, EmptyState, Segmented, Toggle, Tabs, Toast, WaitState } from '@ds/base';
import { Wordmark, ShortcutBar, CleanStateCheck, ModelChip, GpuMeter } from '@ds/shell';
import { EvidenceCard, CorrelationBracket } from '@ds/reasoning';
import { AnswerReceipt } from '@ds/human';
import { ChoiceNote, ScoreCurve } from '@ds/output';
import { LanguageVote, SceneShares, EstimateBars, GainMeter } from '@ds/charts';
import { UncertaintyRing } from '@ds/map';
import { RANK_W } from '@ds/rt';
import { LiveSource, ReplaySource, parseLog, type DataSource, type WorkerStatus, type RunSummary } from './data';
import { emptyCase, reduce } from './reducer';
import { arr, record, str, type Category, type CaseRecord, type RunEvent } from './model';
import { loadPanorama, type PanoramaImage } from './images';
import { coordinates, modelName, time } from './format';
import { PanoramaColumn, Strip, Crop } from './panorama';
import { EvidenceMap, TileContext } from './map';
import { WorkerBanner } from './worker';
import { useEventMotion } from './motion';
import { Compare, LoggedMatch, Lookalikes, candidateReferences } from './compare';
import { CueView, QuestionView, copyText, optionLinks } from './human';
import { Caption, Candidates, Coordinate, Disclosure, EstimatedScore, Exports, LiveStage, Log, LinkedView, LoggedRoster, Matrix, Modal, Narrowing, Panel, ReplayControls, RunHeader, Slots, StageList, mapTree } from './ui';
import { FocusAnswer, FocusBar, FocusCandidates, FocusDetails, FocusIntake, FocusPhoto, FocusQuestion, FocusReplay, FocusRunTools, FocusWorking, QueueTutorial, type DetailTab, type QueueEntry } from './focus';
import { focusCandidate, focusCaseStatus, initialFullConsole } from './focus-model';
import { StreetWorkspace, type LocationView } from './streetview';
import { Welcome } from './welcome';
import { AnalysisFeed, DetectionFeed } from './activity';

interface SealedCase {
  key: string; label: string; file?: File; image?: PanoramaImage; imageUrl?: string; category: Category;
  categorySource: string; special: boolean; error?: string; events: RunEvent[]; mode: 'live' | 'replay';
  runId?: string; source?: DataSource; receivedAt?: number; status?: string;
}
const models = [
  ['views', 'py360convert', 'Prepares the panorama views'], ['yoloe', 'YOLOE-26-L', 'Detects useful objects'], ['sam3', 'SAM 3', 'Checks detection boxes'],
  ['ocr', 'PP-OCRv6-medium', 'Reads signs on the CPU'], ['language', 'Language ID', 'Votes across the logged languages'], ['qwen', 'Qwen3.5-9B', 'Answers a closed scene checklist'],
  ['gemma', 'Gemma 4 12B', 'Fallback checklist model'], ['eomt', 'EoMT', 'Measures visible scene shares'], ['pvlib', 'pvlib', 'Relates the sun to true north'],
  ['pe', 'PE-Core', 'Retrieves prepared reference photos'], ['pigeon', 'mini-PIGEON', 'Estimates regions'], ['geo', 'GeoCLIP / PLONK', 'Samples candidate coordinates'],
  ['names', 'Local name index', 'Finds landmark and area points'], ['mega', 'MegaLoc', 'Retrieves nearby camera references'], ['match', 'ALIKED + LightGlue', 'Checks geometric matches'],
].map(([id, name, role]) => ({ id, name: modelName(name), role, state: 'not reported', gb: 0 }));
const makeKey = () => crypto.randomUUID();
const messageOf = (error: unknown) => error instanceof Error ? error.message : String(error);
const keys = [{ k: '1–4', label: 'answer' }, { k: 'S', label: 'skip · free' }, { k: 'J/K', label: 'next / previous candidate or option' }, { k: '←/→', label: 'reference photo' }, { k: 'G', label: 'Street View / Compare' }, { k: 'F', label: 'hold to flicker' }, { k: '[ / ]', label: 'nearby street photo' }, { k: 'I', label: 'Details' }, { k: 'L', label: 'layers' }, { k: 'V', label: '360° focus' }, { k: 'M', label: 'map follows selection' }, { k: 'O', label: 'copy option links' }, { k: 'C', label: 'cue' }, { k: 'Space', label: 'replay' }, { k: '⇧⏎', label: 'review answer' }];
type Screen = 'welcome' | 'intake' | 'queue' | 'console' | 'answer' | 'report' | 'system';
function Receipt({ c }: { c: CaseRecord }) {
  const q = [...c.questions].reverse().find(q => q.status !== 'open');
  return q ? <Disclosure title="Last question" aside={q.status === 'skipped' ? 'Skipped · free' : `Answered ${q.answer ?? ''} · ×${q.multiplierAfter?.toFixed(2) ?? 'unknown'}`}><LoggedReceipt q={q} /></Disclosure> : null;
}
function LoggedReceipt({ q }: { q: CaseRecord['questions'][number] }) {
  return <>{mapTree(AnswerReceipt({ kind: q.status, q, before: q.before, after: q.after, multiplierBefore: q.multiplierBefore, multiplierAfter: q.multiplierAfter, t: q.resolvedAt }), node => node.type === EstimateBars && [...q.before, ...(q.after ?? [])].some(c => c.v === null) ? <EmptyState icon="estimate" title="Support unknown" body="No numeric share is drawn without a non-zero total weight." /> : node)}</>;
}
function EvidenceFeed({ c, selected, onSelect, focus = false }: { c: CaseRecord; selected?: string; onSelect(id: string): void; focus?: boolean }) {
  const render = (id: string) => {
    const e = c.evidence.find(e => e.id === id); if (!e) return null;
    return <div key={e.id} data-motion-id={e.id} data-leader={`card-${e.id}`} data-dim={selected && selected !== e.id ? 'true' : undefined} onClick={() => onSelect(e.id)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(e.id); } }}>
      <EvidenceCard e={e} names={c.matrix.names} selected={selected === e.id} />{!e.box && <p className="console-micro aq-ink3 app-evidence-note">Position not logged on the panorama.</p>}
    </div>;
  };
  const groups = new Set<string>();
  const current = c.evidence.find(e => e.id === selected) ?? c.evidence.at(-1);
  const evidence = focus ? current ? [current] : [] : [...c.evidence].reverse();
  return <div className="app-stack app-feed">{evidence.map(e => {
    if (!e.group) return render(e.id);
    if (groups.has(e.group)) return null; groups.add(e.group);
    const g = c.groups.find(g => g.id === e.group)!;
    return <CorrelationBracket key={g.id} label={g.label} cap={g.cap}>{(focus ? [e.id] : g.members).map(render)}</CorrelationBracket>;
  })}{!c.evidence.length && <EmptyState icon="model" title="Evidence will appear here" body="Every observation keeps its source and its real log time." />}{!focus && <>{c.language && c.language.length > 0 && <LanguageVote votes={c.language} />}{c.shares && <SceneShares shares={c.shares} masked={c.masked} />}{c.regions.length > 0 && <EstimateBars rows={c.regions} tone="model" title="Region estimates" />}</>}</div>;
}
function download(value: unknown, filename: string) { const blob = new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }), url = URL.createObjectURL(blob), a = document.createElement('a'); a.href = url; a.download = filename; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }

export function App() {
  const params = useMemo(() => new URLSearchParams(location.search), []), stageMode = params.get('mode') === 'stage';
  const consoleId = useRef(params.get('console') ?? makeKey());
  const [cases, setCases] = useState<SealedCase[]>([]), [active, setActive] = useState<string>(), [screen, setScreen] = useState<Screen>('welcome');
  const [tab, setTab] = useState('now'), [selected, setSelected] = useState<string>(), [compare, setCompare] = useState<string>(), [refIndex, setRefIndex] = useState(0);
  const [yaw, setYaw] = useState(0), [showLayers, setShowLayers] = useState(false), [layers, setLayers] = useState<Record<string, boolean>>({ sectors: true, mask: true, boxes: true, text: true, seg: true, sun: true });
  const [photoView, setPhotoView] = useState<'panorama' | '360'>('panorama'), [showCrop, setShowCrop] = useState(false);
  const [locationView, setLocationView] = useState<LocationView>('map');
  const [status, setStatus] = useState<WorkerStatus>(), [connected, setConnected] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState(''), [pending, setPending] = useState(false);
  const [queueHelp, setQueueHelp] = useState(false);
  const [replayTime, setReplayTime] = useState(0), [speed, setSpeed] = useState<1 | 2 | 5>(1), [playing, setPlaying] = useState(false), [animate, setAnimate] = useState(false);
  const [now, setNow] = useState(performance.now()), [sessionStart, setSessionStart] = useState<number>(), [cue, setCue] = useState(false), [submit, setSubmit] = useState(false), [importing, setImporting] = useState(false), [runs, setRuns] = useState<RunSummary[]>([]), [focusRevision, setFocusRevision] = useState(0);
  const [tileLayer, setTileLayerState] = useState(() => { try { return localStorage.getItem('aqui-tile-layer') ?? 'streets'; } catch { return 'streets'; } });
  const setTileLayer = useCallback((id: string) => { setTileLayerState(id); try { localStorage.setItem('aqui-tile-layer', id); } catch { /* per-viewer convenience only */ } }, []);
  const [skipAll, setSkipAll] = useState<string>();
  const [fullConsole, setFullConsole] = useState(() => { try { return initialFullConsole(location.search, localStorage); } catch { return initialFullConsole(location.search); } });
  const [detailsOpen, setDetailsOpen] = useState(false), [detailTab, setDetailTab] = useState<DetailTab>('evidence'), [optionSelection, setOptionSelection] = useState<string>(), [keyboardHelp, setKeyboardHelp] = useState(false);
  const closeDetails = useCallback(() => { setDetailsOpen(false); setCompare(undefined); setOptionSelection(undefined); }, []);
  const openDetails = (tab: DetailTab = 'evidence') => { setDetailTab(tab); setDetailsOpen(true); };
  const switchConsole = () => { const full = !fullConsole; setFullConsole(full); closeDetails(); try { localStorage.setItem('aqui-console-view', full ? 'full' : 'focus'); } catch { /* convenience only */ } const url = new URL(location.href); url.searchParams.set('view', full ? 'full' : 'focus'); history.replaceState(null, '', url); };
  const [stageSnapshot, setStageSnapshot] = useState<{ events: RunEvent[]; cursor: number; replay: boolean; speed: 1 | 2 | 5; key: string; image?: PanoramaImage; imageUrl?: string; label: string }>();
  const upload = useRef<HTMLInputElement>(null), importFiles = useRef<HTMLInputElement>(null), attachImage = useRef<HTMLInputElement>(null), folder = useRef<HTMLInputElement>(null);
  const heldImages = useRef(new Set<PanoramaImage>());
  const mounted = useRef(false);
  const root = useRef<HTMLDivElement>(null), source = useRef<LiveSource>(), subscriptions = useRef(new Map<string, () => void>()), channel = useRef<BroadcastChannel>(), busy = useRef(false), latestCases = useRef(cases), latestActive = useRef(active);
  latestCases.current = cases; latestActive.current = active;
  const item = cases.find(c => c.key === active);
  const events = stageMode ? stageSnapshot?.events ?? [] : item?.events ?? [];
  const isReplay = stageMode ? stageSnapshot?.replay ?? true : item?.mode === 'replay';
  const cursor = stageMode ? stageSnapshot?.cursor ?? 0 : isReplay ? replayTime : events.at(-1)?.t ?? 0;
  const reduced = useMemo(() => reduce(isReplay ? events.filter(e => e.t <= cursor) : events), [events, cursor, isReplay]);
  const c = useMemo(() => {
    const used = !isReplay && item?.receivedAt && !reduced.finished ? (events.at(-1)?.t ?? 0) + (now - item.receivedAt) / 1000 : cursor;
    return { ...reduced, label: stageMode ? stageSnapshot?.label ?? 'Stage' : item?.label ?? 'New case', size: item?.image ? [item.image.width, item.image.height] as [number, number] : undefined, run: { ...reduced.run, used }, stages: reduced.stages.map(s => s.status === 'running' ? { ...s, dur: Math.max(0, used - s.started) } : s) };
  }, [reduced, events, cursor, isReplay, item?.receivedAt, item?.image, item?.label, now, stageSnapshot?.label]);
  const cRef = useRef(c); cRef.current = c;
  const animateRef = useRef(animate); animateRef.current = animate;
  const statusRef = useRef(status); statusRef.current = status;
  const connectedRef = useRef(connected); connectedRef.current = connected;
  const image = stageMode ? stageSnapshot?.image : item?.image;
  const session = sessionStart ? (now - sessionStart) / 1000 : 0;
  useEventMotion(root, c, animate);
  useEffect(() => {
    const current = new Set(cases.flatMap(entry => entry.image ? [entry.image] : []));
    if (stageSnapshot?.image) current.add(stageSnapshot.image);
    heldImages.current.forEach(image => { if (!current.has(image)) image.dispose(); }); heldImages.current = current;
  }, [cases, stageSnapshot?.image]);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; queueMicrotask(() => { if (!mounted.current) heldImages.current.forEach(image => image.dispose()); }); }; }, []);
  useEffect(() => { const timer = setInterval(() => setNow(performance.now()), 1000); return () => clearInterval(timer); }, []);
  useEffect(() => { document.documentElement.dataset.theme = stageMode ? 'stage' : screen === 'report' ? 'light' : 'dark'; document.title = `Aqui · ${stageMode ? 'Stage' : item?.label ?? 'Panorama localisation'}`; }, [screen, stageMode, item?.label]);
  const checkStatus = useCallback(async () => { try { source.current ??= new LiveSource(); const s = await source.current.status(); setStatus(s); setConnected(true); setRuns(await source.current.list()); } catch { setConnected(false); } }, []);
  useEffect(() => { if (!stageMode) { void checkStatus(); const timer = setInterval(() => void checkStatus(), 5000); return () => { clearInterval(timer); subscriptions.current.forEach(stop => stop()); }; } }, [stageMode, checkStatus]);
  useEffect(() => { setSelected(undefined); setCompare(undefined); setYaw(0); setRefIndex(0); setCue(false); setSubmit(false); setPlaying(false); setTab('now'); setPhotoView('panorama'); setShowLayers(false); setShowCrop(false); setDetailsOpen(false); setOptionSelection(undefined); setLocationView('map'); }, [active]);
  useEffect(() => { setOptionSelection(undefined); }, [c.question?.id]);
  useEffect(() => {
    if (!playing || !isReplay || stageMode) return;
    let last = performance.now(); const timer = setInterval(() => { const now = performance.now(), delta = (now - last) / 1000 * speed; last = now; setAnimate(true); setReplayTime(t => { const end = events.at(-1)?.t ?? 0; if (t + delta >= end) setPlaying(false); return Math.min(end, t + delta); }); }, 100);
    return () => clearInterval(timer);
  }, [playing, isReplay, speed, events, stageMode]);
  const seek = (t: number) => { setPlaying(false); setAnimate(false); setReplayTime(t); };
  const play = () => { if (!playing && replayTime >= (events.at(-1)?.t ?? 0)) { setReplayTime(0); setAnimate(false); } setPlaying(v => !v); };
  const updateCase = (key: string, patch: Partial<SealedCase>) => setCases(list => list.map(c => c.key === key ? { ...c, ...patch } : c));
  const onEvent = (key: string, e: RunEvent) => {
    setAnimate(true); setCases(list => list.map(item => item.key === key && (!item.runId || e.run_id === item.runId) && !item.events.some(p => p.seq === e.seq) ? { ...item, events: [...item.events, e], receivedAt: performance.now() } : item));
  };
  useEffect(() => {
    const event = c.events.at(-1); if (!event || stageMode || !['console', 'answer'].includes(screen)) return;
    // Background events update the queue without leaving the screen the user chose.
    // A run can finish after free skips, keeping an output produced before the questions.
    // Final output and finish events can also arrive in the same React render.
    if (c.finished && c.answer) { setScreen('answer'); setCompare(undefined); return; }
    if (!animate) return;
    if (event.type === 'question.asked') { setScreen('console'); setCompare(undefined); }
    if (event.type === 'output.produced') { setScreen('answer'); setCompare(undefined); }
    if (event.type === 'stage.started' && event.stage === 'spot') setScreen('console');
    if (event.type === 'evidence.added') { const id = str(event.payload.evidence_id); if (['text', 'postcode', 'phone', 'road_number'].includes(str(event.payload.kind))) { setSelected(id); const e = c.evidence.find(e => e.id === id); if (e?.box) setYaw(e.box.yaw); } }
  }, [c.events.at(-1)?.seq, c.id]);
  useEffect(() => {
    const layers = status?.tile_layers ?? [];
    if (stageMode || isReplay || !item?.runId || !item.source || c.question?.status !== 'open' || !layers.some(l => l.id === tileLayer)) return;
    void item.source.prefetchTiles(item.runId, c.question.id, tileLayer).catch(() => { /* tiles are optional */ });
  }, [item?.runId, c.question?.id, c.question?.status, tileLayer, (status?.tile_layers ?? []).length]);
  // The stage channel carries exactly the active case, and clears image state on every case boundary.
  const broadcast = useCallback((includeImage = false) => {
    const activeItem = latestCases.current.find(v => v.key === latestActive.current); if (!activeItem) return;
    channel.current?.postMessage({ type: 'state', console: consoleId.current, key: activeItem.key, events: activeItem.events, cursor: cRef.current.run.used, replay: activeItem.mode === 'replay', speed, animate: animateRef.current, status: statusRef.current, connected: connectedRef.current, label: activeItem.label, ...(includeImage ? { imageFile: activeItem.file, imageUrl: activeItem.imageUrl } : {}) });
  }, [speed]);
  useEffect(() => {
    if (!('BroadcastChannel' in window)) return;
    const bus = new BroadcastChannel(`aqui-${consoleId.current}`); channel.current = bus;
    let alive = true;
    bus.onmessage = async message => {
      const p = record(message.data); if (p.console !== consoleId.current) return;
      if (!stageMode && p.type === 'hello') broadcast(true);
      if (stageMode && p.type === 'state') {
        const incoming = p.events as RunEvent[]; if (!Array.isArray(incoming)) return;
        setAnimate(p.animate === true); setConnected(p.connected === true); if (p.status) setStatus(p.status as WorkerStatus);
        setStageSnapshot(old => ({ events: incoming, cursor: Number(p.cursor) || 0, key: str(p.key), replay: p.replay === true, speed: [1, 2, 5].includes(Number(p.speed)) ? p.speed as 1 | 2 | 5 : 1, label: str(p.label, 'Stage'), image: old && old.key === p.key ? old.image : undefined }));
        if (p.imageFile instanceof File || typeof p.imageUrl === 'string') {
          try { const blob = p.imageFile instanceof File ? p.imageFile : await (await fetch(str(p.imageUrl))).blob(); const loaded = await loadPanorama(blob, p.imageFile instanceof File ? p.imageFile : undefined); if (alive) setStageSnapshot(old => { if (!old || old.key !== p.key) { loaded.dispose(); return old; } return { ...old, image: loaded }; }); else loaded.dispose(); } catch { /* missing image is shown explicitly */ }
        }
      }
    };
    if (stageMode) bus.postMessage({ type: 'hello', console: consoleId.current });
    return () => { alive = false; bus.close(); };
  }, [stageMode, broadcast]);
  useEffect(() => { if (!stageMode) broadcast(false); }, [c.events.at(-1)?.seq, active, cursor, c.run.used, status, connected]);
  useEffect(() => { if (!stageMode) broadcast(true); }, [active, item?.image]);
  const chooseEvidence = (id: string) => { setAnimate(false); setSelected(id); const e = c.evidence.find(e => e.id === id); if (e?.box) { setYaw(e.box.yaw); setShowCrop(true); } const candidate = c.candidates.find(v => v.evidence.includes(id) || v.supports.includes(id)); if (candidate) setCompare(undefined); };
  const chooseCandidate = (id: string) => {
    setAnimate(false); const candidate = c.candidates.find(v => v.id === id); if (!candidate) { chooseEvidence(id); return; }
    if (fullConsole && !detailsOpen) setScreen('console'); else openDetails('compare');
    setCompare(id); setRefIndex(0); const evidence = c.evidence.find(e => [...candidate.evidence, ...candidate.supports].includes(e.id) && e.box); setSelected(evidence?.id); if (evidence?.box) setYaw(evidence.box.yaw);
  };
  const action = async (work: () => Promise<void>) => {
    if (busy.current) return false; busy.current = true; setPending(true); setError('');
    try { await work(); return true; } catch (e) { setError(messageOf(e)); return false; } finally { busy.current = false; setPending(false); }
  };
  const answer = (optionId: string) => { if (item?.runId && item.source && c.question && !isReplay) void action(() => item.source!.answer(item.runId!, c.question!.id, optionId)); };
  const reviewAnswer = () => {
    if (!item?.runId || !item.source || !c.answer || isReplay) return;
    const entry = item, outputId = c.answer.id, after = item.events.at(-1)?.seq ?? 0;
    void action(async () => {
      await entry.source!.review(entry.runId!, outputId);
      subscriptions.current.get(entry.key)?.();
      subscriptions.current.set(entry.key, entry.source!.subscribe(entry.runId!, e => onEvent(entry.key, e), setConnected, after));
      await checkStatus();
    });
  };
  const skip = () => { if (item?.runId && item.source && c.question && !isReplay) void action(() => item.source!.skip(item.runId!, c.question!.id)); };
  // Skip the open question and every later one of a live run: free, neutral skips; the run finishes with its current output.
  const skipRemaining = (runId: string) => { source.current ??= new LiveSource(); const live = source.current; void action(async () => { await live.skipRemaining(runId); setSkipAll(undefined); setNotice('Remaining questions will be skipped: free, and the run finishes with its current output.'); await checkStatus(); }); };
  const sendCue = async (text: string) => { if (!item?.runId || !item.source || isReplay) return false; const sent = await action(() => item.source!.cue(item.runId!, text)); if (sent) setCue(false); return sent; };
  const copy = (json = false) => { if (!c.answer) return; void copyText(json ? JSON.stringify({ lat: c.answer.lat, lng: c.answer.lng }) : coordinates(c.answer.lat, c.answer.lng)).then(() => setNotice('Coordinates copied · latitude, longitude.')).catch(e => setError(messageOf(e))); };
  const exportLog = () => { if (item?.source && item.runId) void action(async () => download(await item.source!.log(item.runId!), 'log.json')); else download({ schema: 'panoloc.log/1', run_id: c.id, events }, 'log.json'); };
  const openStage = () => { const url = new URL(location.href); url.search = new URLSearchParams({ mode: 'stage', console: consoleId.current }).toString(); window.open(url, `aqui-stage-${consoleId.current}`); };
  async function addFiles(files: File[]) {
    setError(''); if (cases.length + files.length > 6) { setError('A session holds at most six sealed cases; remove a waiting file before adding another.'); return; }
    const additions: SealedCase[] = [];
    for (const file of files) {
      const key = makeKey(), base = { key, label: `Case ${cases.length + additions.length + 1}`, file, category: 'unknown' as Category, categorySource: 'unknown', special: false, events: [], mode: 'live' as const };
      try { const image = await loadPanorama(file, file); additions.push({ ...base, image }); } catch (e) { additions.push({ ...base, error: messageOf(e) }); }
    }
    setCases(list => [...list, ...additions]); if (!active) setActive(additions[0]?.key);
  }
  async function start() {
    const waiting = cases.filter(c => c.mode === 'live' && !c.runId && c.image && !c.error); if (!waiting.length) return;
    await action(async () => {
      source.current ??= new LiveSource(); const s = await source.current.status(); setStatus(s); setConnected(true); if (!sessionStart) setSessionStart(performance.now());
      const ordered = [...waiting].sort((a, b) => Number(b.key === active) - Number(a.key === active));
      for (const entry of ordered) {
        const runId = await source.current.start({ file: entry.file!, category: entry.category, categorySource: entry.categorySource, special: entry.special });
        updateCase(entry.key, { runId, source: source.current, receivedAt: performance.now() });
        subscriptions.current.set(entry.key, source.current.subscribe(runId, e => onEvent(entry.key, e), setConnected));
      }
      setActive(ordered[0].key); setScreen('console'); void checkStatus();
    });
  }
  async function replayFixture(name: string) {
    await action(async () => {
      const events = parseLog(await (await fetch(`/fixtures/${name}.events.jsonl`)).text());
      const scene = name === 'case-a' ? 'urban' : name === 'case-b' ? 'rural' : undefined;
      const imageUrl = scene ? `/fixtures/${scene}.svg` : undefined;
      const image = imageUrl ? await loadPanorama(await (await fetch(imageUrl)).blob()) : undefined;
      const key = makeKey(), source = new ReplaySource(events);
      const entry: SealedCase = { key, label: name === 'sample' ? 'Sample log' : `Invented ${scene === 'urban' ? 'Porto' : 'Alentejo'} case`, category: scene === 'urban' ? 'urban' : scene === 'rural' ? 'non-urban' : 'unknown', categorySource: 'official', special: false, events, mode: 'replay', runId: events[0].run_id, source, image, imageUrl };
      setCases(list => [...list.filter(c => c.mode !== 'replay'), entry]); setActive(key); setReplayTime(0); setSpeed(1); setPlaying(false); setAnimate(false); setImporting(false); setScreen('console');
    });
  }
  async function importRun(files: File[]) {
    await action(async () => {
      const log = files.find(f => /^(events\.jsonl|log\.json)$/i.test(f.name)) ?? files.find(f => /\.(jsonl|json)$/i.test(f.name));
      if (!log) throw new Error('Choose events.jsonl or log.json from one run folder.');
      if (log.size > 20 * 1024 * 1024) throw new Error('This log exceeds the 20 MB import limit.');
      const events = parseLog(await log.text()), panorama = events[0].panorama;
      const jpgs = files.filter(f => /\.jpe?g$/i.test(f.name));
      if (jpgs.length > 1) throw new Error('Open only one panorama with its log; cases must stay sealed.');
      const file = jpgs[0]; if (file && file.name !== panorama) throw new Error(`This log belongs to ${panorama}; the selected JPEG has a different filename.`);
      const image = file ? await loadPanorama(file, file) : undefined, key = makeKey();
      setCases(list => [...list.filter(c => c.mode !== 'replay'), { key, label: 'Replayed case', file, image, category: 'unknown', categorySource: 'unknown', special: false, events, mode: 'replay', runId: events[0].run_id, source: new ReplaySource(events) }]);
      setActive(key); setReplayTime(0); setAnimate(false); setImporting(false); setScreen('console');
    });
  }
  async function attach(file?: File) {
    if (!file || !item) return;
    await action(async () => { if (c.file && file.name !== c.file) throw new Error(`This sealed log belongs to ${c.file}; choose its panorama.`); const loaded = await loadPanorama(file, file); updateCase(item.key, { image: loaded, file }); });
  }
  async function openRun(runId: string) {
    await action(async () => {
      source.current ??= new LiveSource(); const exported = await source.current.log(runId); const events = parseLog(JSON.stringify(exported)); const key = makeKey();
      const state = reduce(events);
      const summary = runs.find(r => r.run_id === runId); const live = summary?.status !== 'finished' && summary?.status !== 'submitted';
      // Both backends keep the unchanged upload at <run_id>/<panorama> under /api/files (T76: reopen after a reload).
      const panorama = str(record(exported).panorama), imageUrl = panorama ? `/api/files/${encodeURIComponent(runId)}/${encodeURIComponent(panorama)}` : undefined;
      let image: PanoramaImage | undefined;
      if (imageUrl) { try { const r = await fetch(imageUrl); if (r.ok) image = await loadPanorama(await r.blob()); } catch { /* the strip says the file is unavailable */ } }
      setCases(list => [...list, { key, label: `Case ${list.length + 1}`, events, mode: live ? 'live' : 'replay', category: 'unknown', categorySource: 'unknown', special: summary?.special_one ?? false, runId, source: live ? source.current : new ReplaySource(events), receivedAt: performance.now(), image, imageUrl: image ? imageUrl : undefined }]);
      if (live) subscriptions.current.set(key, source.current.subscribe(runId, e => onEvent(key, e), setConnected, events.at(-1)?.seq));
      setActive(key); setReplayTime(events.at(-1)?.t ?? 0); setScreen(state.answer && (state.finished || !fullConsole && summary?.status === 'answer ready') ? 'answer' : 'console'); setImporting(false); setAnimate(false);
    });
  }
  const openCase = (entry: SealedCase) => {
    const state = reduce(entry.events);
    setActive(entry.key); setScreen(entry.runId ? state.answer && (state.finished || !fullConsole && runs.find(r => r.run_id === entry.runId)?.status === 'answer ready') ? 'answer' : 'console' : 'intake');
    if (entry.mode === 'live' && entry.runId && entry.source && !entry.events.some(e => e.type === 'stage.started')) void action(() => entry.source!.priority(entry.runId!));
  };
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (stageMode || screen === 'welcome' || (e.target as HTMLElement).closest('input,textarea,[contenteditable="true"]')) return;
      const k = e.key.toLowerCase();
      // Compare now lives in the Details sheet; retain its candidate/reference keys there.
      if (detailsOpen && detailTab === 'compare' && (e.target as HTMLElement).closest('.focus-sheet') && !root.current?.querySelector('[role="dialog"]:not(.focus-sheet)')) {
        if (k === 'j' || k === 'k') { const index = c.candidates.findIndex(v => v.id === compare), next = c.candidates[(index + (k === 'j' ? 1 : -1) + c.candidates.length) % c.candidates.length]; if (next) chooseCandidate(next.id); e.preventDefault(); }
        if (compare && (e.key === 'ArrowLeft' || e.key === 'ArrowRight') && !(e.target as HTMLElement).closest('[role="slider"],[role="tablist"],[role="radiogroup"],.app-viewer')) { const candidate = c.candidates.find(v => v.id === compare), count = candidate ? candidateReferences(c, candidate).length : 0; if (count > 1) { e.preventDefault(); setRefIndex(index => (index + (e.key === 'ArrowRight' ? 1 : -1) + count) % count); } }
        return;
      }
      if (root.current?.querySelector('[role="dialog"]')) return;
      if (k === ' ' && (e.target as HTMLElement).closest('summary,button,a,[role="button"]')) return;
      if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key) && (e.target as HTMLElement).closest('[role="slider"],[role="tablist"],[role="radiogroup"],.app-viewer')) return;
      const caseVisible = screen === 'console' || screen === 'answer';
      const questionVisible = caseVisible && !!c.question && (!fullConsole || screen === 'console');
      if (fullConsole && screen === 'queue' && /^[1-6]$/.test(k)) { const next = cases.filter(entry => !entry.error)[Number(k) - 1]; if (next) openCase(next); return; }
      if (questionVisible && !isReplay && /^[1-4]$/.test(k)) { const option = c.question!.options[Number(k) - 1]; if (option) answer(option.id); e.preventDefault(); return; }
      if (questionVisible && k === 's') { skip(); e.preventDefault(); return; }
      if (questionVisible && k === 'o') { const links = c.question!.options.flatMap(o => Object.values(optionLinks(o))).join('\n'); if (links) void copyText(links).catch(err => setError(messageOf(err))); return; }
      if (caseVisible && (k === 'j' || k === 'k')) {
        if (questionVisible) { const options = [...root.current!.querySelectorAll<HTMLElement>('[data-option-id]')], index = options.indexOf(document.activeElement as HTMLElement); options[(index + (k === 'j' ? 1 : -1) + options.length) % options.length]?.focus(); }
        else { const index = c.candidates.findIndex(v => v.id === compare); const next = c.candidates[(index + (k === 'j' ? 1 : -1) + c.candidates.length) % c.candidates.length]; if (next) chooseCandidate(next.id); }
      }
      if (compare && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) { const candidate = c.candidates.find(v => v.id === compare); const count = candidate ? candidateReferences(c, candidate).length : 0; if (count > 1) { e.preventDefault(); setRefIndex(index => (index + (e.key === 'ArrowRight' ? 1 : -1) + count) % count); } }
      if (k === 'i' && item) { e.preventDefault(); if (detailsOpen) closeDetails(); else openDetails(); }
      if (k === 'l') { setShowLayers(v => !v); if (!fullConsole) openDetails('run'); } if (k === 'm') setFocusRevision(v => v + 1);
      if (k === 'g' && c.answer && caseVisible && !questionVisible) { e.preventDefault(); setLocationView(view => view === 'streetview' ? 'compare' : 'streetview'); }
      if (k === 'v') { setPhotoView('360'); requestAnimationFrame(() => root.current?.querySelector<HTMLElement>('.app-viewer')?.focus()); }
      if (k === 'c' && !isReplay && item?.runId && !c.finished) setCue(true);
      if (k === ' ' && isReplay) { e.preventDefault(); play(); }
      if (e.key === 'Enter' && e.shiftKey && c.answer && !c.submitted) { e.preventDefault(); setSubmit(true); }
      if (e.key === 'Escape') { closeDetails(); setCue(false); setSubmit(false); setImporting(false); setKeyboardHelp(false); root.current?.querySelectorAll<HTMLDetailsElement>('nav details[open]').forEach(menu => { menu.open = false; }); }
    };
    window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key);
  });
  // Supply the arrow-key behavior omitted by the showcase Tabs / Segmented primitives.
  const arrowControls = (e: React.KeyboardEvent) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
    const target = e.target as HTMLElement, list = target.closest('[role="tablist"],[role="radiogroup"]'); if (!list || target.closest('.aq-q')) return;
    const buttons = [...list.querySelectorAll<HTMLElement>('button[role="tab"],button[role="radio"]')]; if (!buttons.includes(target)) return;
    const index = buttons.indexOf(target), next = e.key === 'Home' ? 0 : e.key === 'End' ? buttons.length - 1 : (index + (e.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length;
    e.preventDefault(); buttons[next]?.focus(); buttons[next]?.click();
  };
  const replayControls = isReplay && events.length > 0 && <ReplayControls events={events} t={cursor} speed={stageMode ? stageSnapshot?.speed ?? speed : speed} playing={playing} onSeek={seek} onPlay={play} onSpeed={setSpeed} compact={screen !== 'report'} />;
  const selectedCandidate = c.candidates.find(v => v.id === compare);
  const mapSelection = compare ?? c.candidates.find(v => selected && [...v.evidence, ...v.supports].includes(selected))?.id;
  const currentStage = c.stages.find(s => s.status === 'running');
  const currentEvent = c.events.at(-1);
  const answerDetails = c.answer && <>
    <Slots a={c.answer} />
    <ScoreCurve urban={c.answer.category} band={c.answer.r !== null ? [c.answer.r, c.answer.r] : undefined} multiplier={c.answer.multiplier} />
    <p className="console-micro aq-ink3">Estimate uses the logged radius as a distance proxy; the true location is never available.</p>
    <Button variant="quiet" icon="copy" onClick={() => copy(true)}>Copy coordinate as JSON</Button>
  </>;
  const reviewStarted = [...c.events].reverse().find(e => e.type === 'run.reopened')?.seq ?? 0;
  const reviewingAnswer = reviewStarted > 0 && !c.finished;
  const reviewDecision = [...c.evidence].reverse().find(e => e.kind === 'answer_review' || e.kind === 'review_failed' || e.kind === 'review_conflict');
  const reviewSummary = runs.find(r => r.run_id === item?.runId);
  const reviewContent = !stageMode && !isReplay && c.answer && (reviewSummary?.can_review !== undefined || reviewStarted > 0) ? <section className="answer-review" aria-label="Answer review">
    <Button variant="secondary" icon="question" disabled={pending || reviewingAnswer || !reviewSummary?.can_review || c.submitted} onClick={reviewAnswer}>{reviewingAnswer ? 'Thinking' : 'Investigate further'}</Button>
    <p className="console-micro aq-ink2">{reviewingAnswer ? 'The agent is reviewing this answer. Your current coordinates remain available.' : reviewSummary?.can_review ? 'Not convinced? Let the agent check the photo or ask you a question. A human answer costs ×0.95; skipping is free.' : 'Review limit reached for this answer.'}</p>
    {reviewDecision && reviewDecision.seq > reviewStarted && <p className="console-micro aq-ink3" role="status">{str(reviewDecision.payload.observation)}</p>}
  </section> : null;
  const finalContent = c.answer ? <div className="app-final app-stack">
    <h1 className="narrative-title">Best estimate</h1><Coordinate a={c.answer} onCopy={copy} showCopy={false} size={stageMode ? 'md' : 'lg'} />
    <p className="console-body aq-ink2">{c.answer.coordinates.length === 10 && c.answer.coordinates.every(p => p.lat === c.answer!.lat && p.lng === c.answer!.lng) ? 'Same coordinate in all 10 slots.' : `${c.answer.coordinates.length} logged answer slots.`}</p>
    {c.answer.expected !== null || c.answer.split ? <EstimatedScore expected={c.answer.expected} urbanUnknown={c.answer.split} special={c.answer.special} /> : <p className="console-body aq-ink3">Score estimate unavailable: position uncertainty is unknown.</p>}
    {c.answer.mostLikely === false && <ChoiceNote a={{ ...c.answer, mostLikely: false }} mostLikelyName={c.candidates[0]?.name} />}
    <Exports onCopy={() => copy()} onExport={exportLog} onSubmit={() => setSubmit(true)} canSubmit={!isReplay && !c.submitted && !pending} />
    {reviewContent}
    {stageMode ? answerDetails : <Disclosure title="Score curve and answer slots">{answerDetails}</Disclosure>}
    {c.outputs.length > 1 && <Disclosure title="Earlier outputs" aside={c.outputs.length - 1}>{c.outputs.slice(0, -1).map(a => <div className="app-history" key={a.id}><Coordinate a={a} onCopy={() => void copyText(coordinates(a.lat, a.lng))} /><span className="console-micro aq-ink3">Produced at {time(a.t)} · snapshot ×{a.multiplier.toFixed(2)}</span></div>)}</Disclosure>}
  </div> : <EmptyState icon="pin" title="No answer has been produced" body="The coordinate appears when output.produced arrives." />;

  function stageContent() {
    if (!stageSnapshot || !c.events.length) return <div className="aq-opening"><div className="aq-opening-l"><Wordmark size={64} /><h1 className="narrative-display">Where could here be?</h1><p className="stage-body aq-ink2">One panorama, its pixels and one best estimate.</p><p className="stage-label aq-ink3">Waiting for the operator console.</p></div><div className="aq-opening-r"><h2 className="stage-title">The local team</h2><ul className="aq-opening-models">{models.map(m => <li key={m.id}><ModelChip name={m.name} actor={['views', 'pvlib', 'names'].includes(m.id) ? 'solver' : 'model'} /><span className="stage-label aq-ink3">{m.role}</span></li>)}<li><ModelChip name="Solver" actor="solver" /><span className="stage-label aq-ink3">Weighs evidence and chooses the output</span></li><li><ModelChip name="Team" actor="team" /><span className="stage-label aq-ink3">Answers questions and supplies text cues</span></li></ul></div></div>;
    if (c.question) return <div className="app-stage-pair"><QuestionView q={c.question} evidence={c.evidence} disabled readOnly onAnswer={() => {}} onSkip={() => {}} onError={setError} brief /><EvidenceMap c={c} q={c.question} final={false} onSelect={() => {}} tileSource={status?.tile_source} animate={animate} /></div>;
    if (c.answer && (currentEvent?.type === 'output.produced' || c.finished || currentEvent?.type === 'run.submitted')) return <div className="app-stage-pair"><EvidenceMap c={c} final onSelect={() => {}} tileSource={status?.tile_source} animate={animate} />{finalContent}</div>;
    if (c.matches.length && currentStage?.id === 'spot') return <div className="app-stage-pair"><LoggedMatch c={c} image={image} e={c.matches.find(e => e.payload.accepted === true) ?? c.matches.at(-1)!} /><EvidenceMap c={c} onSelect={() => {}} tileSource={status?.tile_source} animate={animate} /></div>;
    if (c.candidates.length && (currentEvent?.type === 'candidates.updated' || ['geo', 'names', 'fuse'].includes(currentStage?.id ?? currentEvent?.stage ?? ''))) return <div className="app-stage-pair"><EvidenceMap c={c} onSelect={() => {}} tileSource={status?.tile_source} animate={animate} /><div className="app-stack"><Candidates c={{ ...c, candidates: c.candidates.slice(0, 3) }} onSelect={() => {}} />{c.evidence.at(-1) && <EvidenceCard e={c.evidence.at(-1)} names={c.matrix.names} />}</div></div>;
    const focus = [...c.evidence].reverse().find(e => e.box);
    return <div className="app-stage-pair"><div className="app-stack">{focus && <Crop c={c} image={image} evidence={focus} />}<Strip c={c} image={image} yaw={focus?.box?.yaw ?? yaw} layers={layers} selected={focus?.id} onSelect={() => {}} onYaw={() => {}} /></div><div className="app-stack">{c.evidence.at(-1) && <EvidenceCard e={c.evidence.at(-1)} names={c.matrix.names} selected />}{currentStage && <WaitState what="Thinking" elapsed={currentStage.dur ?? 0} deadline={currentStage.deadline ?? undefined} fallback={currentStage.fallback} />}<EvidenceMap c={c} onSelect={() => {}} tileSource={status?.tile_source} animate={animate} /></div></div>;
  }
  const tileChoice = { layers: status?.tile_layers ?? [], layer: tileLayer, setLayer: setTileLayer };
  const banner = (own?: string) => <WorkerBanner status={status} runs={runs} ownRunId={own} pending={pending} onSkipRemaining={setSkipAll} onOpen={runId => { const mine = cases.find(entry => entry.runId === runId); if (mine) openCase(mine); else void openRun(runId); }} />;
  const focusState = c.question ? 'question' : c.answer && (c.finished || screen === 'answer') ? 'answer' : 'working';
  const focusRecord = { ...c, candidates: focusState === 'working' ? c.candidates.slice(0, 3).map(focusCandidate) : [], evidence: c.evidence };
  const connectionContent = <><Panel title="Worker">{banner()}<Button variant="quiet" onClick={() => void checkStatus()}>Check connection</Button></Panel><Panel title="Readiness and local models"><CleanStateCheck caseLabel="every case" items={[{ label: 'New model conversation required for each run', ok: true }, { label: 'Empty evidence record for each run', ok: true }, { label: 'No state carried over between cases', ok: true }]} /><LoggedRoster status={status} models={models} />{status?.gpu.used_gb != null ? <GpuMeter used={status.gpu.used_gb} total={status.gpu.total_gb} /> : <p className="console-body aq-ink3">GPU memory not reported.</p>}</Panel><Panel title="Map tiles"><p className="console-body aq-ink2">{status?.tile_layers?.length ? status.tile_layers.map(layer => layer.name).join(', ') : status?.tile_source ? 'Local tiles configured' : 'Local outlines'}</p></Panel></>;
  const focusMenu = <><Button variant="quiet" icon="replay" onClick={() => setImporting(true)}>Replay a log</Button><Button variant="quiet" icon="photo" disabled={!item} onClick={() => attachImage.current?.click()}>Open this panorama</Button><Button variant="quiet" icon="forward" onClick={openStage}>Stage window</Button><Button variant="quiet" icon="file" disabled={!item} onClick={() => { closeDetails(); setScreen('report'); }}>Case report</Button><Button variant="quiet" icon="model" onClick={() => { closeDetails(); setScreen('system'); }}>System states</Button><Button variant="quiet" onClick={() => setKeyboardHelp(true)}>Keyboard shortcuts</Button><Button variant="quiet" pressed={fullConsole} onClick={switchConsole}>Full console</Button>{(screen === 'report' || screen === 'system') && <Button variant="quiet" onClick={() => item ? openCase(item) : setScreen('intake')}>Back to case</Button>}</>;
  const locationTabs = <Tabs label="Location view" tabs={[{ id: 'map', label: 'Map' }, { id: 'streetview', label: 'Street View' }, { id: 'compare', label: 'Compare' }]} value={locationView} onChange={(value: LocationView) => setLocationView(value)} />;
  const streetContent = c.answer && locationView !== 'map' && <StreetWorkspace key={`${active}:${c.answer.lat}:${c.answer.lng}`} c={c} image={image} point={c.answer} mode={locationView} yaw={yaw} setYaw={setYaw} />;
  function detailsContent() {
    if (detailTab === 'compare' && selectedCandidate) return <Compare c={c} candidate={selectedCandidate} image={image} yaw={yaw} setYaw={setYaw} refIndex={refIndex} setRefIndex={setRefIndex} onEvidence={chooseEvidence} onError={setError} onClose={() => { setCompare(undefined); setDetailTab('candidates'); }} />;
    if (detailTab === 'candidates' || detailTab === 'compare') return <Candidates c={c} selected={compare} onSelect={chooseCandidate} />;
    if (detailTab === 'questions') return c.questions.length ? c.questions.map(q => <div key={q.id} className="app-stack"><QuestionView q={q} evidence={c.evidence} disabled inspection onAnswer={() => {}} onSkip={() => {}} onError={setError} />{q.status !== 'open' && <>{q.gain === null ? <p className="console-data-sm aq-ink3">Expected gain not logged.</p> : <GainMeter gain={q.gain} breakEven={q.breakEven} cueLine />}<LoggedReceipt q={q} /></>}</div>) : <EmptyState icon="question" title="No questions yet" />;
    if (detailTab === 'stages') return <><StageList stages={c.stages} /><Narrowing c={c} /></>;
    if (detailTab === 'matrix') return <Matrix c={c} selected={selected} onSelect={chooseEvidence} />;
    if (detailTab === 'log') return <Log events={c.events} />;
    if (detailTab === 'run') return <><Panel title="Run metrics"><RunHeader c={c} status={status} connected={connected} session={session} speed={isReplay ? speed : undefined} /><p className="console-data-sm app-break aq-ink3">{c.file}</p></Panel>{isReplay && <Panel title="Timeline"><ReplayControls events={events} t={cursor} speed={speed} playing={playing} onSeek={seek} onPlay={play} onSpeed={setSpeed} /></Panel>}<FocusRunTools c={c} image={image} yaw={yaw} layers={layers} setLayers={setLayers} /><Panel title="Map key"><EvidenceMap c={c} q={c.questions.at(-1)} selected={mapSelection} onSelect={chooseCandidate} tileSource={status?.tile_source} /></Panel>{c.answer && <><Panel title="Output sources"><Coordinate a={c.answer} onCopy={copy} /><ChoiceNote a={c.answer} mostLikelyName={c.candidates[0]?.name} /><UncertaintyRing r={c.answer.r} source={c.answer.rSource} /><Button variant="quiet" icon="copy" onClick={() => copy(true)}>Copy coordinate as JSON</Button></Panel><Panel title="Score curve and answer slots"><ScoreCurve urban={c.answer.category} band={c.answer.r !== null ? [c.answer.r, c.answer.r] : undefined} multiplier={c.answer.multiplier} /><p className="console-micro aq-ink3">Estimate uses the logged radius as a distance proxy; the true location is never available.</p><table className="aq-table console-data-sm"><thead><tr><th>Slot</th><th>Latitude, longitude</th><th>Rank weight</th><th>Multiplier</th><th>Produced</th></tr></thead><tbody>{c.answer.coordinates.map((p, index) => <tr key={p.rank}><td>{p.rank}</td><td>{coordinates(p.lat, p.lng)}</td><td>{RANK_W[index]?.toFixed(2) ?? '—'}</td><td>×{c.answer!.multiplier.toFixed(2)}</td><td>{time(c.answer!.t)}</td></tr>)}</tbody></table></Panel>{c.outputs.length > 1 && <Panel title="Earlier outputs">{c.outputs.slice(0, -1).map(a => <div className="app-history" key={a.id}><Coordinate a={a} onCopy={() => void copyText(coordinates(a.lat, a.lng))} /><p className="console-micro aq-ink3">Produced at {time(a.t)} · snapshot ×{a.multiplier.toFixed(2)}</p></div>)}</Panel>}</>}<Panel title="Exports"><Button icon="download" onClick={exportLog}>Export JSON log</Button>{!isReplay && item?.runId && !c.finished && <Button icon="cue" cost={0.8} shortcut="C" onClick={() => setCue(true)}>Send a text cue</Button>}</Panel></>;
    return <EvidenceFeed c={c} selected={selected} onSelect={chooseEvidence} />;
  }
  const atSetup = screen === 'intake' || screen === 'queue';
  const queueEntries: QueueEntry[] = cases.map(entry => {
    const state = reduce(entry.events), summary = runs.find(run => run.run_id === entry.runId);
    const caseStatus = focusCaseStatus(state, !!entry.runId, summary?.status);
    const queueIndex = entry.runId ? (status?.queue ?? []).indexOf(entry.runId) : -1;
    return { key: entry.key, label: entry.label, filename: entry.file?.name ?? (state.file || undefined),
      special: entry.special || state.special, position: queueIndex >= 0 ? queueIndex + 1 : summary?.position,
      status: entry.error ? 'invalid' : summary?.status === 'failed' ? 'failed' : entry.mode === 'replay' ? 'replay' : caseStatus === 'waiting' ? entry.runId ? 'queued' : 'ready' : caseStatus,
      error: entry.error ?? summary?.error };
  });
  const setupContent = <FocusIntake files={cases.filter(entry => entry.mode === 'live')} queue={queueEntries} active={active} connected={connected} worker={status?.worker} pending={pending} workerContent={banner()} onHelp={() => setQueueHelp(true)}
    onChoose={() => upload.current?.click()} onFiles={files => void addFiles(files)} onStart={() => void start()} onCheck={() => void checkStatus()}
    onCategory={(key, category) => updateCase(key, { category, categorySource: category === 'unknown' ? 'unknown' : 'inferred' })} onSource={(key, categorySource) => updateCase(key, { categorySource })}
    onSpecial={(key, special) => setCases(list => list.map(entry => entry.key === key ? { ...entry, special } : special && !entry.runId ? { ...entry, special: false } : entry))}
    onRemove={key => { setCases(list => list.filter(entry => entry.key !== key)); if (active === key) setActive(cases.find(entry => entry.key !== key)?.key); }}
    onOpen={key => { const entry = cases.find(entry => entry.key === key); if (entry) openCase(entry); }} />;
  return <TileContext.Provider value={tileChoice}><Density value={stageMode ? 'stage' : 'console'} theme={stageMode ? 'stage' : screen === 'report' ? 'light' : 'dark'} className="app-root">
    <div ref={root} className={`app-shell ${stageMode ? 'app-stage' : fullConsole && screen !== 'welcome' ? '' : 'app-focus'}`} onKeyDown={arrowControls}>
      {!stageMode && screen !== 'welcome' && !fullConsole && <FocusBar cases={cases.map(entry => ({ key: entry.key, label: entry.label, special: entry.special || reduce(entry.events).special, status: entry.error ? 'invalid' : focusCaseStatus(entry.key === active ? c : reduce(entry.events), !!entry.runId, runs.find(r => r.run_id === entry.runId)?.status) }))} active={atSetup ? undefined : active} atSetup={atSetup} multiplier={c.penalty.multiplier} session={session} connected={connected} connection={connectionContent} menu={focusMenu} candidateCount={c.candidates.length} onCandidates={() => openDetails('candidates')} onCase={key => { closeDetails(); const entry = cases.find(entry => entry.key === key); if (entry) openCase(entry); }} onSetup={() => { closeDetails(); setScreen('intake'); }} />}
      {!stageMode && screen !== 'welcome' && fullConsole && <nav className="app-nav" aria-label="App screens">
        <Wordmark size={24} />{(['intake', 'console', 'answer'] as const).map(s => <Button key={s} variant="quiet" icon={s === 'intake' && !atSetup ? 'back' : undefined} pressed={s === 'intake' ? atSetup : screen === s} disabled={['console', 'answer'].includes(s) && !item} onClick={() => setScreen(s)}>{({ intake: atSetup ? 'Cases & queue' : 'Back to cases', console: 'Run', answer: 'Answer' })[s]}</Button>)}
        {c.candidates.length > 0 && item && <Button variant="secondary" icon="pin" onClick={() => openDetails('candidates')}>Candidate answers ({c.candidates.length})</Button>}
        <div className="app-nav-end"><Button icon="replay" onClick={() => setImporting(true)}>Replay a log</Button>
          <Disclosure title="Tools" className="app-tools app-disclosure-float">
            <div className="app-stack" onClick={e => { if ((e.target as HTMLElement).closest('button:not([disabled])')) { const menu = e.currentTarget.closest('details'); if (menu) menu.open = false; } }}>
              <Button variant="quiet" icon="photo" disabled={!item} onClick={() => attachImage.current?.click()}>Open this panorama</Button>
              <Button variant="quiet" icon="forward" onClick={openStage}>Stage window</Button>
              <Button variant="quiet" icon="file" disabled={!item} pressed={screen === 'report'} onClick={() => setScreen('report')}>Case report</Button>
              <Button variant="quiet" icon="model" pressed={screen === 'system'} onClick={() => setScreen('system')}>System states</Button>
              <Button variant="quiet" onClick={switchConsole}>Focus console</Button>
            </div>
            <Disclosure title="Keyboard shortcuts"><ShortcutBar keys={keys} /></Disclosure>
          </Disclosure>
        </div>
      </nav>}
      {(stageMode && c.events.length > 0 || fullConsole && screen !== 'welcome' && item && screen !== 'intake' && screen !== 'queue') && <RunHeader c={c} status={status} connected={connected} speed={isReplay ? stageSnapshot?.speed ?? speed : undefined} session={session} />}
      {error && <div className="app-alert"><Toast tone="contra" title={error} /><Button variant="quiet" icon="close" onClick={() => setError('')}>Dismiss</Button></div>}
      {notice && <div className="app-alert" role="status">{notice}<Button variant="quiet" onClick={() => setNotice('')}>Dismiss</Button></div>}
      {stageMode ? <>{stageContent()}<Caption event={currentEvent} speed={isReplay ? stageSnapshot?.speed : undefined} /></> : <>
        {screen === 'welcome' && <Welcome onStart={() => setScreen('intake')} />}
        {screen !== 'welcome' && !fullConsole && screen !== 'report' && screen !== 'system' && <>
          {atSetup || !item ? setupContent : <>
            {isReplay && <FocusReplay events={events} t={cursor} speed={speed} playing={playing} onSeek={seek} onPlay={play} onSpeed={setSpeed} />}
            <main className={`focus-layout is-${focusState} ${focusState === 'answer' && locationView === 'compare' ? 'has-compare' : ''}`} data-focus-state={focusState}>
              <div className="focus-main">{focusState === 'answer' && c.answer ? <><FocusAnswer a={c.answer} onCopy={() => copy()} onSubmit={() => setSubmit(true)} canSubmit={!isReplay && !c.submitted && !pending} onDetails={() => openDetails('run')} review={reviewContent} /><div className="focus-answer-photo"><FocusPhoto c={c} image={image} yaw={yaw} setYaw={setYaw} selected={selected} onSelect={chooseEvidence} layers={layers} view={photoView} setView={setPhotoView} /><Button variant="quiet" icon="camera" onClick={() => setLocationView('compare')}>Compare with street view</Button><DetectionFeed c={c} selected={selected} onSelect={chooseEvidence} /></div></> : <><FocusPhoto c={c} image={image} yaw={yaw} setYaw={setYaw} selected={selected} onSelect={chooseEvidence} layers={layers} view={photoView} setView={setPhotoView} busy={focusState === 'working' && (c.stages.some(stage => stage.status === 'running') || !isReplay && !!item.runId && !c.finished)} />{c.question ? <FocusQuestion c={c} disabled={isReplay || pending} readOnly={isReplay} onAnswer={answer} onSkip={skip} onSkipAll={!isReplay && item.runId ? () => setSkipAll(item.runId) : undefined} skippingAll={runs.find(r => r.run_id === item.runId)?.skip_remaining} onHighlight={setOptionSelection} onError={setError} onDetails={() => openDetails('questions')} /> : <FocusWorking c={c} event={currentEvent} image={image} selected={selected} onSelect={chooseEvidence} onDetails={() => openDetails()} />}</>}</div>
              <aside className="focus-map-column" aria-label={c.question ? 'Question options map' : 'Location view'}>{focusState !== 'question' && <FocusCandidates c={c} selected={compare} onSelect={chooseCandidate} onAll={() => openDetails('candidates')} />}{focusState === 'answer' && locationTabs}{focusState === 'answer' && locationView !== 'map' ? streetContent : <EvidenceMap c={focusRecord} selected={focusState === 'working' ? mapSelection : undefined} evidenceSelection={selected} onSelect={chooseCandidate} tileSource={status?.tile_source} q={c.question} optionSelection={optionSelection} final={focusState === 'answer'} animate={animate} focusRevision={focusRevision} compact focus aspect={c.candidates.length && focusState !== 'question' ? 0.5 : undefined} />}<AnalysisFeed c={c} selected={selected} onSelect={chooseEvidence} /></aside>
            </main>
          </>}
        </>}
        {(fullConsole && screen !== 'welcome' || screen === 'report' || screen === 'system') && <>
        {atSetup && setupContent}
        {screen === 'console' && item && <>{item.mode === 'live' && item.runId && !c.finished && status?.current !== item.runId && banner(item.runId)}<div className="app-replay-bar">{replayControls}{status?.mock && !isReplay && <Badge tone="outline">Scripted mock · invented evidence</Badge>}</div><LinkedView revision={currentEvent?.seq ?? 0} links={selected ? [[CSS.escape(`card-${selected}`), CSS.escape(selected)], [CSS.escape(`card-${selected}`), CSS.escape(`map-${selected}`)]] : []}>
          <div className="aq-col-pano app-pano"><PanoramaColumn c={c} image={image} yaw={yaw} setYaw={setYaw} selected={selected} onSelect={chooseEvidence} layers={layers} setLayers={setLayers} showLayers={showLayers} setShowLayers={setShowLayers} view={photoView} setView={setPhotoView} showCrop={showCrop} setShowCrop={setShowCrop} /></div>
          <div className="aq-col-reason app-reason">
            <Caption event={currentEvent} speed={isReplay ? speed : undefined} />
            {currentStage && (currentStage.dur ?? 0) > 10 ? <WaitState what="Thinking" elapsed={currentStage.dur} deadline={currentStage.deadline ?? undefined} fallback={currentStage.fallback} /> : <LiveStage c={c} />}
            {c.question ? <><QuestionView q={c.question} evidence={c.evidence} disabled={isReplay || pending} readOnly={isReplay} onAnswer={answer} onSkip={skip} onError={setError} />{!isReplay && item.runId && <div className="app-skip-rest app-pad"><Button variant="quiet" icon="skip" disabled={pending || runs.find(r => r.run_id === item.runId)?.skip_remaining === true} onClick={() => setSkipAll(item.runId)}>Skip remaining questions</Button><span className="console-micro aq-ink3">This and every later question · free · the run finishes with its current output</span></div>}</> : selectedCandidate ? <Compare c={c} candidate={selectedCandidate} image={image} yaw={yaw} setYaw={setYaw} refIndex={refIndex} setRefIndex={setRefIndex} onEvidence={chooseEvidence} onError={setError} onClose={() => setCompare(undefined)} /> : <>
              <Tabs tabs={[{ id: 'now', label: 'Now' }, { id: 'evidence', label: 'Evidence', count: c.evidence.length }, { id: 'stages', label: 'Stages' }, { id: 'matrix', label: 'Matrix' }, { id: 'log', label: 'Log' }]} value={tab} onChange={setTab} label="Reasoning views" />
              <div role="tabpanel" className="app-tab-panel">
                {tab === 'now' ? <div className="app-stack"><DetectionFeed c={c} selected={selected} onSelect={chooseEvidence} /><AnalysisFeed c={c} selected={selected} onSelect={chooseEvidence} />{selected && <EvidenceFeed c={c} selected={selected} onSelect={chooseEvidence} focus />}{c.evidence.length > 1 && <Button variant="quiet" onClick={() => setTab('evidence')}>View all {c.evidence.length} observations</Button>}<Receipt c={c} /></div> : tab === 'stages' ? <div aria-live="polite"><StageList stages={c.stages} /><Narrowing c={c} /><Receipt c={c} /></div> : tab === 'matrix' ? <Matrix c={c} selected={selected} onSelect={chooseEvidence} /> : tab === 'log' ? <Log events={c.events} /> : <EvidenceFeed c={c} selected={selected} onSelect={chooseEvidence} />}
              </div>
            </>}
          </div>
          <div className="aq-col-map app-map-column">
            <EvidenceMap c={c} selected={mapSelection} evidenceSelection={selected} onSelect={chooseCandidate} tileSource={status?.tile_source} q={c.question ?? c.questions.at(-1)} animate={animate} focusRevision={focusRevision} compact />
            <div className="app-pad app-stack"><Candidates c={c} selected={compare} onSelect={chooseCandidate} compact />{c.candidates.length > 0 && <Disclosure title="Candidate details" aside={`${c.candidates.length} candidates${c.ruledOut.length ? ` · ${c.ruledOut.length} ruled out` : ''}`}><Candidates c={c} selected={compare} onSelect={chooseCandidate} /></Disclosure>}</div>
            {!isReplay && !c.finished && <div className="app-pad app-skip-rest"><Button icon="cue" cost={0.8} shortcut="C" onClick={() => setCue(true)}>Send a text cue</Button>{item.runId && <Button variant="quiet" icon="skip" disabled={pending || runs.find(r => r.run_id === item.runId)?.skip_remaining === true} onClick={() => setSkipAll(item.runId)}>{runs.find(r => r.run_id === item.runId)?.skip_remaining ? 'Skipping remaining questions' : 'Skip remaining questions'}</Button>}</div>}
          </div>
        </LinkedView>{c.question && <ShortcutBar keys={[{ k: '1–4', label: 'answer (×0.95)' }, { k: 'S', label: 'skip (free)' }, { k: 'J/K', label: 'option focus' }, { k: 'O', label: 'copy links' }]} />}</>}
        {screen === 'answer' && item && <>{replayControls}<Caption event={currentEvent} speed={isReplay ? speed : undefined} /><div className="app-answer"><div className="app-stack"><FocusCandidates c={c} selected={compare} onSelect={chooseCandidate} onAll={() => openDetails('candidates')} />{locationTabs}{locationView === 'map' ? <EvidenceMap c={c} final onSelect={chooseCandidate} tileSource={status?.tile_source} animate={animate} compact /> : streetContent}<Disclosure title="Uncertainty source"><UncertaintyRing r={c.answer?.r ?? null} source={c.answer?.rSource} /></Disclosure></div>{finalContent}</div></>}
        {screen === 'report' && item && <article className="aq-report app-report"><header className="aq-report-h"><div className="aq-report-t"><h1 className="narrative-title">{c.label}: case report</h1><p className="console-body aq-ink2">{c.file} · {c.urban} ({c.urbanSource}) · elapsed {time(c.run.used)}</p><Badge tone="solver">Estimate · no true location available</Badge></div>{c.answer && <Coordinate a={c.answer} onCopy={copy} />}</header><Panel title="Replay and event log">{replayControls}<Log events={c.events} /></Panel><div className="app-report-pair"><Panel title="What supports what"><Matrix c={c} onSelect={chooseEvidence} /><Candidates c={c} selected={compare} onSelect={chooseCandidate} /></Panel><div className="app-stack"><Panel title="Questions and their costs">{c.questions.map(q => q.status === 'open' ? <QuestionView key={q.id} q={q} evidence={c.evidence} disabled readOnly onAnswer={() => {}} onSkip={() => {}} onError={setError} /> : <AnswerReceipt key={q.id} kind={q.status} q={q} before={q.before} after={q.after} multiplierBefore={q.multiplierBefore} multiplierAfter={q.multiplierAfter} t={q.resolvedAt} />)}</Panel><Lookalikes c={c} onEvidence={chooseEvidence} /><Panel title="Scene measurements">{c.language && <LanguageVote votes={c.language} />}{c.shares && <SceneShares shares={c.shares} masked={c.masked} />}<table className="aq-table console-data"><tbody>{[...(c.language ?? []), ...(c.shares ?? [])].map(p => <tr key={p.id}><td>{p.id}</td><td>{p.v.toFixed(2)}</td></tr>)}</tbody></table></Panel><Panel title="Export"><Button icon="download" onClick={exportLog}>Export JSON log</Button><Button icon="file" onClick={() => window.print()}>Print case report</Button></Panel></div></div></article>}
        {screen === 'system' && <div className="app-system">
          <Panel title="Worker connection"><Badge icon={connected ? 'online' : 'offline'}>{connected ? status?.mock ? 'Mock agent connected' : 'Agent connected' : 'No agent connected'}</Badge><p className="console-body aq-ink2">{connected ? 'HTTP actions and the event stream are available.' : 'The upload preview and replay still work; start the backend for a live run.'}</p><Button onClick={() => void checkStatus()}>Check connection</Button></Panel>
          <Panel title="Local models"><LoggedRoster status={status} models={models} />{status?.gpu.used_gb != null ? <GpuMeter used={status.gpu.used_gb} total={status.gpu.total_gb} /> : <p className="console-body aq-ink3">GPU memory not reported.</p>}</Panel>
          <Panel title="Stage outcomes"><StageList stages={c.stages.filter(s => ['failed', 'timed_out', 'skipped'].includes(s.status))} /><p className="console-body aq-ink3">Failed optional stages stay logged and the run continues without them.</p></Panel>
          <Panel title="Map tiles"><Badge icon="offline">{status?.tile_source || import.meta.env.VITE_TILE_SOURCE ? 'Local tiles configured; outlines are the fallback' : 'Local tiles unavailable · bundled PT / ES / FR outlines'}</Badge><EvidenceMap c={c} onSelect={chooseCandidate} /></Panel>
          <Panel title="Uncertainty and category"><UncertaintyRing r={c.answer?.r ?? null} source={c.answer?.rSource} /><ScoreCurve urban={c.urban} /><p className="console-body aq-ink3">Unknown radius stays unknown; an unknown Urban label shows both score curves.</p></Panel>
          <Panel title="No text or candidate"><EmptyState icon="language" title={c.texts.length ? `${c.texts.length} positioned readings logged` : 'No positioned text logged'} body="Language votes stay absent when no votes arrive." /><Candidates c={c} onSelect={chooseCandidate} /></Panel>
          <Panel title="Log validation"><p className="console-body aq-ink2">Malformed JSON is refused before import; unknown event types and evidence kinds remain in the Log tab.</p><Button icon="replay" onClick={() => setImporting(true)}>Open a log</Button></Panel>
        </div>}
        </>}
      </>}
      {!stageMode && detailsOpen && item && <FocusDetails tab={detailTab === 'compare' && !selectedCandidate ? 'candidates' : detailTab} onTab={setDetailTab} onClose={closeDetails} compare={!!selectedCandidate}>{detailsContent()}</FocusDetails>}
      <input ref={upload} type="file" className="app-hidden" multiple accept="image/jpeg,.jpg,.jpeg" onChange={e => { void addFiles([...(e.target.files ?? [])]); e.target.value = ''; }} />
      <input ref={importFiles} type="file" className="app-hidden" multiple accept=".json,.jsonl,.jpg,.jpeg" onChange={e => { void importRun([...(e.target.files ?? [])]); e.target.value = ''; }} />
      <input ref={folder} type="file" className="app-hidden" multiple {...{ webkitdirectory: '', directory: '' }} onChange={e => { void importRun([...(e.target.files ?? [])]); e.target.value = ''; }} />
      <input ref={attachImage} type="file" className="app-hidden" accept="image/jpeg,.jpg,.jpeg" onChange={e => { void attach(e.target.files?.[0]); e.target.value = ''; }} />
      {queueHelp && <QueueTutorial onClose={() => setQueueHelp(false)} />}
      {importing && <Modal title="Replay a sealed run" onClose={() => setImporting(false)} actions={<Button onClick={() => setImporting(false)}>Close</Button>}><div className="app-stack"><p>Select events.jsonl or log.json with its panorama JPEG, or open one run folder.</p><div className="aq-row"><Button icon="file" onClick={() => importFiles.current?.click()}>Choose log and panorama</Button><Button icon="file" onClick={() => folder.current?.click()}>Open a run folder</Button></div><div className="aq-row"><Button onClick={() => void replayFixture('case-a')}>Replay Porto</Button><Button onClick={() => void replayFixture('case-b')}>Replay Alentejo</Button><Button onClick={() => void replayFixture('sample')}>Replay sample</Button></div>{runs.length > 0 && <Panel title="Backend runs · status only">{runs.map(r => <Button key={r.run_id} icon="replay" onClick={() => void openRun(r.run_id)}>{r.run_id} · {r.status}{r.special_one ? ' · ×3' : ''}</Button>)}</Panel>}</div></Modal>}
      {skipAll && <Modal title="Skip the remaining questions?" onClose={() => setSkipAll(undefined)} actions={<><Button variant="quiet" onClick={() => setSkipAll(undefined)}>Go back</Button><Button variant="primary" icon="skip" disabled={pending} onClick={() => skipRemaining(skipAll)}>Skip remaining questions</Button></>}><p>The open question of <span className="console-data">{runs.find(r => r.run_id === skipAll)?.panorama ?? skipAll}</span> and every later one become skips. Skips are free and change nothing, so the run finishes with its current output and the worker moves on to the queue.</p></Modal>}
      {cue && <Modal title="Send a text cue" onClose={() => setCue(false)} actions={<Button onClick={() => setCue(false)}>Close</Button>}><CueView pending={pending} onSend={sendCue} /></Modal>}
      {keyboardHelp && <Modal title="Keyboard shortcuts" onClose={() => setKeyboardHelp(false)} actions={<Button onClick={() => setKeyboardHelp(false)}>Close</Button>}><ShortcutBar keys={keys} /></Modal>}
      {submit && c.answer && <Modal title={isReplay ? 'Review this replay answer' : 'Submit this answer?'} onClose={() => setSubmit(false)} actions={<><Button variant="quiet" onClick={() => setSubmit(false)}>Go back</Button><Button variant="primary" icon="submit" disabled={pending || isReplay} onClick={() => { if (item?.source && item.runId && !isReplay) void action(() => item.source!.submit(item.runId!, c.answer!.id)).then(ok => { if (ok) setSubmit(false); }); }}>Submit</Button></>}><p>{isReplay ? 'Recorded' : 'Sends'} {c.answer.coordinates.length} slots of <span className="console-data">{coordinates(c.answer.lat, c.answer.lng)}</span> (latitude, longitude), produced at <span className="console-data">×{c.answer.multiplier.toFixed(2)}</span>.</p></Modal>}
    </div>
  </Density></TileContext.Provider>;
}
