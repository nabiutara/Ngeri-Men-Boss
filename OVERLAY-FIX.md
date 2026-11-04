# Foot rings and editable labels — November 1, 2026

## Observed cause

MATCH1 contains simultaneous full-body and torso-only detections of one player.
The old overlay filter required nearly identical foot coordinates and protected
different automatic kit groups. Torso detections end near the knees, so they got a
second ring; some also had an incorrect team group. Filtering only the ring left
duplicate labels and selection targets in place.

The following model-output pairs were visually checked against MATCH1:

| Time (seconds) | Track IDs | Reviewed observation |
| --- | --- | --- |
| 0.033158 | 13, 15 | Full body and shorter torso of the same maroon player |
| 1.359483 | 17, 22 | Full body and torso of the same blue player |
| 3.680552 | 17, 39 | Full body and torso of the same maroon player |
| 5.338458 | 61, 63 | Overlapping boxes on the same maroon player |
| 6.731099 | 4, 73 | Two boxes on the goalkeeper |
| 6.996364 | 37, 88 | Full body and torso of the same blue player |

The repeated ID 17 on different players illustrates a separate identity-switch
problem. This presentation repair does not repair the model's historical IDs.

## Implemented behavior

- Deduplicate repeated IDs, then prefer the larger body box for nested duplicate
  detections. Require aligned horizontal centers, at least 95% containment of the
  smaller box, a shorter body height and matching head or foot edges. Limit bottom
  displacement to 35% of body height. Automatic kit disagreement cannot veto this
  specific nested-body check.
- For non-nested duplicates, require IoU at least 0.65, aligned centers and close
  feet. Keep different known kit groups separate in this branch.
- Use one filtered player list for rings, labels, hit testing and formation view.
  Saved detections are never deleted. The player picker still lists filtered tracks.
- Allow a per-track **Keep visible during overlaps** override for ambiguous real
  overlapping players. Existing **Exclude** remains available for false tracks.
- Draw three rotating segments on one ellipse, with a rear leg gap and soft glow.
  Rotation follows video time; repeated times hold position. Pauses and seeks snap
  to current detections. Cap the marker radius using player width to avoid oversized
  rings on distant players.
- Put the player picker and label textbox directly below the video. Selection
  pauses playback. Typing updates and saves immediately, with one undo snapshot per
  editing session. Names and overlap overrides survive project save/import. A blank
  label displays the track number. User text is drawn as text, never interpreted as HTML.

## Recorded verification and limits

The initial overlay/label review on 1 November recorded the checks below. The
current working tree includes later engine and UI edits; those changes have not
been re-run through these checks in this review.

The six reviewed pairs all reduce to one marker in regression tests. Tests also
cover separate nearby players, opposing kits, manual overrides, repeated timestamps,
pause/seek/cut resets, rendering repeated rows once and three arcs at one radius.
Label tests cover immediate autosave, undo grouping, blank values and project
round-trips. Projection and rejected-video-import checks were also recorded as
passing in the initial review.

In the local browser, MATCH1 at 0.033 seconds shows track 15 filtered behind track
13; at 1.36 seconds track 22 is filtered behind track 17. A custom "Playmaker" label
was typed into track 13, immediately displayed, then verified in the actual exported
MATCH1 project JSON. These checks do not constitute full-match accuracy measurement.

Two real players can overlap almost completely. Geometry cannot always determine
identity, and detection bottom centers are not ankle keypoints. Use the override if
a legitimate player is suppressed. This patch does not retrain or replace weights,
merge saved IDs, infer player names, or introduce physical pitch measurements.

Reload the browser to load the current cache-busted assets (version 2.8). Existing
saved tracking works with this presentation repair; no new video analysis is
required. Keep the original video available for relinking after a page reload.
