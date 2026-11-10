# Tactical patterns: first integration report

Implemented 10 November 2026. This adds a local, configurable pattern workflow
inspired by [Codeball](https://github.com/metrica-sports/codeball)'s documented
Pattern concept: define a question, produce candidate events, and review the video.
This is an original Touchline implementation, not a Codeball installation or a
Codeball-compatible data adapter. No Codeball source was copied or vendored, no new
dependencies were installed, and no Git remote was added. Existing model provenance,
checkpoint restrictions, tracking settings, and manual correction controls remain.

## Use it

1. Import or re-link your video and analyze its tracking.
2. Calibrate the pitch using the existing four-corner control. Review alignment.
3. Open **Tactical patterns > Configure zone & search**, below player connections.
4. Name the pattern; select all players, Home, Away, or a track ID. Set the rectangle
   using percentages of the normalized pitch map and optionally a minimum duration.
   The preview shows the selected zone. These are not physical measurements. The
   default right-hand half is a geometric example, not an attacking-half designation.
5. Search and use **Review video** to seek to each candidate's first inside sample.
   Choose unreviewed, keep, or dismiss; edit your interpretation and save it as a note.
6. Notes appear in the existing Interpretation panel and are included in Save project.
   Save settings also stores the configuration in the project. Export/import a
   template to reuse the settings in another project; check its team and track ID.
7. Export reviewed results to keep the candidate list, review statuses, interpretations,
   zone configuration, source filename, calibration, and algorithm version as JSON.

Search results and review statuses are temporary: they do not survive a reload or
another search. Save notes and export results before leaving. Exported result JSON
is an analysis record, not a project or importable tracking file. Dismiss marks a
candidate; it does not delete a note you already saved. Changing a candidate's text
does not update its saved note until you press Update saved note.

## What the results mean

- An observed entry requires consecutive usable samples of the same track, outside
  then inside the zone. Its crossing lies between those two timestamps; it is not
  an exact crossing time. The review button seeks to the inside sample.
- A first sighting inside the zone is a visit with an unconfirmed entry. It is not
  counted as an observed entry. A single inside sample has zero observed duration.
- Duration is the span between consecutive inside samples, not an extrapolation
  to an entry/exit boundary. Sampling can miss short exits and re-entries.
- Missing players, invalid/out-of-pitch projections, camera scene changes, and time
  gaps break visits. Adjacent gaps must be at most 1.5 times the nominal sample
  period, capped at 0.5 seconds. No connection interpolation or ball interpolation
  contributes to results. Sparse sampling can therefore produce only zero-duration
  sightings rather than unjustified occupancy estimates.
- Only the calibrated camera scene is searched. Valid camera matrices are required
  even for legacy imports. Other scenes are skipped, and missing camera metadata
  requires tracking again. Camera matrices do not prove alignment: drift still needs
  manual visual review. A valid-looking but inaccurate calibration can produce wrong
  candidates. No automatic calibration-quality score is claimed.
- Team exclusions, names, foot-offset corrections, and manual overlap overrides are
  respected. The same duplicate filter used by overlays is applied. Referees are
  excluded; goalkeepers can match all-player or assigned-team searches. Unassigned
  players only match all-player or explicit track-ID searches.
- Results are bound to their source tracks, calibration, and player corrections.
  If these change, review actions and export require a new search. Form edits do not
  rewrite old results; their original configuration is retained in the export.
- Searches retain at most 2,000 completed visits and explicitly report truncation.
  Filter by player/team or raise the minimum duration to narrow the results.
- Zone directions follow the calibration, not possession or attacking direction.
  Video-zone drawings remain independent. There are no meters, speeds, inferred
  passes, inferred possession, pitch-control scores, or automatic tactical conclusions.

## Implementation and verification

`dist/patterns.js` supplies validated configuration and a DOM-independent scanner.
`dist/patterns-ui.js` supplies search, cancellation, templates, review, and export.
`patternProjector` in `dist/football-features.js` maps each sample with its own
camera transform and the calibrated video's letterbox geometry; it does not move
the playback clock. `dist/app.js` connects saved settings, corrections, and notes.
Old projects load with defaults. New browser scripts are packaged with the app.

Validation: 58 Python regression tests passed; all 10 JavaScript test scripts passed,
including the existing projection suite and two new pattern suites. New checks cover
entry uncertainty, gaps/cuts/identity changes, duration, filters, limits, projection,
manual offsets, project compatibility, seeking, note updates, stale results, exports,
and cancellation. UI checks use a simulated DOM. Browser visual verification was
attempted but blocked because Computer Use could not confidently identify the current
browser URL. No real-match pattern accuracy benchmark has been performed.

## Best next improvements

1. Review candidates on a short, manually labeled match segment and measure entry
   precision/recall and timing error before adding more pattern types.
2. Add saved calibration segments and explicit alignment review so a search can
   cover multiple shots without treating unknown camera geometry as valid.
3. Add persistent reviewed event records with source revisions and stable identities;
   then support drawing zones on the pitch preview and several named patterns.
4. Add manually confirmed football events before attempting pass/possession patterns.
   A future actual Codeball adapter would require its own schema and dependency tests.

Conceptual reference: [Codeball README, Patterns section](https://github.com/metrica-sports/codeball#readme).
Codeball's source is MIT-licensed; this feature does not change ownership or licensing
of Codeball, Touchline's existing third-party code, or model weights.
