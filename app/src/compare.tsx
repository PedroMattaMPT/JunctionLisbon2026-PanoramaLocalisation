import React, { useEffect, useMemo, useState } from 'react';
import { MatchView } from '@ds/extra';
import { Button, EmptyState, Stamp } from '@ds/base';
import { CandidateRow } from '@ds/beliefs';
import { ScoreCurve } from '@ds/output';
import { PolarityChip } from '@ds/reasoning';
import { arr, finite, point, record, str, strings, type CaseRecord, type Candidate, type Evidence } from './model';
import { localAsset } from './data';
import { distance, coordinates, haversine, roleText, score } from './format';
import { imageCase, Viewer, Crop, perspectiveImage, referenceFor } from './panorama';
import type { PanoramaImage } from './images';
import { Disclosure, mapTree, useWidth, Matrix, Panel } from './ui';
import { ExternalLinks, optionLinks } from './human';

export function candidateReferences(c: CaseRecord, candidate: Candidate) {
  return [...c.neighbours, ...c.matches].filter(e => candidate.evidence.includes(e.id) || e.payload.candidate_id === candidate.id || strings(e.payload.candidate_ids).includes(candidate.id) || referenceFor(e).source === candidate.source || (e.pol[candidate.id] ?? 0) > 0);
}
export function LoggedMatch({ c, image, e }: { c: CaseRecord; image?: PanoramaImage; e: Evidence }) {
  const { ref, width } = useWidth<HTMLDivElement>(550), height = width * 0.32;
  const payload = e.payload, reference = record(payload.reference), yaw = finite(payload.query_yaw), fov = finite(payload.query_fov);
  const query = useMemo(() => image && yaw !== null && fov !== null && fov > 0 && fov < 180 ? perspectiveImage(image, yaw, fov) : undefined, [image, yaw, fov]);
  const [keypoints, setKeypoints] = useState(arr(payload.keypoints));
  useEffect(() => { const url = localAsset(payload.keypoints_url); if (!url) { setKeypoints(arr(payload.keypoints)); return; } const controller = new AbortController(); void fetch(url, { signal: controller.signal }).then(r => r.json()).then(v => setKeypoints(arr(v))).catch(() => setKeypoints([])); return () => controller.abort(); }, [e.id, payload.keypoints_url]);
  const matchingCase = { ...imageCase(c, image), spot: { refs: [{ id: str(reference.id, e.id), inliers: finite(payload.inliers), matches: finite(payload.matches), dist: finite(payload.distance_m), accepted: payload.accepted === true }] } };
  const half = width / 2;
  const tree = MatchView({ c: matchingCase, width, height, lines: 0 });
  return <div ref={ref}>{mapTree(tree, node => {
    if (node.props.className === 'aq-match-h') return React.cloneElement(node, {}, <><span className="console-label">Query view · {yaw !== null ? `yaw ${yaw}°` : 'yaw not logged'}</span><span className="console-label aq-ink3">Reference {str(reference.id, e.id)} · {distance(finite(payload.distance_m))} from the candidate</span></>);
    if (node.type === 'svg' && node.props.role === 'img') return React.cloneElement(node, {}, <>
      {query && <image href={query} width={half} height={height} preserveAspectRatio="xMidYMid meet" />}
      {localAsset(reference.photo_url) && <image href={localAsset(reference.photo_url)} x={half} width={half} height={height} preserveAspectRatio="xMidYMid meet" />}
      {query && localAsset(reference.photo_url) && keypoints.slice(0, 500).map((value, i) => { const kp = record(value), q = arr(kp.query), r = arr(kp.reference); if ([...q, ...r].length !== 4 || [...q, ...r].some(v => finite(v) === null || (v as number) < 0 || (v as number) > 1)) return null; return <line key={i} x1={(q[0] as number) * half} y1={(q[1] as number) * height} x2={half + (r[0] as number) * half} y2={(r[1] as number) * height} className={kp.inlier === false ? 'aq-match-out' : 'aq-match-in'} />; })}
    </>);
    if (node.props.className === 'aq-match-cap') return React.cloneElement(node, {}, <><span className="console-readout aq-c-support" data-inlier-count>{finite(payload.inliers) ?? 'unknown'}</span><span className="console-body">inliers{finite(payload.matches) !== null ? ` of ${payload.matches} matches` : '; match count not logged'}</span><span className="console-micro aq-ink3">{keypoints.length ? `${keypoints.length} logged keypoint pairs drawn` : 'keypoint positions not logged'}</span></>);
    return node;
  })}<div className="app-stack console-body"><p>{payload.accepted === true ? 'Accepted' : payload.accepted === false ? 'Rejected' : 'Verdict not logged'}{finite(payload.threshold) !== null ? ` · threshold ${payload.threshold} inliers` : ' · threshold not logged'} · {str(payload.reason, 'Reason not logged')}.</p>{payload.accepted === true && <Stamp kind="confirmed" />}{!query && <p className="aq-ink3">Query image, yaw or field of view not logged; no keypoint lines are inferred.</p>}</div></div>;
}
export function Compare({ c, candidate, image, yaw, setYaw, refIndex, setRefIndex, onEvidence, onError, onClose }: { c: CaseRecord; candidate: Candidate; image?: PanoramaImage; yaw: number; setYaw(yaw: number): void; refIndex: number; setRefIndex(index: number): void; onEvidence(id: string): void; onError(message: string): void; onClose(): void }) {
  const references = candidateReferences(c, candidate), e = references[(refIndex + references.length) % Math.max(1, references.length)];
  const reference = e ? referenceFor(e) : undefined, queryYaw = e ? finite(e.payload.query_yaw) : null;
  const related = c.evidence.find(e => candidate.evidence.includes(e.id) && e.box);
  useEffect(() => { if (queryYaw !== null) setYaw(queryYaw); else if (related?.box) setYaw(related.box.yaw); }, [candidate.id, e?.id]);
  const estimate = score(candidate.r, c.urban, c.penalty.multiplier);
  const pointOfCandidate = point(candidate), best = c.answer ?? c.candidates[0];
  return <section className="app-compare app-stack" aria-label={`Compare ${candidate.name}`}>
    <header className="aq-panel-h"><h2 className="narrative-title">Compare</h2><Button variant="quiet" icon="close" onClick={onClose}>Close</Button></header>
    <CandidateRow c={{ ...candidate, sup: candidate.sup ?? 'unknown', con: candidate.con ?? 'unknown' }} selected max={1} showDelta={candidate.delta !== null} />
    <p className="console-micro aq-ink3">{candidate.v === null ? 'Support unknown' : `Support ${candidate.v.toFixed(2)} · weight ÷ total weight`}.</p>
    <p className="console-body aq-ink2">{roleText(candidate.role)} · ± {distance(candidate.r)}.</p>
    {e?.kind === 'match' ? <LoggedMatch c={c} image={image} e={e} /> : <div className="app-compare-pair"><Panel title="This panorama">{related?.box ? <Crop c={c} image={image} evidence={related} /> : <Viewer c={c} image={image} yaw={yaw} onYaw={setYaw} />}</Panel><Panel title="Reference photo">{reference && localAsset(reference.photo_url) ? <><img className="app-reference" src={localAsset(reference.photo_url)} alt={`${str(reference.place, 'Reference')} · ${str(reference.source)}`} /><p className="console-body">{e?.kind === 'landmark_photo' ? 'Landmark photo: its coordinate is the landmark’s, not where the camera stood.' : `Photo-bank neighbour: looks similar${finite(reference.similarity) !== null ? ` · similarity ${Number(reference.similarity).toFixed(2)}` : ''}.`}</p>{point(reference) && <p className="console-data aq-ink3">{coordinates(point(reference)!.lat, point(reference)!.lng)} · {e?.kind === 'landmark_photo' ? 'landmark coordinate' : 'camera GPS'}</p>}</> : <EmptyState icon="neighbour" title="No linked reference photo" body="The log has not supplied a reference for this candidate." />}</Panel></div>}
    <div className="aq-row"><Button icon="back" shortcut="←" disabled={references.length < 2} onClick={() => setRefIndex((refIndex - 1 + references.length) % references.length)}>Previous photo</Button><span className="console-data aq-ink3">{references.length ? `${refIndex % references.length + 1} of ${references.length}` : 'No reference'}</span><Button icon="forward" shortcut="→" disabled={references.length < 2} onClick={() => setRefIndex((refIndex + 1) % references.length)}>Next photo</Button></div>
    <Disclosure title="Evidence for this candidate"><Matrix c={c} candidate={candidate.id} onSelect={onEvidence} /></Disclosure>
    <Disclosure title="Distance and estimated score">
      {pointOfCandidate && best?.lat !== undefined && best.lng !== undefined && <p className="console-body aq-ink3">{distance(haversine(pointOfCandidate, { lat: best.lat, lng: best.lng }))} from the current best estimate.</p>}
      <ScoreCurve urban={c.urban} band={candidate.r !== null ? [candidate.r, candidate.r] : undefined} expected={estimate.split ?? estimate.expected ?? undefined} multiplier={c.penalty.multiplier} />
    </Disclosure>
    <Disclosure title="Share map links"><ExternalLinks links={optionLinks({ point: pointOfCandidate ? [pointOfCandidate.lat, pointOfCandidate.lng] : undefined, links: {} })} onError={onError} /></Disclosure>
    <Lookalikes c={c} selected={candidate.id} onEvidence={onEvidence} collapsed />
  </section>;
}
export function Lookalikes({ c, selected, onEvidence, collapsed = false }: { c: CaseRecord; selected?: string; onEvidence(id: string): void; collapsed?: boolean }) {
  const first = c.candidates.find(v => v.id === selected) ?? c.candidates[0]; if (!first) return null;
  const others = c.candidates.filter(v => v.id !== first.id && v.evidence.length && first.evidence.length && v.evidence.filter(id => first.evidence.includes(id)).length / Math.max(v.evidence.length, first.evidence.length) >= 0.6);
  const second = others[0]; if (!second) return null;
  const shared = first.evidence.filter(id => second.evidence.includes(id)), separates = c.evidence.filter(e => (e.pol[first.id] ?? 0) !== (e.pol[second.id] ?? 0));
  const content = <Panel title="Far apart, alike"><div className="aq-lookalike"><div className="console-heading">{first.name}</div><div className="console-micro aq-ink3">Shared evidence</div><div className="console-heading">{second.name}</div><div className="aq-lookalike-b console-body">{shared.map(id => c.evidence.find(e => e.id === id)?.obs).filter(Boolean).join(' · ')}</div></div>{separates.length ? separates.map(e => <div className="aq-row" key={e.id}><Button variant="quiet" onClick={() => onEvidence(e.id)}>{e.obs}</Button><PolarityChip name={first.name} pol={e.pol[first.id] ?? 0} /><PolarityChip name={second.name} pol={e.pol[second.id] ?? 0} /></div>) : <p className="console-body aq-ink3">No logged evidence separates these candidates.</p>}</Panel>;
  return collapsed ? <Disclosure title="Look-alikes" aside={second.name}>{content}</Disclosure> : content;
}
