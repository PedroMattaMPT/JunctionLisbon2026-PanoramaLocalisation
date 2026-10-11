# Aqui frontend build report

2026-10-10 · T50 remains **doing**.

UI update, 2026-10-11: the default run now shows one photo view, one current observation and three leading candidates. Full evidence, sources, ruled-out reasons, diagnostics, receipts, comparison details, replay controls and output history remain available through tabs and expandable sections. Questions and costs stay prominent; event reduction and backend penalty snapshots are unchanged. Strict build, 38 frontend tests and 12 browser checks passed, including mock upload → paid answer → free skip → final output → confirmed submission/export, complete replay export, keyboard disclosure, responsive layouts and stage synchronization. No browser errors or external runtime requests occurred in that check.

Updated screenshots: [focused console](screenshots/console-simplified.png), [comparison](screenshots/compare-simplified.png), [final answer](screenshots/answer-simplified.png). All use invented fixture content.

The inference-independent frontend is implemented in `app/`. It uses the published Aqui components, generated tokens, bundled fonts and local assets. The real inference package is not required to develop or demonstrate the interface.

## Works end to end

- Intake decodes JPEGs, accepts 2:1 panoramas, warns on other 2:1 sizes, refuses other ratios and false JPEGs, parses filename date/UTC/shot, and previews the original image locally. Urban/source and Special One flags are passed to the backend. Upload bytes are unchanged.
- The latest organiser clarification is reflected in intake: Unknown is the default before submission, a manual category defaults to inferred, and both score scenarios are retained when the label is unknown.
- The event reducer powers live and replay views: stages, captions, linked pixel/card/map selection, support shares, uncertainty, correlated evidence, ruled-out places, question receipts, output history and JSON export. Missing data stays absent or unknown.
- The console, Compare, questions, final answer, sealed queue, light printable report, stage window and system states are composed from the existing design system. Compare draws logged keypoint pairs and distinguishes accepted, rejected, similar and landmark references.
- The standard-library mock streams real `Run` events over SSE, pauses for questions, enforces the existing penalty ledger and processes one queued case at a time. The browser flow passed: upload → free skip → confirmed cue → answer → final output → JSON export → confirmed mock submission. Its first output retained ×1.00 and its later output retained ×0.76. The next queued case had an independent question and log.
- Production replay works with the backend stopped. The real sample displays the missing-panorama state and its final ×0.76 snapshot. A valid 6080×3040 upload still previews without a backend; Start says “No agent connected” and offers backend/replay routes.
- Stage mode follows the paired console through a per-console BroadcastChannel. Stage theme/density and the same 05:40 final output were checked at 1920×1080. The case report's print media hides navigation, removes log clipping and uses one column.
- All twelve motion beats have event mappings. Reduced-motion playback was checked in the browser: eleven views-related animations used 180 ms fades with no transforms and no infinite loops. Indexed PNG class masks were decoded and coloured from `seg-*` tokens; an unmapped class stayed transparent.

## Checks

| Check | Result |
| --- | --- |
| `npm install` | Completed with exact versions and lockfile |
| `npm run build` | Passed strict TypeScript and Vite production build |
| `npm test` | 35 tests: reducer/caption/replay invariants, sparse payloads, local assets, disconnected backend, mask indices/filters and tokens |
| `python3 -m unittest discover -s app/dev -p 'test_*.py'` | 5 tests passed: real ledger, neutral skip, duplicate/invalid answers, output snapshots, stale submission, SSE resume, original upload hash, one-worker queue priority and local write boundary |
| Token generation | All 139 variable references from the DS stylesheet and Tailwind preset resolve |
| Browser layouts | 1440×900 console/Compare/final, 1920×1080 stage; no horizontal overflow in those checks |
| Browser runtime | No JavaScript errors in the connected rich-fixture comparison/stage flow; disconnected API requests correctly fail while replay remains usable |

The production bundle currently emits Vite's size advisory: approximately 1.33 MB of JavaScript before gzip, about 412 KB compressed. It includes the map and panorama engines. Splitting those engines is a later loading optimization; it does not require inference integration.

## Waiting for integration

The real pipeline needs the proposed HTTP/SSE adapter and the richer event payloads described in [CONTRACT.md](../CONTRACT.md). Object verdicts, scene masks/sun, neighbours, region samples, name matches and geometric matches are currently exercised with invented fixtures. The mock does not infer a location from the uploaded JPEG.

Venue PMTiles/raster extracts and their source-layer schema have not been tested because no extract was available. The bundled outline fallback is verified. Production cue validation still needs a complete local gazetteer and semantic hint check; the development mock's limited check is not sufficient for challenge use. Submission currently records a mock acknowledgement; organiser submission transport remains to be supplied.

Real mask/reference latency, dense event batches, match query projection and projector behaviour need an integration pass with the inference package and venue hardware. Polygon holes/MultiPolygon questions are not supported yet. Those limits and the app's component adapters are recorded in [DESIGN_GAPS.md](../DESIGN_GAPS.md). T50 is not marked done because those checks remain open.

## Screenshots

All reference content below is invented; no challenge answer key was used.

Console at 01:26: the selected postcode connects its pixels, verbatim reading and candidate map.

![Aqui console mid-run](screenshots/console-mid-run.png)

Compare: an accepted reference with 412 logged inliers, 40 displayed keypoint pairs, its threshold and confirmed-match stamp; the latest rejected match remains in the run caption and log.

![Aqui candidate comparison](screenshots/compare.png)

Final output: latitude/longitude with a true minus, 22 m radius, source/method and ×0.95 snapshot, with the ten repeated slots and score estimate.

![Aqui final pin](screenshots/final-pin.png)

The paired projector window uses the stage theme and the same final output.

![Aqui stage mode](screenshots/stage.png)

Start instructions are in [README.md](../README.md). No inference dependencies, changes to `design_system/`, or changes to `panoloc/` were needed for this frontend work.
