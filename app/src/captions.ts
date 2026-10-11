import { arr, record, str, finite, snapshot, type RunEvent, type Actor } from './model';
import { coordinates, distance, modelName, stageName, time } from './format';

export interface Caption { headline: string; caption: string; actor: Actor; source: string; t: number }
export function captionFor(e: RunEvent): Caption {
  const p = e.payload, stage = stageName(e.stage), source = e.actor === 'team' ? 'Team' : e.actor === 'agent' || e.actor === 'solver' ? 'Solver' : modelName(e.model);
  const actor: Actor = e.actor === 'team' ? 'team' : e.actor === 'model' ? 'model' : 'solver';
  const n = (key: string) => finite(p[key]);
  const penalty = snapshot(p.penalty);
  const mult = penalty ? `×${penalty.multiplier.toFixed(2)}` : 'the logged multiplier';
  let headline = stage, caption = `${e.type} was logged.`;
  if (e.actor === 'model' && ['output.produced', 'candidates.updated'].includes(e.type)) return { headline: 'Coordinate source refused', caption: 'Language-model coordinates were ignored; the solver must provide the coordinate.', actor, source, t: e.t };
  switch (e.type) {
    case 'run.started': headline = 'A clean case'; caption = 'The run starts with an empty evidence record for this panorama.'; break;
    case 'run.finished': headline = 'Run finished'; caption = `Finished${n('duration_s') !== null ? ` in ${time(n('duration_s')!)}` : ''}${penalty ? ` at ${mult}` : ''}.`; break;
    case 'run.submitted': headline = 'Answer submitted'; caption = `The solver output ${str(p.output_id, 'on screen')} was submitted with its logged snapshot.`; break;
    case 'stage.started': headline = e.stage === 'views' ? 'Preparing the views' : `${stage} is running`; caption = e.stage === 'views' && n('views') !== null ? `Preparing ${n('views')} views, plus sky and ground.` : `${e.model ? modelName(e.model) : source} is running ${stage.toLowerCase()}${n('deadline_s') !== null ? ` with a ${n('deadline_s')} s deadline` : ''}.`; break;
    case 'stage.finished': headline = `${stage} complete`; caption = `${stage} finished${n('elapsed_s') !== null ? ` in ${n('elapsed_s')!.toFixed(1)} s` : ''}${p.over_deadline ? ', beyond its deadline' : ''}.`; break;
    case 'stage.skipped': headline = `${stage} skipped`; caption = `${stage} was skipped${str(p.reason) ? `: ${str(p.reason)}` : ''}.`; break;
    case 'stage.failed': case 'stage.timed_out': {
      const timed = e.type === 'stage.timed_out'; headline = `${stage} ${timed ? 'timed out' : 'failed'}`;
      caption = `${stage} ${timed ? 'timed out' : 'failed'}${n('elapsed_s') !== null ? ` after ${n('elapsed_s')!.toFixed(1)} s` : ''}${str(p.message) ? `: ${str(p.message)}` : ''}; ${str(p.fallback) ? `${str(p.fallback)} ran instead` : 'the run continues without this stage'}.`; break;
    }
    case 'candidates.updated': {
      headline = 'Weighing the evidence';
      const candidates = arr(p.candidates).map(record); const total = candidates.reduce((sum, c) => sum + Math.max(0, finite(c.weight) ?? 0), 0);
      const best = [...candidates].sort((a, b) => (finite(b.weight) ?? 0) - (finite(a.weight) ?? 0))[0];
      const out = record(arr(p.ruled_out)[0]);
      caption = best ? `${str(best.name, str(best.label, str(best.candidate_id, 'The leading candidate')))} leads${total > 0 ? ` with support ${((finite(best.weight) ?? 0) / total).toFixed(2)}` : ' with support unknown'}${str(out.name) && str(out.reason) ? `; ${str(out.name)} was ruled out because ${str(out.reason)}` : ''}.` : 'No candidate support was logged.'; break;
    }
    case 'question.asked': headline = 'A question for you'; caption = n('gain') !== null ? `Expected gain +${(n('gain')! * 100).toFixed(1)}% against the 5.26% answer cost.` : 'The solver asks a multiple-choice question; an answer costs ×0.95 and a skip is free.'; break;
    case 'question.answered': headline = 'Answer received'; caption = `You chose ${str(p.label, str(p.option_id, 'a logged option'))}; every later guess uses ${mult}.`; break;
    case 'question.skipped': headline = 'Skipped'; caption = 'Skipped: free, and nothing changed.'; break;
    case 'operator.auto_skip': headline = p.reason === 'timeout' ? 'Question timed out' : 'Remaining questions skipped'; caption = p.reason === 'timeout' ? `Nobody answered ${str(p.question_id, 'the question')} in ${n('timeout_s') ?? n('waited_s') ?? '?'} s, so it is skipped: free, and nothing changed.` : `The team skipped ${str(p.question_id, 'the open question')} and every later one: free, and nothing changed.`; break;
    case 'cue.sent': headline = 'Cue sent'; caption = `Every guess from now on uses ${mult}.`; break;
    case 'conversion.applied': headline = 'Conversion logged'; caption = `The logged place conversion costs ${mult} on later guesses.`; break;
    case 'output.produced': {
      headline = 'Best estimate'; const c = record(arr(p.coordinates)[0]);
      caption = finite(c.lat) !== null && finite(c.lng) !== null ? `${coordinates(c.lat as number, c.lng as number)} · ± ${distance(n('position_uncertainty_m'))}.` : 'An output was logged without a readable coordinate.'; break;
    }
    case 'evidence.added': {
      const kind = str(p.kind, 'evidence');
      switch (kind) {
        case 'object': headline = 'Looking for objects'; caption = `${str(p.label, 'An object')} ${p.kept === false ? 'was rejected' : p.kept === true ? 'was kept' : 'is being checked'}${n('score') !== null ? ` at model score ${n('score')!.toFixed(2)}` : ''}.`; break;
        case 'postcode': case 'phone': case 'road_number': case 'text': headline = 'Reading signs'; caption = str(p.text) ? `Read “${str(p.text)}”${n('confidence') !== null ? ` at confidence ${n('confidence')!.toFixed(2)}` : ''}${str(p.country) ? `, parsed as ${str(p.country)}` : ''}.` : 'No text was recorded in this observation.'; break;
        case 'language': {
          headline = 'Reading signs'; const votes = Array.isArray(p.votes) ? arr(p.votes).map(record) : Object.entries(record(p.votes)).map(([id, v]) => ({ id, v }));
          const top = votes.filter(v => finite(v.v) !== null).sort((a, b) => (finite(b.v) ?? 0) - (finite(a.v) ?? 0))[0];
          caption = top ? `Language vote: ${str(top.id)} ${(finite(top.v)! * 100).toFixed(0)}% of the logged votes.` : 'No language votes were logged.'; break;
        }
        case 'checklist': headline = 'Describing the scene'; caption = `${source}: ${str(p.item, 'checklist item')}, ${p.answer === 'not_visible' ? "can't tell" : str(p.answer, 'answer not logged')}${n('answered') !== null && n('total') !== null ? `; ${n('answered')} of ${n('total')} answered` : ''}.`; break;
        case 'landmark_hypothesis': headline = 'Describing the scene'; caption = `The model proposes “${str(p.name, 'an unnamed landmark')}” as a hypothesis.`; break;
        case 'scene_shares': headline = 'Measuring the scene'; caption = 'Logged scene shares describe visible pixels, not land cover.'; break;
        case 'sun': headline = 'Finding north'; caption = n('azimuth') !== null && n('elevation') !== null ? `Sun at ${n('azimuth')}°, ${n('elevation')}° up${n('bearing_of_yaw0') !== null ? `; bearings are now true${n('err_deg') !== null ? `, ± ${n('err_deg')}°` : ''}` : '; north remains unknown'}.` : 'A sun observation was logged; the bearing fix is incomplete.'; break;
        case 'neighbour': case 'landmark_photo': headline = 'Comparing reference photos'; caption = `A ${kind === 'neighbour' ? 'photo-bank neighbour' : 'landmark photo'}${str(p.place) ? ` around ${str(p.place)}` : ''} was logged${n('similarity') !== null ? ` with similarity ${n('similarity')!.toFixed(2)}` : ''}.`; break;
        case 'region': headline = 'Estimating regions'; caption = 'The model supplied region estimates from the panorama pixels.'; break;
        case 'geo_sample': headline = 'Sampling the search area'; caption = Array.isArray(p.points) ? `${arr(p.points).length} logged sampled points are on the map.` : 'A sampled-point observation was logged without point positions.'; break;
        case 'name_match': headline = 'Looking up names'; caption = `“${str(p.query, 'Query not logged')}”${Array.isArray(p.matches) ? `: ${arr(p.matches).length} places match in the local index` : ': match count not logged'}.`; break;
        case 'match': headline = 'Matching a reference photo'; caption = `${n('inliers') !== null ? `${n('inliers')} points agree` : 'A match was logged'}${n('distance_m') !== null ? ` with a reference photo ${distance(n('distance_m'))} away` : ''}${p.accepted === true ? '; accepted by the geometric check' : p.accepted === false ? `; rejected${str(p.reason) ? ` because ${str(p.reason)}` : ''}` : '; verdict not logged'}.`; break;
        case 'contradiction': headline = 'Evidence in conflict'; caption = `${str(p.note, 'The solver logged conflicting evidence')}.`; break;
        default: headline = 'Evidence received'; caption = `An observation of kind “${kind}” was logged.`;
      }
      break;
    }
  }
  return { headline, caption, actor, source, t: e.t };
}
