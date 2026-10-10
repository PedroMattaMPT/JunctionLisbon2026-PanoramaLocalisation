import * as base from './base';
import * as shell from './shell';
import * as pano from './panorama';
import * as reasoning from './reasoning';
import * as beliefs from './beliefs';
import * as charts from './charts';
import * as map from './map';
import * as human from './human';
import * as output from './output';
import * as extra from './extra';
import { Icon, ICONS } from './icons';
import * as Docs from './docs';
import * as Samples from './samples';
import * as Screens from './screens';
import * as rt from './rt';
const NS: any = { ...base, ...shell, ...pano, ...reasoning, ...beliefs, ...charts, ...map, ...human, ...output, ...extra, Docs, Samples, Screens, Icon, ICONS,
  fmt: { coord: rt.fmtCoord, dist: rt.fmtDist, time: rt.fmtTime, est: rt.fmtEst, mult: rt.fmtMult, int: rt.fmtInt }, theta: rt.theta, RANK_W: rt.RANK_W, MAX_SCORE: rt.MAX_SCORE };
const w: any = window; w.Aqui = Object.assign(w.Aqui || {}, NS);
