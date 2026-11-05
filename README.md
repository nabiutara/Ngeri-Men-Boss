# Touchline Studio

A local soccer-video analysis workspace with customizable player overlays, tactical drawings, formation boards, and your own interpretation notes.

For frame labeling, shirt-color corrections, and local candidate training, follow
**[FRAME-LABELING.md](FRAME-LABELING.md)**. The app's **Review frame labels** button
opens the editor. Rings, boxes, and labels share one color source, with per-track
manual overrides. Confirmed shirt samples can calibrate the next analysis of the
same video. Candidate training is explicit and never activates a checkpoint.

For measured comparisons and offline reviewed datasets, follow **EVALUATION.md**.
`benchmark.py` compares fixed configurations, `evaluation.py` scores manually reviewed
labels, and `prepare_training.py` exports YOLO data with match-level split guards.
The optional cloud worker can create experimental pseudo-label candidates; it never
replaces the verified active model. See `cloud/DEPLOY.md` for the private cloud setup.

## Independent project

Touchline Studio has its own local Git history and no upstream remote. The reference
checkout is research material only; the application does not depend on it. Code,
tests, packaging, and model configuration are maintained inside this project folder.
Third-party model ownership and provenance remain documented in MODEL-PROVENANCE.json
and REPOSITORY-ANALYSIS.md. Removing Git ancestry does not change the origin of trained weights.

Physical pitch dimensions are not assumed. Tracking uses dimensionless coordinates.
Before adding real-world distances or speeds, ask the user for verified measurements.

To rebuild the portable ZIP from this folder, run `python build_package.py`.

For a file-by-file explanation and code provenance, start with **SOURCE-GUIDE.md**.
**CODE-MAP.md** indexes declarations and UI handlers; **DEPENDENCIES.json** lists
the installed third-party library versions and their declared source locations.

See **REVIEW.md** for the code/model review, repaired defects, compatibility notes,
and validation limits. It distinguishes earlier check results from the current
unverified working-tree changes.

## Open the app on Windows

1. Extract this folder somewhere writable.
2. Install Python 3.11–3.13 if needed; enable **Add Python to PATH**.
3. Double-click **Start Touchline.cmd**. It reuses the installed workspace environment when available; otherwise first setup downloads the tracking packages. The browser opens only after the server responds.
4. The workspace opens at **http://127.0.0.1:8765**. The launcher also prints a **Phone link (same Wi-Fi)**. On the phone, open that address while it is connected to the same Wi-Fi as the PC. The app footer's **Connect phone on Wi-Fi** button shows and copies the link. Keep the launcher window open; closing it stops the server. If Windows Firewall asks, allow Python on **Private networks only**.
5. Import your video, then click **Analyze uploaded video**. Model weights download on the first analysis.

The Windows launcher allows devices on your local Wi-Fi to reach the app. Phone and PC
must stay on the same network and the PC must remain on. The server still runs on the
PC; video processing and storage stay there. This does not publish the app to the
public internet. Use **Open Touchline.cmd** for PC-only loopback mode.

The optional cloud deployment is separate and sends video to Cloudflare R2 for
temporary storage and a Modal GPU worker; raw clips are deleted after processing, while
pseudo-labeled sample frames and candidate checkpoints are retained. Review
`cloud/DEPLOY.md` before enabling cloud uploads.

A fresh ZIP installation downloads its own dependencies and the 173 MB model.

If the launcher fails during setup, it now prints the Python/package error and saves
the details in `work/setup.log`. Server startup failures print the current attempt's
output from `work/server.log`. The Windows launcher limits numerical-library threads
to reduce memory pressure; this does not guarantee that a large video will fit in RAM.

If you see `Could not open requirements file`, the launcher is in an incomplete
folder. Extract the entire ZIP, open its `Touchline Studio` folder and run the launcher
there. Keep `requirements.txt`, `launch.py`, and `dist` beside the launcher. Use a
Windows shortcut if you want to launch from Desktop or Downloads; copying only the
CMD file does not copy the application. The updated launcher checks for missing
application files before creating an environment or installing anything.

## Your workflow

- **Track:** The football-trained checkpoint linked by `nabiutara/football_analysis` detects players, goalkeepers, referees, and the ball. Camera-aware BoT-SORT is the default identity tracker; ByteTrack is selectable. YOLO26 Small and Nano remain general-purpose fallbacks. CUDA is used when supported by the installed PyTorch runtime; otherwise analysis uses the CPU.
- **Assign:** Outfield players are grouped by repeated shirt-color observations. Home/Away initially name color groups, not verified venue identities; swap them when needed. Click any track to correct its team or display label. Goalkeepers remain unassigned until you choose their team. Jersey numbers are not recognized automatically.
- **Customize:** Toggle foot circles, labels, trails, boxes, team connections, the ball marker, and referees. Referees are hidden by default. Use detected kit colors only when you want to replace your custom palette. Adjust team colors, circle size, and opacity.
- **Draw:** Add lines, arrows, circles, zones, or interpretation boxes. Select and drag to move, or drag the ending handle to resize. Change color, thickness, and start/end time. Drawings initially last eight seconds.
- **Interpret:** Write freely in the session notes, add timestamped notes, or place editable text directly on the video. No interpretation text is generated for you.
- **Formation:** Choose 4-3-3, 4-4-2, 4-2-3-1, 3-5-2, or 3-4-3 and move the board markers. With all four pitch corners visible, calibrate top-left, top-right, bottom-right, bottom-left. Assigned tracks then map onto the board. Optical flow compensates modest pan/zoom within the shot. Recalibrate after cuts, large perspective changes, lost camera tracking, or visible drift. Templates are tactical references, not automatic formation classification.
- **Save:** Edits autosave in your browser; tracking results use its local cache. Save a project JSON for a portable backup. Projects contain tracking and edits, but do not embed video. Re-link the original file by importing the same filename.
- **Export:** Save an annotated PNG, text notes, an editable project, or a silent WebM recording from the current playhead. WebM export runs in real time, requires a visible tab, and is limited to five minutes per recording. It does not preserve audio.

The initial demo contains animated illustrations and simulated tracks. Import a real clip to use real detections. No demo tracks are placed over uploaded footage.

## Controls

Foot markers use three gently rotating arcs on one thin, glowing ellipse, with a
rear gap for the legs. Ring size adapts to the player box, up to your Circle size
setting. Full-body / torso duplicates are filtered together for rings, labels,
selection and formation display. The original tracking data is retained.

**Edit a label:** choose a player in **Player labels & details** directly below the
video, or click the player. Type your text into **Player label**; it updates and
saves immediately. Save project includes the edited names. A blank field falls back
to the track number. Names belong to track IDs, so review them after an ID switch.
Use **Keep visible during overlaps** if a real overlapping player was filtered;
use Team → Exclude to hide a false track. The picker includes filtered tracks.

See **OVERLAY-FIX.md** for the six reviewed MATCH1 duplicate cases and limitations,
and **CV-RESOURCES.md** for the primary computer-vision sources reviewed.

Space: play/pause. Left/right arrows: seek 5 seconds. V: select. L: line. A: arrow. C: circle. Z: zone. T: interpretation box. Ctrl+Z: undo drawing/player/formation edits. Delete: delete selected drawing. Drag and drop a video onto the canvas to import it.

## Other launch options

```sh
python -m venv .venv
# Activate the environment, then:
python -m pip install -r requirements.txt
python server.py --open
```

To open the editing workspace before installing YOLO, run `python server.py --open` with standard Python. Tracking will be marked unavailable until requirements are installed.

To generate tracking results separately:

```sh
python server.py --input match.mp4 --output tracking.json --model football-best.pt --tracker botsort --imgsz 960 --stride 2
```

Import the matching video in the browser, then use **Get the local YOLO app → Import tracking JSON**.

## Practical limits

- The default model is football-specific. A short MATCH1 development comparison and selected-player review have been completed; full-match tracking accuracy remains unmeasured. Small distant players, overlaps, cuts, and camera motion can cause missed detections or ID switches.
- Foot markers use the bottom center of a detected person box, not anatomical pose estimation. Formation mapping assumes a flat pitch and a reliable camera transform. Partial-pitch broadcast views need manual board work or a more advanced field-line/camera model.
- Use H.264 MP4 for broad playback compatibility. Uploads are limited to 2 GB; analysis accepts videos up to four hours and 250,000 processed frames. Very large result files may be slow to load or export.
- The runner accepts one job at a time and allows devices on the same Wi-Fi when launched with **Start Touchline.cmd**. It is not a public hosted inference server. Uploaded temporary copies are removed after completion/cancellation; tracking result files and downloaded weights remain under `work/`.
- The app's runtime data is not included in the source archive. Use **Save project** for a backup; clearing browser storage removes autosaved edits.

## Verification and performance

The current source inventory contains 48 Python tests across seven modules and
eight JavaScript check scripts. The suites cover the tracking pipeline, reviewed
sample storage, dataset guards, training HTTP routes, and candidate orchestration.
Editor events use a simulated DOM/video decoder, and trainer orchestration uses a
mocked trainer; these tests do not establish accuracy gains on real matches.
Visual browser verification of the new editor is still pending because Computer Use
could not verify the current browser URL. Earlier functional evidence includes recorded model
inference on a three-second excerpt of the repository's match sample. At stride 2
and 960 detail on the recorded CPU setup, it processed 37 frames in about 69
seconds, assigned 20 track identities to two kit-color groups of 10, and observed
the ball in 20 frames. This is historical functional evidence, not a labeled
accuracy benchmark.
The total 28 track IDs include referees, goalkeepers, and fragmented identities; they are not 28 unique players.

This large football model is an offline analyzer. For faster CPU work, use 640 detail, larger stride, or a
YOLO26 fallback. A supported CUDA setup can accelerate it. Inspect short clips before processing a full match.

See **REPOSITORY-ANALYSIS.md** for the reviewed commit, model checksum, adopted fundamentals, corrected sample
assumptions, and remaining limits. Automated checks can be run with:

```sh
python -m unittest discover -s tests -v
node tests/test_football_ui.cjs
node tests/test_foot_markers.cjs
node tests/test_video_import.cjs
node tests/test_player_connections.cjs
node tests/test_player_labels.cjs
node tests/test_cloud_client.cjs
node tests/test_frame_review.cjs
node tests/test_frame_review_ui.cjs
```

## Model documentation

The integration is based on, [Ultralytics YOLO26](https://docs.ultralytics.com/models/yolo26/) and [Ultralytics tracking](https://docs.ultralytics.com/modes/track/). The Ultralytics dependency and model weights have their own licensing terms; see the [Ultralytics license](https://www.ultralytics.com/license).

Startup failures are recorded in `work/server.log`. Reopening the launcher reuses a healthy local server. If another app occupies port 8765, the launcher reports that conflict without terminating it.

If the browser says **refused to connect**, start **Start Touchline.cmd** (or the adjacent **Open Touchline.cmd**) and wait for **Touchline Studio is ready**. A browser bookmark alone cannot start the local app. On the phone, use the exact **Phone link (same Wi-Fi)** printed by the launcher; the PC's address may change when the Wi-Fi reconnects. If the phone cannot connect, check that both devices use the same non-guest Wi-Fi and allow Python through Windows Firewall for private networks. If startup fails, the launcher stays open so you can read the error; its log is `work/server.log` inside the app folder.


## Custom player connections (asset version 3.1)

Below the video, open **Connect your players**, select **Sequence** or **Individual
pairs**, and press **Start connecting**. Click the players in your desired order,
then **Finish** and play. Alternatively, choose each player in the label picker and
press **Add selected player**. Your chosen edges are preserved, rather than sorted
by changing screen position. Color and thickness use the drawing toolbar settings
at creation time. Clear connections and Undo are available. Save project preserves
connections. Custom edges take precedence over automatic team-shape lines in the
same scene. The toolbar's **Line** tool is a fixed drawing; use **Start connecting**
for lines that follow players.

A brief detection gap can be filled when the same track appears on both sides
within 0.6 seconds in the same camera scene. Position and box-size guards reject
large discontinuities. Rings and line endpoints share the interpolated position;
dashed connections identify estimates. Longer gaps, scene cuts and changed IDs are
not inferred. A hidden line remains saved and returns when its endpoints are visible.
Source detections and training samples are unchanged by this presentation feature.

If a player gets a new ID, pause at the point of the change. Under **Connect your
players**, choose the **Old connection track**, select the replacement player in
the video or player picker, and press **Reattach to selected player**. All lines
using that endpoint follow the replacement from the current time onward; playback
before that time retains the old ID. Reattachment is limited to the current scene,
supersedes later corrections on that endpoint, and supports Undo and Save project.
This changes connection endpoints, not the detector's identities or player labels.
For a real player suppressed by the overlap filter, use **Keep visible during
overlaps** in the player editor. Excluded players remain excluded.

Regression fixtures cover dropouts, long gaps, cuts, large jumps, timed ID repairs,
seeks, the repair controls, dashed drawing, Undo and project round trips. No accuracy
gain on the user's video has been measured; a long occlusion still needs review.

Select a player to adjust **Foot position** left/right and up/down. Values are
percentages of that player's detection box, not physical pitch measurements.
Positive values move right/down; zero resets. These corrections move both the ring
and custom connection endpoints and persist with the project.

Playback now uses decoded-frame timestamps through requestVideoFrameCallback where
available, with a playback-clock fallback if frame callbacks stop. During a seek the
previous canvas stays intact until the video is ready. Additional smoothing lag is
limited to 8% of ring radius (previously 25%). This reduces presentation lag; it does
not repair incorrect detector boxes or identity switches. No pose model was added,
no new training was run, and a full MATCH1 visual accuracy improvement has not yet
been measured for this timing change. Connection behavior and timing are covered
by automated regression checks; the local browser loads the new controls.
