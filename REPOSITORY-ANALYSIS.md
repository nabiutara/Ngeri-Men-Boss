# Football pipeline integration

Reference repository: [nabiutara/football_analysis](https://github.com/nabiutara/football_analysis).
Reviewed commit: `e4799632cdf271cf57f4eb0c4d872cf1b7ab0f17`.

The repository was cloned and its main pipeline, tracker, team assigner, camera estimator,
perspective transform, possession assignment, speed estimator, and training notebook were inspected.
Its code was treated as a reference; Touchline's implementation is independently written.
No repository pickle stubs, notebook API keys, or fixed clip coordinates are executed or reused.

## What Touchline adopts

| Fundamental | Integration |
| --- | --- |
| Football-specific YOLO detection | The exact checkpoint linked by the repository is the default; class names are read from the checkpoint: ball, goalkeeper, player, referee. |
| Person identities | Uses maintained Ultralytics trackers with low-confidence detections retained for association. Camera-aware BoT-SORT is the stability default after the MATCH1 development review; ByteTrack remains selectable. Near-identical person boxes are suppressed across roles before matching. See STABILITY.md. |
| Goalkeeper handling | Goalkeepers share the player association class but keep a separate output role. Their team remains manual because keeper kits usually differ. |
| Shirt-color clustering | Upper-torso Lab-color clustering; repeated observations per track; local background suppression; isolated outlier rejection; abstention when two reliable groups cannot be found. |
| Camera-motion estimation | Pyramidal optical flow with forward/backward validation and RANSAC. Moving people are masked out, transforms accumulate, and a failed estimate starts a new reference segment. |
| Perspective transformation | Preserves the existing user-selected four-corner pitch calibration and maps current player feet back into its reference frame. Cuts or lost camera motion require recalibration. |
| Ball positions | Uses center positions, temporal candidate selection, and interpolation only across short, bracketed gaps within the same scene. Interpolated balls use a dashed marker. |
| Nearest-player ball association | Exposes a proximity candidate in results only when the ball was observed. It does not claim measured possession or carry ownership through missing observations. |

The existing page layout, palette, drawing tools, foot-circle customization, notes, and export flows remain.
Small additional controls expose ball/referee visibility, tracker choice, analysis detail, kit colors, and team swapping.

## Corrections to sample-specific assumptions

- Videos and detections are streamed; frame records are spooled to disk and finalized in a second pass. Full video frames are not accumulated in memory.
- The video supplies its actual frame rate, size, duration, and stride-adjusted timestamps.
- Fixed pixel thresholds and hard-coded team overrides are replaced with normalized coordinates, relative distances, and editable assignments.
- Empty detections, unavailable ball observations, empty crops, insufficient team samples, featureless frames, and cancellation have explicit handling.
- Optical-flow status, forward/backward error, inlier ratio, translation, and scale are checked. The single largest feature displacement is not used as camera motion.
- Track IDs are unique across reset segments. Interpolation and trails do not cross scene boundaries.
- Green kits are preserved by comparing torso pixels with the surrounding background, rather than deleting all green pixels.
- Isolated dark uniforms cannot dominate the two-team fit. Uncertain tracks are left unassigned.
- Real speed and distance are not produced from the repository's fixed 24-fps setting and sample-specific pitch rectangle. Metric measurements need verified calibration and additional accuracy validation.

## Model provenance and selection

Upstream checkpoint: [repository-linked football model](https://drive.google.com/file/d/1DC2kCygbBWUKheQ_9cFziCsYVSRw6axK/view).

SHA-256: `53fcd08a5e5283d7bba705f07fc04022a6ab73a2ba2a847d3bc8143c9ecad2eb`.

The 172,628,985-byte checkpoint loads under Ultralytics 8.4.192 with restricted checkpoint loading enabled.
Downloads and local reuse are checked against the recorded digest. Model files are cached locally and are
not embedded in the distributable source ZIP. A new installation fetches this exact upstream checkpoint
on the first football analysis. General YOLO26 Small and Nano remain explicit fallbacks.

The football checkpoint is selected because it was trained for this task and distinguishes roles that
the previous generic person detector could not. This does not establish that it is the best model on
every match: no labeled evaluation set or competing football checkpoints were supplied. Detections and
IDs can still fail under small-player views, occlusion, blur, cuts, unusual kits, or severe camera motion.

## Team and formation semantics

Home/Away initially name the two detected kit groups; the algorithm cannot infer venue semantics.
Use **Swap home / away**, or correct individual tracks. Your chosen overlay colors stay unchanged unless
you select **Use kit colors**. Referees are hidden by default and can be shown separately.

The formation board remains a customizable tactical template or calibrated track map. It does not
claim to infer a team's tactical formation label. Four corners must be visible for the existing
calibration tool. Optical flow compensates modest pan/zoom within a shot; it is not a full field-line
camera reconstruction. Recalibrate when alignment drifts or the app displays **RECALIBRATE**.

## Verification

Automated tests cover kit separation (including green shirts and isolated outliers), insufficient
evidence, camera translation, scene cuts, featureless frames, bounded ball interpolation, missing
detections, variable frame timing, cancellation cleanup, camera-adjusted board projection, and malformed
result imports. The actual checkpoint is also exercised on the repository's linked match video.

Sources: [Ultralytics tracking](https://docs.ultralytics.com/modes/track/),
[reference tracker](https://github.com/nabiutara/football_analysis/blob/e4799632cdf271cf57f4eb0c4d872cf1b7ab0f17/trackers/tracker.py),
[reference team assignment](https://github.com/nabiutara/football_analysis/blob/e4799632cdf271cf57f4eb0c4d872cf1b7ab0f17/team_assigner/team_assigner.py).
