# Touchline Studio: source and architecture guide

## Where the code comes from

The application-specific Python, JavaScript, HTML, CSS, launchers, packaging scripts,
and tests were drafted and edited by Codex in this conversation for Touchline Studio.
Regression checks are provided; current pass status is recorded separately because
the working tree can change after a test run. The independent Git
history begins at commit `7b2ddae`; it records this project's baseline, not an upstream
repository's development history. The user's project instructions are in AGENTS.md.

[nabiutara/football_analysis](https://github.com/nabiutara/football_analysis), reviewed
at `e4799632cdf271cf57f4eb0c4d872cf1b7ab0f17`, supplied the reference fundamentals:
football detection, ByteTrack identity association, torso-color grouping, optical-flow
camera motion, perspective transforms, and ball proximity/interpolation. The app is
an independent implementation using maintained Ultralytics components. The reference
clone's files and pickle stubs are not imported or executed by this application.

The default `football-best.pt` is third-party pretrained model data linked by that
reference project. It was downloaded, not written or trained here. Its exact URL,
checksum, and four detection classes are in MODEL-PROVENANCE.json. The YOLO26 fallback
weights are Ultralytics models. Removing Git ancestry does not change model provenance.

Installed libraries are third-party code. requirements.txt pins the direct install
requirements, and DEPENDENCIES.json lists the actual installed distributions and
their declared source URLs. It is a record of this computer's environment, not a
complete security or licensing audit. No proprietary PyCharm or Python-library source
is copied into this application folder.

## Read the project in this order

1. `README.md`: launch, use, performance, and limitations.
2. `server.py`: entry point, local HTTP service, uploads, analysis jobs, cancellation.
3. `football_engine.py`: detection and the football analysis pipeline.
4. `dist/index.html`: the interface's visible controls and script loading order.
5. `dist/app.js`: playback, canvas drawing, editable state, saving, and exports.
6. `dist/player-connections.js`: validation and display filtering for saved player edges.
7. `dist/football-features.js`: camera-adjusted projection, ball markers, team swapping.
8. `tests/`: regression checks for the pipeline, UI, and geometry.

CODE-MAP.md lists the declared functions/classes and source line numbers. The source
itself is the authoritative description of behavior; line numbers change after edits.

## File-by-file explanation

| File | What is written here |
| --- | --- |
| `server.py` | Starts the local HTTP server at port 8765, serves `dist/`, validates host/origin and upload settings, saves a temporary video, runs one analysis job at a time, reports progress/results, and requests cancellation. The standard command is loopback-only; `--lan` allows the detected private IPv4 address for same-Wi-Fi phone access. It also supports command-line analysis. |
| `football_engine.py` | Resolves/checks model weights, loads YOLO with restricted checkpoint loading, reads actual video timing, streams detections, maps class names to football roles, associates people with ByteTrack or BoT-SORT, samples torso colors, estimates camera motion, and writes normalized tracking JSON. |
| `dist/index.html` | Defines the video canvas, toolbar, playback controls, formation board, interpretation area, tracking controls, file inputs, and dialogs. Loads player-connection and football helpers before the main app. |
| `dist/styles.css` | Defines the page palette, typography, panels, buttons, spacing, overlay controls, dialogs, and responsive layouts. DM Sans and Manrope are requested from Google Fonts; local sans-serif fallbacks are available. |
| `dist/app.js` | Owns application state. Draws the simulated demo or imported video; interpolates nearby track positions; draws player rings, labels, boxes, trails, and connections; implements drawings, selection, undo, formation editing, calibration, local persistence, job polling, and PNG/JSON/TXT/WebM exports. |
| `dist/football-features.js` | Validates camera transforms; performs 3×3 matrix operations; moves player coordinates into the calibration's reference view; invalidates a calibration across shots; draws observed/interpolated ball markers; binds team swapping and kit-color buttons. |
| `dist/player-connections.js` | Validates persisted edges and timed endpoint corrections; bridges bounded same-ID gaps for connected players and resolves edges within one camera scene. |
| `tests/test_football_engine.py` | Tests kit-color grouping, green kits, isolated color outliers, insufficient evidence, camera translation/cuts/drift, featureless images, short ball gaps, ball candidate selection, class mapping, empty detections, tracker-row shapes, and cancellation cleanup. Model-free fixtures test edge cases. |
| `tests/test_football_ui.cjs` | Executes the projection/validation functions in a Node sandbox to check camera-adjusted pitch mapping, scene-change invalidation, valid imports, and malformed result rejection. |
| `tests/test_player_connections.cjs` | Checks edge validation, movement-following anchors, missing players, scene boundaries, pair/sequence editing, undo, persistence, and video-frame timestamps. |
| `tests/test_player_labels.cjs` | Checks editable label persistence, grouped undo, blank labels, manual overlap overrides, and project sanitization. |
| `Start Touchline.cmd` | Creates/checks a local Python environment, installs requirements if absent, and runs `launch.py`, which starts or reuses a readiness-checked server. Keep its window open while using the app. |
| `build_package.py` | Creates the portable ZIP using an explicit file list. Excludes Git history, model binaries, environments, credentials, and runtime data. |
| `requirements.txt` | Pins Ultralytics 8.4.192, LAP 0.5.13, and gdown 5.2.2. Their dependencies supply PyTorch, OpenCV, NumPy, and supporting packages. |
| `MODEL-PROVENANCE.json` | Records model origin, checksum, classes, tracker choices, and the policy that physical measurements must be confirmed. |
| `REPOSITORY-ANALYSIS.md` | Explains which reference ideas were adopted, sample-specific assumptions corrected, model selection, and validation limits. |
| `AGENTS.md` | Instructions for future coding agents, including independent Git history, provenance, measurement questions, testing, and local-only operation. |
| `.gitignore` | Prevents environments, runtime data, model binaries, local IDE state, and generated archives from entering Git. |
| `.run/*.run.xml` | PyCharm Run/Debug configurations for starting the app, running Python tests, and building the ZIP. They select the existing Python environment on this computer. |
| `.idea/` | Local PyCharm project settings. IDE-specific machine state stays outside the portable package and Git. |
| `SOURCE-GUIDE.md`, `CODE-MAP.md`, `DEPENDENCIES.json` | This explanatory guide, the source navigation index, and the installed dependency inventory. |

The adjacent `outputs/Open Touchline.cmd` is a convenience launcher for this workspace.
It uses the already-installed environment in the outer `work/yolo-env` folder and
falls back to the packaged launcher. It is not part of the portable app's runtime API.

## Main analysis flow

```text
Import video → app.js → POST /api/jobs → server.py job thread
    → football_engine.track_football
        → verify weights → YOLO detections → role mapping → tracker IDs
        → torso-color samples + camera transform + ball candidates
        → temporary frame records → team-color fit → final tracking JSON
    → GET status/result → app.js validates and caches results
    → canvas overlays / football-features projection / editable user corrections
```

The server exposes `GET /api/health`, `POST /api/jobs`, `GET /api/jobs/{id}`,
`GET /api/jobs/{id}/result`, and `DELETE /api/jobs/{id}`. Mutations require the
workspace header, requests are checked against the local host/origin, and only one
analysis job runs at a time. This is a local application, not a public multiuser server.

## What each core engine component does

`dist/foot-markers.js` is a presentation-only renderer for segmented elliptical foot
markers, bounded positional smoothing, glow, and the fixed leg gap. It does not
change detection or tracking results. `tests/test_foot_markers.cjs` checks the
three-arc geometry, nested-body duplicate suppression, repeated-frame position
holds, and resets across pauses, seeks, and camera scenes.

- `resolve_model`: accepts known model names, downloads the default model when missing,
  and rejects a mismatched checksum. It does not read the reference clone.
- `role_for`: translates model class names into player, goalkeeper, referee, or ball.
- `distinct_people`: suppresses near-identical person boxes across roles before tracking; preserves role/index alignment and leaves ball candidates separate.
- BoT-SORT is the default association tracker with built-in camera compensation. Confidence-score fusion is disabled; ByteTrack remains available. See STABILITY.md for evidence and limits.
- `jersey_color`: samples upper-torso pixels in Lab color space while suppressing local
  background. Green shirts are preserved rather than removed by a broad hue rule.
- `TeamColors`: collects repeated samples per identity, rejects isolated outliers,
  clusters two color groups, and abstains when evidence is insufficient. When the
  local collection has reviewed shirt samples from three distinct outfield IDs per
  team for this exact source hash, it uses that palette to guide home/away assignment.
- `CameraMotion`: estimates background movement using optical flow, backward checks,
  and RANSAC; accumulates transforms within a shot; resets after unreliable motion.
- `BallHistory`: selects plausible observed candidates near recent ball observations.
- `bounded_ball_fill`: interpolates only short, bracketed gaps within one scene.
- `track_football`: orchestrates these steps, separates referee/goalkeeper roles,
  namespaces identities across resets, and finalizes results without retaining the
  entire decoded video in RAM. Its proximity candidate is not measured possession.

## Coordinates, state, and limits

The evaluation workflow lives in `benchmark.py`, `evaluation.py`, and
`prepare_training.py`. The first records reproducible comparisons and review packets;
the second computes explicitly scoped sampled-frame metrics from reviewed labels;
the third exports verified annotations into YOLO images/labels directories while
checking match-level split boundaries. Read EVALUATION.md before using these tools.
Their regression tests are `tests/test_evaluation.py` and `tests/test_training_export.py`.

Player `x,y` values mark the bottom center of detection boxes in normalized image
coordinates. Ball positions mark their box centers. These are not pose-estimated
anatomical foot locations. Camera transforms and formation coordinates are dimensionless.
No verified pitch dimensions, meters, or km/h are assumed or calculated. Ask the user
for physical reference measurements before implementing metric speed/distance.

Browser edits use localStorage; tracking uses IndexedDB. Exported project JSON includes
edits and tracks but not the video. Server `work/jobs` contains transient uploads and
result JSON; uploads are removed after a job ends. `work/models` holds model weights.
Neither directory is application source. The model and detector settings currently
do not establish a labeled accuracy score or guarantee perfect identities through occlusion.

## Using PyCharm

Open this folder as the project. Choose **Touchline Studio** in the Run selector and
click Run to start the local server and open its browser workspace. Stop an existing
instance first if port 8765 is already occupied. Choose **Touchline Python tests** for
the regression suite or **Build Touchline package** to refresh the ZIP. All Python,
HTML, CSS, JavaScript, test, and documentation files remain editable in one project.
Third-party library implementations can be inspected under PyCharm's External Libraries.

See PYCHARM-SETUP.md for the one-time interpreter selection. IDE launch and interpreter
registration still need confirmation in PyCharm; preparing XML does not verify them.
The adjacent **Open Touchline in PyCharm.cmd** launcher opens the installed IDE with
this project folder. Workspace-specific `.run/` and `.idea/` files are not in the ZIP.

`launch.py` checks local server identity, detects port conflicts, starts the server with a persistent log, and opens the browser only after readiness. The Windows **Start Touchline.cmd** launcher enables same-Wi-Fi access and prints the phone link; **Open Touchline.cmd** stays loopback-only. `tests/test_launch.py` verifies reuse, conflict handling, and failed-child behavior.


## Overlay, labels, and connections

OVERLAY-FIX.md documents the November 1 ring and label update. CV-RESOURCES.md
records the primary sources reviewed and separates shipped behavior from future
research. The MATCH1 fixture contains six visually reviewed pairs, not ground-truth
training annotations. `tests/test_player_labels.cjs` covers live editing and project
round-trips.

`dist/player-connections.js` validates saved player edges and resolves current
anchors without reordering them. Same-ID gaps up to 0.6 seconds are interpolated
only with observations on both sides and bounded displacement/size changes. Timed
manual endpoint corrections retain earlier playback; estimated lines are dashed.
`tests/test_player_connections.cjs` covers movement, short/long gaps, changed IDs,
scene boundaries, reattachment UI, pair/sequence editing, undo, persistence, and frame
timestamps. `dist/app.js` owns the connection UI, shared ring/line anchors, saved
foot offsets, frame-clock fallback, and optional signed cloud-upload flow. Optional
cloud-only training code is isolated under
`cloud/`: it creates pseudo-label candidates from sampled predictions, retains their
provenance, and never replaces the verified active checkpoint. See `cloud/DEPLOY.md`
for the provider boundary and data-retention behavior.

## Reviewed frame editor and supervised candidates

`dist/frame-review.js` provides incremental SHA-256 hashing, proposal-to-box conversion,
review validation, reviewed-only export, and the shared ring/box/label color resolver.
`dist/frame-review-ui.js` owns the separate frame-review dialog: video seeking,
box editing, roles/teams/identities, shirt sampling, draft persistence, and the local
collection/training controls. Tactical project edits remain separate from reviewed
ground truth. The editor exports the existing `touchline-groundtruth-v1` schema.

`training_workflow.py` validates and retains reviewed JPEG samples, enforces match,
source, and duplicate-image split boundaries, builds immutable YOLO datasets, and
runs explicit supervised fine-tuning from the checksum-verified football checkpoint.
It compares the baseline and validation-selected candidate on validation data and
records artifact checksums and provenance. Candidates stay inactive; test data is
untouched. `server.py` exposes these actions through `/api/training` routes with the
same host, origin, and mutation-header checks as video analysis. It prevents video
analysis and training from running simultaneously.

The local collection, dataset snapshots, and candidate outputs are under
`work/training/`, excluded from the distributable. Confirmed shirt colors calibrate
the same video; they are not new detector classes or a universal jersey model.
FRAME-LABELING.md describes the user workflow and evidence limits. Tests are in
`tests/test_training_workflow.py`, `tests/test_training_api.py`,
`tests/test_frame_review.cjs`, and `tests/test_frame_review_ui.cjs`. Editor event tests
use a simulated DOM/video decoder; candidate orchestration uses a mocked trainer.
