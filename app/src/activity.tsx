import React from 'react';
import type { CaseRecord } from './model';
import { plainLabel } from './focus-model';
import { analysisTitle, explanationFor, featuresFor, findingTitle, isReading } from './analysis-model';
import { modelName, time } from './format';

/** Ambient activity, never a fabricated completion percentage or detection. */
export function Thinking({ label = 'Thinking', compact = false }: { label?: string; compact?: boolean }) {
  return <div className={`thinking ${compact ? 'is-compact' : ''}`} role="status">
    <span className="thinking-orbit" aria-hidden="true"><i /><i /><i /><b /></span>
    <span className="console-heading">{label}<span className="thinking-dots" aria-hidden="true"><i /><i /><i /></span></span>
  </div>;
}

export function DetectionFeed({ c, selected, onSelect }: { c: CaseRecord; selected?: string; onSelect(id: string): void }) {
  const findings = c.evidence.filter(e => e.box || isReading(e.kind) || ['object', 'checklist', 'vlm_checklist', 'landmark_hypothesis'].includes(e.kind)).slice().reverse();
  const objects = c.evidence.filter(e => e.kind === 'object' && e.payload.kept !== false).length;
  const readings = c.evidence.filter(e => ['text', 'ocr_text', 'postcode', 'phone', 'road_number'].includes(e.kind) && !e.payload.ocr_evidence_id).length;
  if (!findings.length) return null;
  return <section className="focus-findings" aria-label="Detections and readings">
    <header><span className="console-label">Detected features</span><span className="console-micro aq-ink3">{objects} {objects === 1 ? 'object' : 'objects'} · {readings} {readings === 1 ? 'reading' : 'readings'} · {c.evidence.filter(e => e.kind === 'vlm_checklist').length} scene views</span></header>
    <div className="investigation-findings" tabIndex={0} aria-label="All detected features, newest first">{findings.map(e => {
      const features = featuresFor(e), observed = features.filter(f => !f.unknown), unclear = features.filter(f => f.unknown);
      const feature = (f: ReturnType<typeof featuresFor>[number]) => <span key={f.key} className={`investigation-feature ${f.unknown ? 'is-unknown' : ''}`} data-feature={f.key}><span className="console-micro aq-ink3">{f.label}</span><span className="console-body">{f.description}</span></span>;
      return <div key={e.id} className={`investigation-finding ${e.kind === 'vlm_checklist' ? 'is-scene' : ''} ${e.payload.kept === false ? 'is-rejected' : ''}`} data-motion-id={e.id} data-selected={e.id === selected ? 'true' : undefined}>
        <button type="button" className="investigation-finding-select" aria-pressed={e.id === selected} onClick={() => onSelect(e.id)}>
        <span className="investigation-finding-heading"><span className="focus-finding-mark" aria-hidden="true">{isReading(e.kind) ? 'Aa' : '⌖'}</span><span className="console-heading">{findingTitle(e)}</span><span className="console-data-sm aq-ink3">{time(e.t)}</span></span>
        {observed.length > 0 && <span className="investigation-features">{observed.map(feature)}</span>}
        {features.length > 0 && !observed.length && <span className="console-body aq-ink3">No clear scene feature in this view.</span>}
        <span className="console-micro aq-ink3">{plainLabel(modelName(e.model, e.kind), 'Model observation')}{e.box && e.kind !== 'vlm_checklist' ? ` · ${Math.round(e.box.yaw)}°` : ''}{!e.box ? ' · image position unavailable' : e.kind === 'vlm_checklist' ? ' · inspected view' : ' · select to inspect pixels'}{e.payload.kept === false ? ' · rejected' : ''}</span>
        </button>
        {unclear.length > 0 && <details className="investigation-unknown-checks"><summary className="console-micro aq-ink3">{unclear.length} unclear or unseen features</summary><div className="investigation-features">{unclear.map(feature)}</div></details>}
      </div>;
    })}</div>
  </section>;
}

export function AnalysisFeed({ c, selected, onSelect }: { c: CaseRecord; selected?: string; onSelect(id: string): void }) {
  const explanations = c.evidence.flatMap(e => { const text = explanationFor(e); return text ? [{ e, text }] : []; }).reverse();
  return <section className="investigation-analysis" aria-label="Analysis summaries">
    <header><h2 className="console-heading">How the clues connect</h2><span className="console-micro aq-ink3">{explanations.length} updates</span></header>
    <p className="investigation-announcement" role="status" aria-live="polite">{explanations[0]?.text ?? 'Explanations appear as observations are checked.'}</p>
    {explanations.length ? <ol className="investigation-trail" tabIndex={0} aria-label="Evidence explanations, newest first">{explanations.map(({ e, text }) => <li key={e.id} data-motion-id={e.id} className={`is-${e.actor}`}>
      <button type="button" aria-pressed={selected === e.id} onClick={() => onSelect(e.id)}><span className="investigation-trail-heading"><span className="console-label">{analysisTitle(e)}</span><span className="console-data-sm aq-ink3">{time(e.t)}</span></span><span className="console-body">{text}</span><span className="console-micro aq-ink3">{e.actor === 'solver' ? 'Solver' : modelName(e.model, e.kind)}</span></button>
    </li>)}</ol> : <p className="console-body aq-ink3">Explanations appear as observations are checked.</p>}
  </section>;
}

