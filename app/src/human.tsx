import React, { useEffect, useState } from 'react';
import QRCode from 'qrcode';
import { QuestionCard, QuestionOption, CueComposer, checkCue } from '@ds/human';
import { Button, EmptyState } from '@ds/base';
import { GainMeter } from '@ds/charts';
import { ModelChip } from '@ds/shell';
import type { Evidence, Option, Question } from './model';
import { mapTree, Modal, type ElementProps } from './ui';
import { modelName } from './format';

export function optionLinks(o: Pick<Option, 'point' | 'links'>) {
  const supplied = Object.entries(o.links ?? {}).filter(([, value]) => { try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol); } catch { return false; } });
  if (supplied.length) return Object.fromEntries(supplied);
  if (!o.point) return {};
  const [lat, lng] = o.point, point = `${lat.toFixed(5)},${lng.toFixed(5)}`;
  return { OSM: `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lng}#map=18/${lat}/${lng}`, 'Google Maps': `https://www.google.com/maps/search/?api=1&query=${point}`, 'Street View': `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${point}` };
}
export async function copyText(text: string) {
  if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(text); return; }
  const area = document.createElement('textarea'); area.value = text; area.className = 'app-copy-buffer'; document.body.append(area); area.select(); const copied = document.execCommand('copy'); area.remove(); if (!copied) throw new Error('Clipboard unavailable; export the coordinates instead.');
}
export function ExternalLinks({ links, onError }: { links: Record<string, string>; onError(message: string): void }) {
  const [qr, setQr] = useState<string>(), [url, setUrl] = useState('');
  useEffect(() => { if (url) { const css = getComputedStyle(document.documentElement); void QRCode.toDataURL(url, { margin: 2, color: { dark: css.getPropertyValue('--ink-1').trim(), light: css.getPropertyValue('--surface-1').trim() } }).then(setQr).catch(() => onError('The QR could not be prepared; copy the link instead.')); } }, [url]);
  if (!Object.keys(links).length) return null;
  return <div className="app-links"><span className="console-micro aq-ink3">Copy links for teammates’ own devices</span><div className="aq-row">{Object.entries(links).map(([name, value]) => <Button key={name} icon="copy" variant="quiet" onClick={() => void copyText(value).catch(error => onError(String(error.message)))}>{name}</Button>)}<Button icon="qr" variant="quiet" onClick={() => setUrl(Object.values(links)[0])}>QR for a phone</Button></div>
    {url && <Modal title="Open on another device" onClose={() => setUrl('')} actions={<Button onClick={() => setUrl('')}>Close</Button>}>{qr && <img src={qr} className="app-qr" alt="QR for the displayed map link" />}<p className="console-data app-break">{url}</p></Modal>}
  </div>;
}
function InteractiveOption({ onAnswer, disabled, ...props }: ElementProps & { onAnswer(id: string): void; disabled: boolean }) {
  const o = props.o as Option;
  const tree = QuestionOption({ ...props, showLinks: false });
  return React.cloneElement(tree, { 'aria-disabled': disabled, 'data-option-id': o.id, onClick: () => { if (!disabled) onAnswer(o.id); }, onKeyDown: (e: React.KeyboardEvent) => { if (!disabled && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); onAnswer(o.id); } } });
}
export function QuestionView({ q, evidence, disabled, onAnswer, onSkip, onError, brief = false, readOnly = false, inspection = false }: { q: Question; evidence: Evidence[]; disabled: boolean; onAnswer(id: string): void; onSkip(): void; onError(message: string): void; brief?: boolean; readOnly?: boolean; inspection?: boolean }) {
  const links = Object.fromEntries(q.options.flatMap(o => Object.entries(optionLinks(o)).map(([label, url]) => [`${o.key} · ${label}`, url])));
  const card = QuestionCard({ q: { ...q, wordedBy: q.wordedBy ? modelName(q.wordedBy) : undefined }, evidence, state: q.status, brief, cueLine: true, number: Number(/^q(\d+)$/.exec(q.id)?.[1]) || 1 });
  return <>{mapTree(card, node => {
    if (node.type === QuestionOption) return <InteractiveOption {...node.props} disabled={disabled || q.status !== 'open'} onAnswer={onAnswer} />;
    if (node.type === GainMeter && q.gain === null) return <div className="console-body aq-ink3 app-pad">Expected gain not logged · any answer costs ×0.95; Skip is free.</div>;
    if (node.type === ModelChip && node.props.name.startsWith('worded by') && !q.wordedBy) return <ModelChip actor="solver" name="wording source not logged" size="sm" />;
    if (node.type === Button) {
      if (node.props.variant === 'skip') return React.cloneElement(node, { disabled, onClick: onSkip });
      if (node.props.icon === 'copy') return React.cloneElement(node, { disabled: !Object.keys(links).length, onClick: () => void copyText(Object.entries(links).map(([name, url]) => `${name}: ${url}`).join('\n')).catch(e => onError(e.message)) });
      if (node.props.icon === 'qr') return null; // QR buttons below contain real links, never showcase placeholders.
    }
    return node;
  })}{!brief && Object.keys(links).length > 0 && <ExternalLinks links={links} onError={onError} />}{disabled && q.status === 'open' && <p className="console-micro aq-ink3 app-pad">{inspection ? 'Close Details to answer or skip the open question.' : brief ? 'The operator console records the answer or a free skip.' : readOnly ? 'Replay is read-only; the recorded response will appear at its real timestamp.' : 'Waiting for the backend receipt; the multiplier has not changed.'}</p>}</>;
}
export function CueView({ onSend, pending }: { onSend(text: string): Promise<boolean>; pending: boolean }) {
  const [text, setText] = useState(''), [confirm, setConfirm] = useState(false);
  const tree = CueComposer({ text, confirm, max: 1000 });
  return <>{mapTree(tree, node => {
    if (node.type === 'textarea') return React.cloneElement(node, { disabled: pending, onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => { node.props.onChange(e); setText(e.target.value); setConfirm(false); } });
    if (node.type === Button) {
      const label = node.props.children;
      return React.cloneElement(node, { disabled: node.props.disabled || pending, onClick: label === 'Keep editing' ? () => setConfirm(false) : label === 'Send cue' ? () => { if (!checkCue(text).length && text.trim() && text.length <= 1000) void onSend(text); } : () => setConfirm(true) });
    }
    if (node.props.className?.includes('aq-cue-ok')) return React.cloneElement(node, {}, 'Browser checks passed; backend validation decides.');
    return node;
  })}{pending && <EmptyState icon="cue" title="Waiting for the agent receipt" body="The multiplier changes only when cue.sent arrives in the log." />}</>;
}
