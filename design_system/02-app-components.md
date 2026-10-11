# App components

Components the app composes from the system. Their code lives in `app/src/` (file in brackets), not in the bundle, and they use only the system's tokens, type styles and icons. How the app arranges them into screens is the app's business (`app/README.md`).

## Shared

- **Panel** (`ui.tsx`): a titled section on `aq-panel`. Options: `title` (`console-title`), `aside` (an action or count at the right of the header).
- **Disclosure** (`ui.tsx`): native `details` / `summary`, token-styled, so keyboard and screen-reader semantics come free and the content stays in the page. Options: inline (default) or `float` (opens as a popover under its summary and closes on an outside click); controlled with `open` / `onOpenChange`. Use it to fold secondary content, never anything that costs points or a question still open.
- **Modal** (`ui.tsx`): the app's dialog frame: Submit, Send a cue, Skip the remaining questions, Replay a sealed run, Keyboard shortcuts, Open on another device. It follows `Dialog`'s rules: a question as the title, the consequence restated, `actions` at the foot. Focus moves in, is trapped, and returns on close; Esc closes.
- **QueueCard** (`ui.tsx`): `CaseCard` with its metadata line hidden once the case leaves `waiting`, so only status crosses between cases.
- **UploadDropZone** (`ui.tsx`): `DropZone` with its button opening the file picker.
- **ExternalLinks** (`human.tsx`): outbound map links for one place (OSM, Google Maps, Street View). They only open outside the app; nothing comes back.

## Case bar

**FocusBar** (`focus.tsx`): one row across the top: `Wordmark` (24 px), case pills, "+ Add", then at the right the current multiplier, the session clock, the Agent disclosure and the ⋯ menu.

- **Case pill:** the case number, ★ for the Special One, and a state glyph: · waiting, ● working, ? needs an answer (one short scale pulse on arrival, none under reduced motion), ✓ done or submitted, ! invalid. The open case takes `aria-current="page"`; the accessible name spells the state out.
- **Multiplier:** `console-data`, ×1.00 in ink, `cost` below ×1.00.
- **Session clock:** `mm:ss / 60:00` in `console-data-sm`.
- **Agent:** a floating `Disclosure` with a status dot (`is-online`) that holds connection, models, GPU and tile status.
- **⋯ menu:** a floating `Disclosure` of `quiet` buttons; choosing one closes it.

## Working

- **Run stepper** (`FocusWorking`): an ordered list of five steps, Read · Describe · Retrieve · Fuse · Ask. Each step is · pending, ● running (`aria-current="step"`) or ✓ done; it groups whatever pipeline stages the log reports, so it works for any stage list.
- **Thinking** (`activity.tsx`): an orbit of three thin rings (`model`, `solver`) around a breathing dot, then "Thinking…" in `console-heading`. Options: `label`, `compact`. It runs only while a stage is really running and sits beside that stage's real elapsed seconds; it never shows a percentage. It is the one ambient loop in the system, and reduced motion plays it once at `dur-quick`.
- **Scan overlay** (`FocusPhoto busy`): a `model` sweep band and two corner brackets over the panorama while perception runs, with the same reduced-motion rule.
- **DetectionFeed** (`activity.tsx`): "Found in the panorama" with the object and reading counts, then the last six findings as buttons. Each one has a mark (Aa for text, ⌖ for an object), the observation in `console-body` and the yaw in mono when it has pixels. `aria-pressed` follows the linked selection.
- **FocusPhoto** (`focus.tsx`): the panorama frame with a `Segmented` Strip / 360° switch; it shows `PanoramaStrip` or `Viewer360`, and the `ZoomCrop` of the selected finding below.
- **FocusCandidates** (`focus.tsx`): "Leading candidates", at most three rows. Each row has its rank in `solver` mono, a plain name, a thin support bar and the radius ("± 120 m"). A footnote appears when a row is an area centre or a landmark point: "Points are area centres, not where the camera stood."

## Question

- **FocusQuestion** (`focus.tsx`): a header (question number, the gain in words, Details), the question as `console-title` in a polite live region, the options as a radio group, then a footer with `Button variant="skip"` and the cost sentence ("An answer costs ×0.95. Skip changes nothing."). Options: `readOnly` (replay note), `onSkipAll` (a `quiet` "Skip all remaining questions").
- **FocusOption** (`focus.tsx`): `QuestionOption` in its `brief` form. It keeps the letter colour, hatch and radio frame, and adds a plain label with the area's size, the `KeyCap` 1–4 and icon buttons that copy each map link (camera for Street View, map for OSM, link otherwise). The agent's full wording appears verbatim as a tooltip on hover or focus. Hover or focus also highlights the matching zone on the map.

## Answer

- **FocusAnswer** (`focus.tsx`): "Best estimate" in `narrative-title` (★ for the Special One), then `CoordinateBlock size="lg"` without its metadata line, then three sentences: the uncertainty in words, the score estimate (≈, both values when the Urban label is unknown, ×3 noted for the Special One) and the multiplier with what spent it. The actions are `primary` "Copy lat, lng", `quiet` "Submit answer" (⇧⏎) and Details. When the chosen point is not the leading candidate, one line says so.
- **Location tabs:** `Tabs` with Map · Street View · Compare. G switches between Street View and Compare once there is an answer.
- **Base-map switch** (`map.tsx`): a `Segmented` "Base map" with Streets · Satellite · Outlines over `MapView`. A failed tile leaves a gap and the data layers stay drawn; Outlines needs no network.
- **StreetWorkspace** (`streetview.tsx`): the original photo beside the nearest street panorama, both in `Viewer360`. Controls: a "Linked views" `Toggle` (turning and zoom together), "Align the views" then "Lock alignment", "Hold to flicker · F", previous and next nearby picture, and outbound links (Google Street View, map, source). A banner says "For your eyes only: nothing here is sent to the agent." States: loading (`Thinking`), nothing within 1 km (`EmptyState`, noting Google may still have coverage), unavailable or timed out (with Try again).
- **Compare** (`compare.tsx`): one candidate against its reference photos, built from `CandidateRow`, `Viewer360` / `ZoomCrop`, `MatchView`, `Stamp`, `EvidenceMatrix`, `PolarityChip` and `ScoreCurve`. J / K and the reference arrows step through references; the matrix and score curve fold into disclosures.
- **Lookalikes** (`compare.tsx`): two candidates that share at least 60% of their evidence, showing what they share and what separates them.

## Details sheet

**FocusDetails** (`focus.tsx`): a modal side sheet over a backdrop. "Details" in `narrative-title`, a Close button, then `Tabs`: Evidence, Candidates, Questions, Stages, Matrix, Log, Run, plus Compare when a reference exists. Focus moves to the first button, is trapped, and returns on close; Esc or I closes. Its content is the full system components (`EvidenceCard`, `CandidateList`, `EvidenceMatrix`, `EventLog`, `StageTimeline`…), never a summary of them.

## Replay

**FocusReplay** (`focus.tsx`): previous and next event (icon buttons), Play / Pause, and a `Segmented` speed of 1×, 2× or 5×. `SystemBadge kind="replay"` stays visible while a replay runs.

## Intake

**FocusIntake** (`focus.tsx`): `narrative-title` "Start the cases", the drop zone, one row per file, and a footer with `primary` Start and the agent's status.

- **File row:** a validity mark (✓ in `support`, ! in `cost` with the reason), the filename in mono, pixel size and MB, a "★ Special One" radio (one per batch, locked once a case starts), and Remove or Open case.
- **Advanced** (`Disclosure`): `FilenameParse`, the Urban label as a `Segmented` (Unknown · Urban · Non-urban; Unknown by default), its source as a `Segmented` (Inferred · Official), and a local preview strip.

## Worker

**WorkerBanner** (`worker.tsx`): what the one live worker is doing, in a polite live region. A `Badge` (neutral when solving, `contra` with the clock icon while it waits on a question), the run it holds, how long the question has waited and the auto-skip countdown in mono, a `quiet` "Skip remaining questions" with the note "Free and neutral: the run finishes with its current output", and the queued uploads in order. Hidden when the worker is idle with nothing queued.
