# Motion

Defined now, built later. Every animation corresponds to a real event in the log; replay plays the log again. Design each state so it can animate into the next.

## Tokens

| Token | Value | Use |
|---|---|---|
| `dur-instant` | 90 ms | hover and press |
| `dur-quick` | 180 ms | small state changes, status icon swaps, reduced-motion cross-fades |
| `dur-standard` | 280 ms | cards and panels entering or leaving |
| `dur-deliberate` | 520 ms | estimate bars, uncertainty rings, multiplier tick |
| `dur-cinematic` | 1400 ms | map flights at one zoom step; scale 1000–2000 ms by zoom levels crossed |
| `dur-stagger` | 40 ms | between list items (30–60 ms) |
| `dur-stagger-cap` | 480 ms | the total stagger never exceeds this |
| `ease-enter` | cubic-bezier(0.16, 1, 0.3, 1) | entrances |
| `ease-exit` | cubic-bezier(0.7, 0, 0.84, 0) | exits, ghosting |
| `ease-move` | cubic-bezier(0.65, 0, 0.35, 1) | in-place change: bars, rings, flights, ruler turning |
| `ease-spring` | linear(…) gentle overshoot | the final surveyor's mark only |

Replay runs at 1×, 2× or 5×: the waits between events compress, the durations above do not. The replay badge is always visible and timestamps stay real.

**Reduced motion:** every beat becomes a `dur-quick` cross-fade; counts jump to their final value; map flights cut. Motion never carries information on its own — every moving thing also changes a number, a word or a mark.

## Storyboard (one beat per event type)

| # | Beat | Log events | What moves |
|---|---|---|---|
| 1 | Intake | `run.started`, `stage.finished` (intake) | The panorama lands as the strip; the filename splits into date, UTC time and shot |
| 2 | Views | `stage.finished` (views) | Eight sectors, sky and ground light up; the photographer area hatches out |
| 3 | Detect | `evidence.added` (detect) | Boxes appear; boxes SAM 3 rejects go dashed, struck and ghosted — **key frames** |
| 4 | Read | `evidence.added` (read) | Text lifts into cards; postcodes and prefixes snap to their country; the language bar fills |
| 5 | Describe | `evidence.added` (describe) | Checklist items tick in; `not_visible` reads "can't tell" |
| 6 | Measure | `evidence.added` (measure) | Segmentation tint sweeps across; the sun is found; the ruler turns to true north |
| 7 | Pixel geolocation | `evidence.added` (geo) | Heat appears; reference photos fly to their GPS; sampled points settle |
| 8 | Fusion | `candidates.updated` | Evidence sends weight; correlated sources merge; a contradiction pulses; ruled-out ghosts — **key frames** |
| 9 | Narrowing | `candidates.updated` | Map zooms country → region → town, never tighter than the uncertainty |
| 10 | Ask | `question.asked`, `.answered`, `.skipped` | Zones draw; on answer the multiplier ticks; on skip nothing moves — **key frames** |
| 11 | Exact spot | `stage.started` (spot), `evidence.added` | Reference slides in; matches draw; inliers count up; the ring contracts — **key frames** |
| 12 | Pinpoint | `output.produced` | Mark lands; ring settles; slots fill; expected score counts up — **key frames** |

## Key frames with timing

The five Motion pages render each frame with the real components at that moment of Case A (and Case B for the skip). Timing notes are on each frame; in short:

- **Beat 3 · Detect.** F1 27.3 s first boxes: brackets scale 0.92 → 1 + fade, `dur-quick`, `ease-enter`, stagger 40 ms capped at 480 ms. F2 all 20 in view; labels after the box settles. F3 33.5 s SAM 3 verdicts: dashed + strike (`dur-quick`), fade to `opacity-ghost` (`dur-standard`, `ease-exit`). F4 the "17 kept, 3 rejected" card lifts into the feed.
- **Beat 8 · Fusion.** F1 ▲ chips tick in sequence while bars grow (`dur-deliberate`, `ease-move`). F2 PE-Core sources slide under one bracket; cap badge last. F3 the contradiction outlines its two sources twice (2 × `dur-quick`, no loop) and Alfama's range widens. F4 Galicia strikes, then ghosts with its reason; it never leaves the list.
- **Beat 10 · Ask.** F1 zone outlines draw A → D (`dur-standard` each, stagger 40 ms), hatch fades in after, heat dims. F2 the card rises; the gain bar fills once. F3 answered: chosen zone thickens, others dim, ×1.00 → ×0.95 ticks in place (`dur-deliberate`). F4 skipped: the card collapses to a dashed receipt; no tick, no bar motion.
- **Beat 11 · Exact spot.** F1 the reference slides in from the right (`dur-standard`). F2 matches draw in batches as LightGlue reports them; rejected ones dashed, then fade. F3 inliers count up to 412 (`dur-deliberate`) — a count of a known number, not a progress bar. F4 the ring contracts ± 180 m → ± 22 m and stops at the remaining offset.
- **Beat 12 · Pinpoint.** F1 the mark drops 12 px with `ease-spring` — the only spring. F2 the ring settles; "± 22 m" fades in. F3 the ten weight bars fill left to right, 40 ms apart. F4 the expected score counts 0 → ≈ 12,500 over `dur-cinematic`, labelled "estimate" throughout.
