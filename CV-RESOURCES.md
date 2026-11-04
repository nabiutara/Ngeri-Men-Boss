# Computer-vision source guide

Reviewed November 1, 2026. This is a focused collection of primary resources relevant
to Touchline Studio, not an exhaustive compilation of the internet. No new external
implementation or model weights were copied into this patch.

| Primary source | Relevance | Status in this app |
| --- | --- | --- |
| [Ultralytics tracking documentation](https://docs.ultralytics.com/modes/track/) | Persistent object IDs, tracker configuration and camera-motion options | Existing pinned local Ultralytics engine with explicit BoT-SORT or ByteTrack selection; no automatic upgrade |
| [ByteTrack authors' repository](https://github.com/FoundationVision/ByteTrack) | Detection association, including low-confidence detections | Existing optional tracker through Ultralytics; provenance retained |
| [BoT-SORT authors' repository](https://github.com/NirAharon/BoT-SORT) | Motion, appearance and camera-motion tracking methods | Existing stability preset uses camera-motion compensation; appearance ReID is not enabled |
| [OpenCV DNN / NMSBoxes reference](https://docs.opencv.org/4.x/d6/d0f/group__dnn.html) | Suppression of overlapping detector boxes | Existing person NMS in the engine; additional presentation filtering handles torso/full-body duplicates in saved results |
| [Ultralytics pose documentation](https://docs.ultralytics.com/tasks/pose/) | Body keypoints and per-keypoint confidence | Potential future ankle-anchor experiments; current rings use detection bottom centers |
| [TrackEval authors' repository](https://github.com/JonathonLuiten/TrackEval) | HOTA, DetA, AssA, IDF1, and other tracking metrics | Reference for future complete-sequence evaluations; current local scorer is sampled-frame only |
| [SoccerNet tracking challenge](https://github.com/SoccerNet/sn-tracking) | Soccer-specific tracking benchmarks and evaluation resources | Future benchmark reference; no dataset downloaded or training started |
| [Ultralytics tracker guidance](https://docs.ultralytics.com/modes/track) | Tracker capabilities and footage-specific selection guidance, including OC-SORT | OC-SORT is a future evaluation candidate; ByteTrack and BoT-SORT remain the only app choices |

## Decisions for this repair

Detector confidence, duplicate suppression and temporal identity are different
problems. Tightening a global threshold can remove real players during a challenge.
Instead, this patch addresses the nested-body duplicate pattern observed in MATCH1
at the presentation layer, preserves source results and offers manual correction.
This containment rule is a project-specific heuristic, not an accuracy guarantee
endorsed by the sources above. See OVERLAY-FIX.md for exact checks and limitations.

Real improvements to identity across occlusion require separately annotated clips,
consistent ground truth and independent evaluation. A pose model may improve ankle
placement but adds runtime cost and can also fail on small or occluded players.
Neither a newer model name nor an attractive overlay proves higher accuracy.

Original football detector attribution, checkpoint hash and reference repository
remain in MODEL-PROVENANCE.json, REPOSITORY-ANALYSIS.md and analysis exports.


[MDN requestVideoFrameCallback](https://developer.mozilla.org/en-US/docs/Web/API/HTMLVideoElement/requestVideoFrameCallback) documents the presented media timestamp used by the 2.8 overlay clock. The API is not a guarantee of exact synchronization on every display.
