# Review frames, correct shirt colors, and train candidates

This workflow keeps Touchline's football model, four detector roles, editable
tracking overlays, tactical drawings, and interpretation controls. It adds reviewed
data and local candidate training. Training is an explicit action; processing or
reviewing a video does not automatically replace the active model.

## 1. Open the review editor

1. Restart **Start Touchline.cmd** after installing this update and refresh the
   browser. The health response includes `reviewed_training: true`.
2. Import or re-link the original match video. You can use the PC browser or the
   phone on the same Wi-Fi; samples and training jobs go to the PC's local server.
3. Optionally run **Analyze uploaded video** to obtain initial box proposals. Pause
   near a difficult frame, then choose **Review frame labels** in the tracking panel.
4. The editor identifies the video by SHA-256. Its incremental hash works over
   local Wi-Fi HTTP without requiring the browser's secure-context crypto APIs.

The editor opens at the playhead. **Previous frame** and **Next frame** navigate
using **Navigation FPS**, initialized from the tracking results when available.
Without results, set it to the video's frame rate (the initial value is 30).
**Time (seconds)** and **Go to time** let you choose any position without analysis.
**Capture playhead** uses the main video's current time without snapping elsewhere.
Frame navigation is nominal; variable-frame-rate sources and browser seeking can
be approximate. Inspect the displayed image before confirming its labels.

**Previous analyzed sample** and **Next analyzed sample** still follow the detector's
processed timestamps. Proposals are loaded only at their matching timestamp, never
silently copied onto a different frame. They include filtered and excluded tracks;
interpolated ball positions are excluded.

## 2. Label the complete image

Enter a **Match ID** and choose **Training**, **Validation**, or **Test**. Every clip
from the same match must use the same ID and split. Use separate matches for training
and validation, and reserve test matches for a later final assessment.

- Select a box from the image or object list. Drag the box to move it; drag a selected
  corner to resize it. The numeric edge fields use percent of the source image.
- Choose **New object role** and **New object team**, then use **Add missing object**
  (N) to add missed players or the ball. Draw tight, full-body
  boxes for people. Label every visible target belonging to the four supported roles, across both
  teams. Staff and spectators are background, not players. Remove detections on
  these non-target people, false objects, and duplicate body parts.
- Choose **Player**, **Goalkeeper**, **Referee**, or **Ball**. Training preserves the
  checkpoint's class order: ball=0, goalkeeper=1, player=2, referee=3.
- Correct **Person ID** when evaluating identities across frames. These are reviewed
  person identities, not automatically recognized jersey numbers. Keep one person's
  ID consistent and use distinct person IDs within each frame.
- Set **Home**, **Away**, or **Unassigned**. These labels are retained for team
  evaluation and color calibration; they are not additional YOLO detector classes.
- **Pick color from shirt** samples a small pixel neighborhood at the point you tap.
  Choose a clear shirt patch, then inspect the enlarged player crop. A sample from
  grass, skin, a sponsor, or a shadow can be wrong even when a box is correct.
- **Delete false box from labels** removes only the selected frame's object.
  **Clear all boxes in this frame** starts that frame over after confirmation.
- **Undo** and **Redo** restore edits within the current frame. Both require review
  again. Keyboard shortcuts: Ctrl+Z, Ctrl+Y, or Ctrl+Shift+Z.
- **Copy previous frame labels** copies the nearest earlier labeled frame as a draft.
  It replaces the current boxes after confirmation when necessary. Adjust every box
  to the new image and recheck person IDs after cuts. The previous frame is unchanged;
  copied labels cannot apply edits to unrelated detector tracks.
- Arrow keys move the selected box by one source pixel; Shift moves ten pixels.
  Delete removes a selected box, V selects/moves, and comma/period step frames.
  Shortcuts do not interfere with typing in form fields.

Check the complete-frame confirmation only after adding missed objects and removing
false ones. Then choose **Confirm & save reviewed frame**. A genuinely empty image
can be confirmed as a background sample; an incompletely labeled image must not be
treated as background.

Each confirmation saves the reviewed JPEG and labels on the PC. Later draft edits
do not replace that saved training version until confirmed again. **Remove this
review frame** removes its browser review and PC sample when the local service is
available. Existing dataset snapshots and completed candidates remain unchanged.

## 3. Correct rings and box colors

Rings, bounding boxes, and player labels now use the same resolved color. The
**Detected kit colors** setting uses the detected or reviewed palette for all three.
Changing the Home/Away color controls selects your manual palette. A player's
**custom track color** takes precedence over both palettes.

In the review editor, **Apply team / shirt color to this track** applies the selected
team and any sampled shirt color to the source analysis track. **Exclude false track
from analysis** hides that track and removes its box from this frame's labels.
Both analysis corrections can be undone with the main workspace's Undo control.
An identity switch can transfer a track's correction to another person, so review
the affected sequence and reconnect tracks when necessary.

For automatic team assignment on the next analysis, save confirmed shirt colors
from at least **three distinct reviewed outfield-player IDs per team**. Re-analyzing
the exact same video uses the median reviewed shirt samples to guide its team-color
assignment. It does not transfer home/away semantics to unrelated videos. Goalkeeper
teams remain manual. Similar team colors and uncertain crops can leave tracks
unassigned; this calibration does not provide universal jersey recognition.

## 4. Export and retain your work

Browser drafts are cached in IndexedDB per video hash. **Export reviewed labels**
downloads only completely reviewed frames as `touchline-groundtruth-v1` JSON. The
export includes source identity, match ID, roles, boxes, IDs, teams, and optional
shirt colors. Importing labels verifies the video hash before replacing a browser
review. Export before clearing browser data or moving to another browser.

Review drafts are separate from the main tactical project JSON. Save a project for
drawings and track overrides, and export reviewed labels for portable annotations.
`prepare_training.py` can still export an offline YOLO dataset from reviewed JSON
and the original videos; see **EVALUATION.md**.

The local PC collection is under `work/training/frames/`. It retains sampled JPEGs
and labels, not the full source video. Keep the original video yourself if you need
to revisit frames. The inference job's temporary full-video copy is deleted after
processing as before. None of these runtime artifacts are included in the ZIP.

## 5. Train and compare a candidate

The editor shows the accumulated frame, match, class, and background counts in each
split. Candidate training becomes available once **all four roles are represented
in both training and validation**, using different matches. These are structural
requirements, not evidence that the dataset is large or diverse enough.

1. Start with **1 epoch · smoke test**, batch 1, and appropriate image detail. Inspect
   the saved training-batch previews for label alignment before a longer run.
2. Choose **Train candidate on PC**. The PC uses CUDA if its installed PyTorch runtime
   supports it; otherwise it trains on CPU. Keep the PC and launcher running. Video
   analysis and candidate training cannot run simultaneously.
3. The worker creates an immutable dataset snapshot, verifies the original football
   checkpoint, and validates the baseline on the validation matches.
4. It fine-tunes from that checkpoint, retains the validation-selected `best.pt`, and
   validates that candidate on the same validation data. Reserved test frames remain
   untouched. **Cancel candidate run** requests cancellation at the next model batch.
5. Download the inactive checkpoint and its comparison/provenance JSON after success.
   Completed candidate entries are restored when the local server restarts.

Snapshots are under `work/training/datasets/<run-id>/`; runs, training plots,
checkpoints, and manifests are under `work/training/runs/`. The manifest includes the
source dataset checksum, base/candidate checksums, settings, package versions, and
baseline/candidate detection validation metrics. No checkpoint is activated by this
workflow. A one-epoch result is a workflow check, not proof of improved accuracy.

Detector validation measures the four object roles. It does not establish improved
tracking identities, smooth ring movement, shirt-color classification, or jersey
number recognition. Review separate match footage and tracking metrics before any
future model activation. The optional cloud pseudo-label worker remains a separate
experimental deployment; these supervised collection/training routes run locally.

## Verification and provenance

Regression checks exercise source hashing, box conversions, review confirmation,
draft invalidation, sampled-color overrides, match/content leakage guards, dataset
snapshots, HTTP routes, and candidate artifact selection. Editor actions are checked
with a simulated DOM/video decoder. Candidate orchestration is tested with a mocked
trainer; no real model improvement is claimed. Visual browser verification remains
limited by the current Computer Use browser access failure.

The supervised workflow was informed by the educational sequence in
[EdjeElectronics/Train-and-Deploy-YOLO-Models](https://github.com/EdjeElectronics/Train-and-Deploy-YOLO-Models).
Its example detector and random image splitter were not copied. Touchline retains
its existing model provenance, match-level split guards, and Ultralytics trackers.
