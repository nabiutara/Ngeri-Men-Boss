# Code and model review — 1 November 2026

## Working-tree follow-up — 2 November 2026

The current diff changes bounded team-color sampling, camera transform drift
resets, time-adaptive ball candidate gating, defensive tracker-row handling, and
stride-based timestamps. The UI diff adds nested-box filtering shared by rings,
labels, selection and formation display; editable labels and overlap overrides;
per-player foot offsets; saved player connections; and decoded-frame clock
handling. Packaging now includes the corresponding assets, tests, and review
notes. These are source-level findings, not confirmation of passing behavior or
improved end-to-end tracking accuracy.

This follow-up also found and corrected an evaluation alignment flaw: labels up to
half a processing interval away from a prediction timestamp could be scored against
the wrong frame. Scoring now requires a timestamp match within 10 microseconds, and
a midpoint regression was added. This aligns the local scorer with its own reviewed
frame template; it does not turn sampled metrics into standard tracking scores.

The current tree contains 31 Python test methods across four test modules and five
JavaScript check scripts. This count comes from source declarations. Test execution
was attempted: the Python suite could not import `lap` and OpenCV (`cv2`), and the
JavaScript scripts could not start because Node.js is unavailable on PATH. Three
launcher tests completed successfully before the suite reported dependency errors.
The current working-tree suite therefore remains unverified. The six MATCH1
duplicate fixtures are visual review examples, not complete ground truth or a
training set.

The repair table and environment notes below record the 1 November review; their
test results describe that earlier tree, not the current uncommitted follow-up.

## Repairs

| Finding | Repair | Evidence |
| --- | --- | --- |
| Team clustering allocated a full pairwise distance matrix across every identity, which can exhaust memory on long clips with fragmented tracks. | Limit fitting to a deterministic, seeded sample of at most 512 identities; assign all observed identities against the resulting centers. | A 1,200-identity regression was recorded for the 1 November tree; it checks bounded fitting and classification in a separable fixture. |
| Importing an unreadable video cleared the active media before validating the replacement. | Validate metadata on a separate video element, release failed object URLs, and commit a replacement only after successful validation. Add a metadata timeout. | A rejected-media regression checks that the original clip and interpretation remain untouched. |
| An old request failure could clear the status of a newer analysis after cancellation. | Ignore failures whose job generation no longer matches the active generation. | Both upload and polling error paths use the existing generation guard. Syntax checked; delayed-request browser behavior has not been exercised end to end in this review. |
| Imported settings accepted truthy strings where checkbox booleans were expected; invalid clip durations could enter saved state. | Accept actual booleans and positive finite stored durations only. | Reviewed sanitizer; syntax/import checks were recorded for the 1 November tree. |
| Runner capability flags remained true after a previously reachable runner disappeared. | Reset capability flags before each health probe. | Reviewed health-probe state transition. |
| A job could report completion just before its temporary upload was removed. | Remove the uploaded copy before publishing completed status. | Cancellation and temporary-file checks were recorded for the 1 November tree. |
| Dead imports and compressed import logic obscured intent. | Remove unused server imports and expand the media-import function into readable steps. | Python compilation and JavaScript parsing were recorded for the 1 November tree. |

## Compatibility

The checked local environment is Windows / Python 3.13 with Ultralytics 8.4.192,
PyTorch 2.15.0, torchvision 0.29.2, OpenCV 5.0.0.93, NumPy 2.5.4, LAP 0.5.13,
and gdown 5.2.2. See DEPENDENCIES.json for the full installed inventory. These
versions are retained rather than upgraded without a comparative benchmark.

The exact default football checkpoint passes its SHA-256 check and restricted load;
its classes remain ball, goalkeeper, player, and referee. Server model choices match
the engine registry. Runtime imports resolve inside this independent project and
do not require the reference clone. Portable packaging excludes model binaries and
runtime environments; a new installation downloads dependencies and weights.

## Model assessment and limits

The default checkpoint supplies football roles that a generic person detector lacks.
ByteTrack is the baseline; BoT-SORT remains optional. Team grouping uses appearance
heuristics, not verified team identity or jersey-number recognition. The exported
`team_confidence` value is a color-separation margin, not a calibrated probability.
Goalkeeper assignment and uncertain tracks require analyst review.

Camera compensation is an accumulated affine approximation. It can drift under
perspective changes; it is not a full field-line camera calibration system. Foot
markers use box bottoms, not measured foot keypoints. Formation templates are manual
tactical references; the calibrated board projects tracks and does not infer a
formation label. Ball proximity is not measured possession.

At the time of the earlier review, the three-second sample supplied the inference evidence:
37 analyzed frames, 20 tracks grouped into two kit groups, and about 69 seconds on CPU.
It is not ground-truth accuracy evidence. This review did not retrain weights, measure
mAP/HOTA/IDF1, establish the best competing model, certify GPU compatibility, or run
a new full-match browser benchmark. Those claims require appropriate data and hardware.

The 1 November review recorded ten Python regression tests, JavaScript camera/import
checks, the failed-video-import regression, and a model provenance/independence
audit as passing at that time. Those results predate this working-tree follow-up
and do not establish its pass status. No physical pitch dimensions, metric speeds,
or distances were introduced. Ask the user for verified physical measurements
before adding those features.

## Player stability follow-up

See **STABILITY.md** for the current defaults, corrected 15-sample MATCH1 review,
repeated-display-frame ring repair, and remaining identity limits. The current
source inventory contains 31 Python test methods and five JavaScript check scripts;
this follow-up has not run them. Provisional identity-review counts that included
uncertain later winger samples have been superseded.
