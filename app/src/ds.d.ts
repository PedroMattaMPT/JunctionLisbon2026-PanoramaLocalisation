// The published snapshot's index.d.ts includes pasted implementation and cannot be
// consumed by tsc. These declarations isolate that read-only JS component boundary;
// the application's event and state code is checked with TypeScript strict mode.
type DS = (props: any) => import('react').ReactElement;
declare module '@ds/base' {
  export const Density: DS, CostTag: DS, Button: DS, KeyCap: DS, Badge: DS, Stamp: DS,
    Tabs: DS, Toggle: DS, Segmented: DS, Tooltip: DS, Toast: DS, Dialog: DS, EmptyState: DS, WaitState: DS;
}
declare module '@ds/shell' {
  export const Wordmark: DS, Timer: DS, MultiplierChip: DS, ScoreReadout: DS, GpuMeter: DS,
    SystemBadge: DS, ModelChip: DS, ModelRoster: DS, CaseCard: DS, ShortcutBar: DS, CleanStateCheck: DS, RunBar: DS;
}
declare module '@ds/panorama' {
  export const PanoramaStrip: DS, BearingRuler: DS, Viewer360: DS, ZoomCrop: DS, LayerToggles: DS, PerspScene: DS;
}
declare module '@ds/extra' { export const FilenameParse: DS, DropZone: DS, MatchView: DS, LeaderLines: DS; }
declare module '@ds/reasoning' { export const StageRow: DS, StageTimeline: DS, EvidenceCard: DS, PolarityChip: DS, CorrelationBracket: DS, CaptionBar: DS; }
declare module '@ds/beliefs' { export const CandidateRow: DS, CandidateList: DS, RuledOutRow: DS, Funnel: DS, EvidenceMatrix: DS; }
declare module '@ds/human' {
  export const QuestionCard: DS, QuestionOption: DS, AnswerReceipt: DS, CueComposer: DS;
  export function checkCue(text: string): { term: string; why: string }[];
}
declare module '@ds/output' { export const CoordinateBlock: DS, AnswerSlots: DS, ChoiceNote: DS, ScoreCurve: DS, EventLog: DS, ReplayScrubber: DS, ExportBar: DS; }
declare module '@ds/map' {
  export const MapView: DS, UncertaintyRing: DS, SurveyMark: DS, MapLegend: DS;
  export function projector(view: { lat: number; lng: number; span: number }, w: number, h: number): { p: (lat: number, lng: number) => [number, number]; mpp: number; k: number; cos: number };
}
declare module '@ds/charts' { export const LanguageVote: DS, SceneShares: DS, CompassDial: DS, EstimateBars: DS, GainMeter: DS, ConfidenceMeter: DS; }
declare module '@ds/icons' { export const Icon: DS; }
declare module '@ds/geo-data' { export const REGIONS: { id: string; name: string; r: string[] }[]; }
declare module '@ds/rt' {
  export const MAX_SCORE: number, RANK_W: number[];
  export function theta(d: number, urban: boolean): number;
  export function useDensity(): 'console' | 'stage';
  export function useT(): Record<string, string>;
}
declare module 'pannellum' {}
declare module '*.mjs' { export function checkTokens(css?: string): Promise<number>; export function generateTokens(): string; }
