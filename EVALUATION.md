# Evaluation and training-data workflow

This workflow establishes a measured baseline before changing model weights. It runs
locally, retains exact settings and source hashes, and never promotes a model automatically.
No uploaded video or analyst correction trains the detector automatically.

## 1. Choose representative clips

Start with short clips from your own camera conditions: ordinary play, crowded play,
distant players, pans/zooms, shadows, difficult kits, and camera cuts. The reference
sample only proves the tooling works; it does not establish accuracy on your matches.
Tell us which errors matter most and which local video paths to use.

Use one explicit match ID for every excerpt of a match. All excerpts from that match
must stay in one training/validation/test split. Different filenames or timestamps do
not make nearby frames independent test data. The app cannot detect every near-duplicate
or infer match identity, so the human grouping decision matters.

## 2. Run the baseline

From the project directory, using the configured PyCharm interpreter:

```text
python benchmark.py --video "C:/path/to/short-clip.mp4" --match-id match-001 --output "work/evaluations/match-001-baseline"
```

The output directory must be new. Three cases compare one change at a time against
the baseline: football detector + ByteTrack at 960, ByteTrack at 640, and BoT-SORT at
960. Every case uses confidence 0.1 and stride 2. Inputs longer than 30 seconds are
rejected by default to prevent unexpectedly long CPU runs; explicitly increase
`--max-seconds` only after understanding the runtime.

REPORT.md summarizes timing and observations. report.json records the input SHA-256,
match group, video metadata, package versions, code hashes, model hash, settings,
failures, and case results. Timing includes model initialization and finalization;
these are single-pass measurements and are not universal hardware benchmarks.

Unlabeled diagnostics include observed role counts, identity counts, ball observations,
camera resets, and kit grouping. More detections or fewer IDs alone do not establish
better accuracy. This tool deliberately does not report mAP, HOTA, or IDF1.

## 3. Review frames and create ground truth

Each run creates `review/` with sampled JPG images, a blank groundtruth.template.json,
and separately named prediction-suggestions.json. Predictions are suggestions only.
Do not copy them into ground truth without inspecting and correcting each object.

For every scored frame, annotate all visible active players, goalkeepers, referees
(including assistants), and the visible ball. Spectators and coaches are background.
Keep this annotation scope consistent across matches. Use visible box extents for
occluded objects and label consistently; do not invent fully hidden objects.

Ground-truth object fields:

```json
{"id": 7, "role": "player", "team": "home", "bbox": [0.20, 0.30, 0.25, 0.60]}
```

Boxes are `[left, top, right, bottom]` normalized by image width/height. Person IDs are
manual identities consistent across reviewed frames; they are not detector track IDs
or automatically recognized jersey numbers. Ball `id` may be null. `team` can be
`home`, `away`, or `neutral`. Set each completed frame's `reviewed` and `fully_annotated`
to true only after manual review. Reviewed empty frames are valid negative examples.

Then score saved results without repeating expensive inference:

```text
python benchmark.py --video "C:/path/to/short-clip.mp4" --match-id match-001 --predictions "work/evaluations/match-001-baseline/football-byte-960.json" --ground-truth "work/evaluations/match-001-baseline/review/groundtruth.template.json" --output "work/evaluations/match-001-scored"
```

The scorer rejects different video hashes, incomplete review flags, invalid boxes,
and timestamps that do not match distinct processed prediction frames (within
10 microseconds for JSON rounding). It no longer accepts a nearby unprocessed frame.
It uses one-to-one IoU matching at 0.5 by default. It reports sampled-frame person/ball
precision and recall, role accuracy on matched boxes, within-scene sampled identity
switches, best-global-mapping team accuracy, and box-bottom error in pixels.

These limited sampled-frame metrics are not full-video tracking benchmarks. Box-bottom
error is not anatomical foot-keypoint error. Interpolated ball positions do not count
as observed detections. Sparse labels can miss errors between reviewed frames.

For comparison, the official SoccerNet tracking challenge evaluates complete tracking
sequences with HOTA as its main metric, including detection and association components.
This tool does not calculate HOTA, DetA, AssA, or IDF1, so its sparse sampled scores
must not be compared numerically with challenge results. See the [SoccerNet tracking
evaluation](https://github.com/SoccerNet/sn-tracking#evaluation) and [TrackEval
metrics](https://github.com/JonathonLuiten/TrackEval#currently-implemented-metrics).

The current UI offers ByteTrack and BoT-SORT. Ultralytics also documents OC-SORT as a
candidate for nonlinear motion without ReID, but this project has not exposed or
evaluated it. Add another tracker only as a controlled candidate on the same reviewed
clips; do not promote it based on general recommendations or raw track counts. See
[Ultralytics tracking guidance](https://docs.ultralytics.com/modes/track#which-tracker-should-i-use).

## 4. Export reviewed training data

Create a plan with multiple matches and reviewed annotation files:

```json
{
  "schema": "touchline-dataset-plan-v1",
  "clips": [
    {"video": "match-a.mp4", "ground_truth": "match-a-reviewed.json", "match_id": "match-a", "split": "train"},
    {"video": "match-b.mp4", "ground_truth": "match-b-reviewed.json", "match_id": "match-b", "split": "val"},
    {"video": "match-c.mp4", "ground_truth": "match-c-reviewed.json", "match_id": "match-c", "split": "test"}
  ]
}
```

Paths are relative to the plan file, or absolute. Run:

```text
python prepare_training.py --plan "C:/path/to/plan.json" --output "work/datasets/football-v1"
```

The exporter refuses split matches, duplicate source frames, inconsistent identical
video content, unreviewed labels, and empty-object training/validation splits. It
produces images/, labels/, data.yaml, and provenance.json. Class order matches the
default checkpoint: ball=0, goalkeeper=1, player=2, referee=3. A COMPLETE marker means
export finished, not that label quality or dataset sufficiency has been certified.
If export fails, an INCOMPLETE marker prevents mistaking a partial export for success.

## 5. Train only after the data review

Inspect the exported labels visually, check class coverage and diversity, then run
a one-epoch training smoke test before a longer fine-tune. Start from pretrained
weights, preserve an untouched test group, and compare candidates on the same held-out
matches. Do not tune on the final test matches. Keep best checkpoints and configurations,
and replace the app model only after detection, identity, team, and runtime comparisons.

The offline exporter does not start training. The app's **Review frame labels**
editor can save confirmed JPEG samples directly to the local collection and start an
explicit supervised candidate run. See **[FRAME-LABELING.md](FRAME-LABELING.md)** for
the complete labeling and training procedure, storage paths, and color-calibration
behavior. Training uses CUDA when supported by the installed PyTorch runtime and
otherwise uses CPU. Candidates remain inactive; test matches are not used by the
training comparison. No real pitch measurements are needed for image-coordinate
evaluation. Ask the user for verified dimensions before metric speeds/distances.
