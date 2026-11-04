# Player identity and ring stability

The default tracker is Ultralytics BoT-SORT with its built-in sparse optical-flow
camera compensation. ByteTrack remains selectable. Both retain low-confidence
observations for association and suppress near-identical person detections across
roles at 0.70 IoU before matching. Ball candidates are separate. Confidence-score
fusion is disabled so fluctuating detector confidence does not multiply the
first-stage geometric matching cost. Detection and track-birth thresholds still apply.

Goalkeepers and players share an association class while retaining the detector's
role. Shirt-color grouping does not recognize individual players or jersey numbers.
Appearance ReID is not enabled. Tracks can still switch when similarly dressed
players overlap or disappear. Camera cuts or failed motion estimates reset the
tracker, and exported IDs are never reused across those resets.

The ring renderer holds its previous smoothed position when video time repeats;
pauses, seeks, camera cuts and large jumps reset smoothing. The marker uses three
rotating arcs on one ellipse, jersey colors, a soft glow and a fixed rear leg gap.
The November 1 follow-up handles nested torso/full-body duplicate boxes even when
automatic kit groups disagree. Rings, labels and selection share the filtered list.
See OVERLAY-FIX.md for reviewed cases, regression evidence and manual overrides.

## MATCH1 development evidence

MATCH1 is a 7.89-second user-provided clip. At input size 960, confidence 0.1 and
stride 2, the original detector outputs were saved once and replayed to isolate
association changes. The original baseline replay reproduced its 103 generated IDs.

An assistant visually reviewed approximate boxes for the goalkeeper and central blue
forward in six source frames and one near-side blue winger in the first three.
Later near-side identity was uncertain and excluded. These are 15 selected-person
samples, not full-frame ground truth and not training labels.

| Selected-person check | Original ByteTrack | Stability BoT-SORT |
| --- | ---: | ---: |
| Matched reviewed samples | 15 / 15 | 15 / 15 |
| Sampled ID changes | 4 | 1 |

The final production defaults reproduce the selected replay. The unchanged model
checksum is recorded in the result comparison. These development samples were used
to choose settings, so they are not independent test accuracy. Sparse review can miss
errors between samples and for other players. No mAP, HOTA or IDF1 is claimed.

A custom camera-reference-coordinate experiment was rejected after worsening the
initial review; that implementation is not part of the shipped engine. A later
visual check also corrected provisional review counts by excluding ambiguous
near-side samples. The corrected 15-sample figures above are authoritative.

Full-clip generated ID counts were 103 before and 106 after, including transient
false positives and fragmentation. The lower sampled switch count must not be
presented as eliminating those problems. The remaining reviewed change is a late
goalkeeper ID replacement. Occlusion recovery, referee classification and false ball
detections still need broader reviewed data.

Use the updated editable MATCH1 project to inspect existing results. Existing saved
projects keep their previous IDs. New analyses use the new settings after restarting
the local server; reload the browser to load the updated ring renderer. No weights
were retrained, footage uploaded, physical dimensions assumed or metric speeds added.

## 2 November working-tree update

The current uncommitted UI changes add shared duplicate filtering for display and
selection, editable names, an overlap visibility override, foot-position offsets,
custom player connections, and decoded-frame timing. The engine diff also changes
camera drift handling, ball candidate gating, tracker-row parsing, and timestamps.
These changes preserve the stored detection rows in the reviewed code, but their
current working-tree regression status has not been verified. The MATCH1 duplicate
fixture covers six reviewed pairs and is not complete match ground truth or
evidence of detector or identity accuracy.
