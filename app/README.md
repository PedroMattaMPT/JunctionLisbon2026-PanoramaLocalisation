# Aqui operator console

The frontend runs independently of the inference package. Upload validation, local previews, invented fixture replays, comparison, reports, stage mode and JSON export work without models. The Python mock exercises the live HTTP/SSE interface using the real `panoloc.runlog.Run`, including question validation and penalty snapshots.

## Start the app

Requires Node 20.19+ and Python 3.10+ for the mock. From the repository root:

```sh
cd app
npm install
npm run dev
```

Open <http://127.0.0.1:5178/>. The `predev`, `prebuild` and `pretest` scripts generate the tokens and invented fixtures. No inference dependencies are installed. The app uses the existing components and fonts in `../design_system/`; that directory must remain present when developing or building.

```sh
npm run build
npm test
```

The build includes local fonts, icons, Pannellum, MapLibre, outlines and the three fixture logs. There are no runtime CDN dependencies. Serve `dist/` over HTTP, rather than opening `index.html` with `file://`. `npm run preview` serves the build on port 5178. A production static server must reverse-proxy `/api` to a local agent if live runs are needed; replay works with the backend disconnected.

## Sunday: one command

`app/start.sh start | status | stop | restart` (from anywhere) builds the console if its sources changed, then runs the live backend detached under a supervisor that restarts it if it dies. The console is at <http://127.0.0.1:5178/> (also <http://127.0.0.1:8788/>), with `/api` on the same origin. `status` shows the PIDs, the URL, whether the models are warm, and the question a run waits on. `stop` and `restart` refuse while a run is active or a `drive_warmup.py` batch is running; `--force` overrides. Extra arguments go to `live_server.py` and are remembered, e.g. `app/start.sh restart --question-timeout 300` skips any question nobody answers in 5 minutes. Logs are in `runs/app/live_server.log` and `runs/app/supervisor.log`. `app/start.sh build` rebuilds the console alone; the running backend serves the new files without a restart. `AQUI_CONSOLE_PORT=0 app/start.sh restart` frees port 5178 for `npm run dev`.

**Skip remaining questions** (under the question, in the map column, and in the worker banner on Queue and Upload) skips the open question and every later one of that run. Skips are free and neutral, so the run finishes with its current output and the queue moves on. Any console can use it, so a question left open in another tab no longer blocks the worker. The map's base layer (Streets, Satellite or Outlines) comes through the server's caching tile proxy, with the cache in `runs/app/tiles/`. A tile that fails leaves a gap and the points and zones stay drawn. The option links (Google Maps, OSM) still work as the fallback.

## Live mode: the real pipeline

From the repository root, with the venv (it needs torch, RapidOCR and the other model packages):

```sh
.venv/bin/python app/dev/live_server.py          # port 8788, loopback only, same token checks as the mock
cd app && npm run dev                             # console on http://127.0.0.1:5178/, /api proxied to 8788
```

It warms one `panoloc.pipeline.Models` at start-up: OCR, Qwen through Ollama (`num_ctx` 8192, never a second Ollama model), PE-Core with the bank, GeoCLIP, the landmark gallery and verifier, zones and names. It prints each load time and the VRAM. Uploads queue behind one GPU worker. Each one is saved under `runs/app/<run_id>/` and solved alone by `run_panorama`, with a fresh Run and its events streamed through `on_event`. A question waits until you answer it or skip it. The category defaults to Unknown and Special One comes from the intake. If the pipeline raises, the run ends with a visible `stage.failed` and the server stays up. `--no-landmarks` skips the Commons gallery and verifier, which saves about 2.5 GiB of GPU. `--no-retrieval` keeps the GPU models out, leaving OCR, VLM, names and fusion only. `--no-warm` loads models on the first panorama. For rehearsals, `--ask-anyway` asks the first question even below break-even, and `--min-gain -1 --max-questions 2` asks every scheduled question. Each answer still costs ×0.95.

Limits: text cues are refused with a clear error, because the pipeline takes no cue mid-run (T78). Submission isn't wired, so copy the coordinates from the answer screen. One job runs at a time. Run lists reset when the server restarts; the folders in `runs/app/` stay replayable. `.venv/bin/python -m unittest discover -s app/dev -p 'test_*.py'` covers the live server with a stand-in pipeline.

## Exercise a live run without inference

In another terminal, from the repository root:

```sh
python3 app/dev/server.py
```

The mock listens only on `127.0.0.1:8788`. Upload a 2:1 JPEG in the app, choose its Urban label and source, optionally mark the Special One, and start. It processes one sealed case at a time and pauses at each question until an answer or free skip arrives. Its evidence and coordinates are invented, and it does not analyse the uploaded image. A failed optional detector and an unavailable reference match demonstrate the soft failure states.

The evening organiser clarification in `RULES.md` says the official Urban label is revealed after submission. Intake therefore defaults to Unknown and shows both score scenarios. A manual Urban/non-urban selection defaults to the inferred source. Use an official label only when it has actually been revealed, or for an explicitly labelled local fixture; do not assume it is available during a challenge run.

The mock writes the unchanged JPEG under its original basename, `events.jsonl` and `log.json` into `runs/mock/<run_id>/`. Its in-memory run list resets on server restart; the folders remain replayable. After the final output, submission acknowledges and logs the reviewed mock output. It does not send an entry to the challenge organisers.

`--pace 0.12` is the default. It shortens scripted compute sleeps while retaining actual timestamps and human wait times. Use `--pace 1` for uncompressed compute waits. The mock uses Python's standard library and the existing runlog module only.

```sh
python3 -m unittest discover -s app/dev -p 'test_*.py'
```

Those tests use temporary run folders and ephemeral loopback ports. `app/dev/upload-test.jpg` is a small, invented 2:1 JPEG for the tests; it contains no challenge data.

For a different backend port, start the mock with `--port`, then set the Vite proxy target before starting the app:

```sh
AQUI_API_TARGET=http://127.0.0.1:8789 npm run dev
```

Keep the console on port 5178 with the mock, whose write-origin allowlist includes that port. Prefer this same-origin proxy to cross-origin requests. `VITE_API_BASE` is available for a local API with its own CORS configuration; the mock intentionally supplies no cross-origin CORS access.

## Replay and compare

The intake offers three prepared logs:

- **Replay Porto:** invented Case A, procedural urban panorama, answered question, accepted and rejected reference matches, final 22 m radius.
- **Replay Alentejo:** invented Case B, procedural rural panorama, no positioned text, a neutral skip and look-alike candidates.
- **Replay sample:** the real log format produced by `tools/sample_log.py`, with no panorama. The strip explicitly says the file is unavailable.

Use **Replay a log** to select `events.jsonl` or `log.json`, optionally with its matching JPEG, or open one run folder. The JPEG basename must match `panorama` in the log; selecting another case's image is refused. The sample generator can be rerun from the repository root with `python3 tools/sample_log.py`. It has no answer key.

The scrubber has 1×, 2× and 5× playback. Event timestamps stay real; speed compresses the wait between events, and motion keeps its token duration. Previous/next event controls and the slider's arrow keys allow precise inspection. Home and End jump to the beginning and end. Scrubbing renders the requested state immediately.

Select a candidate in the list or map to open Compare. Arrow keys cycle its linked reference photos. The label distinguishes similar photo-bank neighbours, landmark photos and accepted/rejected geometric matches. Keypoint lines require logged geometry; missing positions and ranges stay absent. The JSON export includes the complete imported log, even when the replay cursor is earlier.

The run opens on **Now**, showing one observation and the leading candidates. Use the Evidence, Stages, Matrix and Log tabs for the complete record; expand **Candidate details**, **Run details**, **Timeline** or **Layers and bearings** for sources, diagnostics and controls. Switch between Panorama and 360° view, and select evidence to open its pixels. Completed question zones are available in **Map key**. **Tools** contains the case report, system states, stage window and keyboard map; the answer folds its score curve, slots and earlier outputs.

## Stage mode and case report

Use **Stage window** in the console. It opens `?mode=stage&console=<console-id>` and follows only that console's active case over a BroadcastChannel. Move this window to the projector. It uses the stage theme and density, focuses on the current reading, question, match or final output, and keeps the caption along the bottom. A bare `?mode=stage` without its paired console waits at the opening card.

The stage window displays the same evidence; questions and costly actions are handled by the operator console. Closing the operator console stops updates. Switching cases clears the previous case's image before loading the next one.

**Case report** uses the light theme and includes the event log, matrix, question receipts, costs, ruled-out candidates, look-alikes and export. Use **Print case report** for the printable layout.

## Local map tiles

Without tiles, the map uses bundled Portugal, Spain and France outlines with the logged evidence layers. No online imagery or Overpass service is used.

With the live server, `/api/status.tile_layers` supplies the Streets (© OpenStreetMap contributors) and Satellite (Esri World Imagery) layers through `/api/tiles/<layer>/{z}/{x}/{y}`. The proxy sends a User-Agent naming the project, keeps at most 2 upstream fetches per layer, and fetches nothing it already has cached. It doesn't retry a failed tile for a minute, and it pauses a layer for 30 s after repeated failures. When a question opens, it prefetches at most 48 tiles for the layer on screen, around that question's options and at zoom 16 or below. `--no-tiles` turns it off.

Without a live server, set a local raster z/x/y source or a local PMTiles extract before starting Vite:

```sh
VITE_TILE_SOURCE='/tiles/{z}/{x}/{y}.png' VITE_TILE_FORMAT=raster npm run dev
```

```sh
VITE_TILE_SOURCE='/tiles/pt-es-fr.pmtiles' npm run dev
```

Place those files under `app/public/tiles/` or serve their URLs locally. PMTiles vector styling expects OpenMapTiles `water`, `building`, `transportation` and `boundary` layers. Raster PMTiles need an appropriate local tile URL adapter; `VITE_TILE_FORMAT=raster` is for z/x/y raster URLs. `/api/status.tile_source` can also supply a local source. Map errors fall back to the outlines. Actual venue tile extracts still need integration verification.

## Keyboard and accessibility

| Key | Action |
| --- | --- |
| J / K | Next / previous candidate; option focus while a question is open |
| Left / right | Previous / next reference in Compare |
| 1–4 | Answer the live agent's options, each ×0.95 |
| S | Free, neutral skip |
| O | Copy the question's external links |
| C | Open the text cue composer, ×0.8 shown before confirmation |
| L | Show/hide layer controls |
| V | Focus the 360° viewer; arrows then turn it |
| M | Return the map camera to the selection |
| Space | Play/pause replay |
| Shift+Enter | Review the current output before submitting |
| 1–6 on Queue | Open a sealed case |
| Escape | Close the active dialog or Compare |

Inputs retain their native keys. Tabs, radio groups, the replay slider and dialogs support keyboard navigation and a token focus ring. Captions and stage rows announce changes politely. With reduced motion, event beats use quick cross-fades, counts jump to the logged value and map flights cut.

See [CONTRACT.md](CONTRACT.md) for the inference interface, [DESIGN_GAPS.md](DESIGN_GAPS.md) for the app adapters, and [the build report](docs/BUILD_REPORT.md) for verification and screenshots. T50 remains in progress until the real pipeline and remaining integration checks pass.
