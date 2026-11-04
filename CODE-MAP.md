# Code navigation map

Generated from current source declarations. Read SOURCE-GUIDE.md for provenance and behavior.

## server.py

| Line | Declaration | Kind |
| --- | --- | --- |
| [44](server.py#L44) | `dependencies_ready` | function |
| [48](server.py#L48) | `training_workflow` | function |
| [57](server.py#L57) | `update_job` | function |
| [62](server.py#L62) | `track_video` | function |
| [72](server.py#L72) | `process_job` | function |
| [95](server.py#L95) | `Handler` | class |
| [96](server.py#L96) | `Handler.__init__` | function |
| [99](server.py#L99) | `Handler.log_message` | function |
| [103](server.py#L103) | `Handler.json_response` | function |
| [113](server.py#L113) | `Handler.valid_request` | function |
| [131](server.py#L131) | `Handler.do_GET` | function |
| [189](server.py#L189) | `Handler.list_directory` | function |
| [193](server.py#L193) | `Handler.do_POST` | function |
| [280](server.py#L280) | `Handler.do_DELETE` | function |
| [311](server.py#L311) | `main` | function |

## launch.py

| Line | Declaration | Kind |
| --- | --- | --- |
| [17](launch.py#L17) | `health` | function |
| [28](launch.py#L28) | `main` | function |

## benchmark.py

| Line | Declaration | Kind |
| --- | --- | --- |
| [26](benchmark.py#L26) | `digest` | function |
| [31](benchmark.py#L31) | `write_report` | function |
| [52](benchmark.py#L52) | `review_packet` | function |
| [78](benchmark.py#L78) | `main` | function |

## evaluation.py

| Line | Declaration | Kind |
| --- | --- | --- |
| [12](evaluation.py#L12) | `box_iou` | function |
| [21](evaluation.py#L21) | `predicted_objects` | function |
| [36](evaluation.py#L36) | `validate_ground_truth` | function |
| [78](evaluation.py#L78) | `match_objects` | function |
| [91](evaluation.py#L91) | `score_ground_truth` | function |
| [161](evaluation.py#L161) | `diagnostics` | function |

## prepare_training.py

| Line | Declaration | Kind |
| --- | --- | --- |
| [14](prepare_training.py#L14) | `validate_plan` | function |
| [39](prepare_training.py#L39) | `export_dataset` | function |
| [108](prepare_training.py#L108) | `main` | function |

## football_engine.py

| Line | Declaration | Kind |
| --- | --- | --- |
| [26](football_engine.py#L26) | `resolve_model` | function |
| [56](football_engine.py#L56) | `role_for` | function |
| [63](football_engine.py#L63) | `jersey_color` | function |
| [103](football_engine.py#L103) | `TeamColors` | class |
| [104](football_engine.py#L104) | `TeamColors.__init__` | function |
| [107](football_engine.py#L107) | `TeamColors.add` | function |
| [111](football_engine.py#L111) | `TeamColors.fit` | function |
| [170](football_engine.py#L170) | `distinct_people` | function |
| [184](football_engine.py#L184) | `CameraMotion` | class |
| [190](football_engine.py#L190) | `CameraMotion.__init__` | function |
| [196](football_engine.py#L196) | `CameraMotion.update` | function |
| [260](football_engine.py#L260) | `BallHistory` | class |
| [262](football_engine.py#L262) | `BallHistory.__init__` | function |
| [266](football_engine.py#L266) | `BallHistory.choose` | function |
| [283](football_engine.py#L283) | `bounded_ball_fill` | function |
| [300](football_engine.py#L300) | `track_football` | function |
| [310](football_engine.py#L310) | `track_football.check_cancel` | function |
| [413](football_engine.py#L413) | `track_football.emit` | function |

## build_package.py

| Line | Declaration | Kind |
| --- | --- | --- |
| [30](build_package.py#L30) | `main` | function |

## tests/test_football_engine.py

| Line | Declaration | Kind |
| --- | --- | --- |
| [17](tests/test_football_engine.py#L17) | `FootballTests` | class |
| [18](tests/test_football_engine.py#L18) | `FootballTests.test_person_duplicates_keep_roles_aligned_without_merging_neighbors` | function |
| [24](tests/test_football_engine.py#L24) | `FootballTests.test_identity_survives_pan_and_gap_but_resets_on_cut` | function |
| [30](tests/test_football_engine.py#L30) | `FootballTests.test_identity_survives_pan_and_gap_but_resets_on_cut.FakeModel` | class |
| [32](tests/test_football_engine.py#L32) | `FootballTests.test_identity_survives_pan_and_gap_but_resets_on_cut.FakeModel.predict` | function |
| [58](tests/test_football_engine.py#L58) | `FootballTests.test_jersey_colors_and_outliers` | function |
| [77](tests/test_football_engine.py#L77) | `FootballTests.test_no_forced_teams_when_evidence_is_insufficient` | function |
| [84](tests/test_football_engine.py#L84) | `FootballTests.test_green_kit_is_not_discarded_as_grass` | function |
| [89](tests/test_football_engine.py#L89) | `FootballTests.test_camera_pan_compensation_and_cut` | function |
| [104](tests/test_football_engine.py#L104) | `FootballTests.test_featureless_frames_do_not_crash` | function |
| [110](tests/test_football_engine.py#L110) | `FootballTests.test_ball_gap_is_bounded_and_does_not_cross_cut` | function |
| [125](tests/test_football_engine.py#L125) | `FootballTests.test_ball_selection_does_not_jump_to_distant_false_positive` | function |
| [132](tests/test_football_engine.py#L132) | `FootballTests.test_class_mapping` | function |
| [137](tests/test_football_engine.py#L137) | `FootballTests.test_large_identity_count_uses_bounded_fit` | function |
| [144](tests/test_football_engine.py#L144) | `FootballTests.test_large_identity_count_uses_bounded_fit.record_size` | function |
| [152](tests/test_football_engine.py#L152) | `FootballTests.test_empty_video_results_and_cancellation_cleanup` | function |
| [160](tests/test_football_engine.py#L160) | `FootballTests.test_empty_video_results_and_cancellation_cleanup.FakeModel` | class |
| [162](tests/test_football_engine.py#L162) | `FootballTests.test_empty_video_results_and_cancellation_cleanup.FakeModel.predict` | function |
| [175](tests/test_football_engine.py#L175) | `FootballTests.test_empty_video_results_and_cancellation_cleanup.progress` | function |
| [185](tests/test_football_engine.py#L185) | `FootballTests.test_tracker_row_shapes_handled_defensively` | function |
| [193](tests/test_football_engine.py#L193) | `FootballTests.test_tracker_row_shapes_handled_defensively.FakeModel` | class |
| [195](tests/test_football_engine.py#L195) | `FootballTests.test_tracker_row_shapes_handled_defensively.FakeModel.predict` | function |
| [198](tests/test_football_engine.py#L198) | `FootballTests.test_tracker_row_shapes_handled_defensively.VariedTracker` | class |
| [199](tests/test_football_engine.py#L199) | `FootballTests.test_tracker_row_shapes_handled_defensively.VariedTracker.__init__` | function |
| [200](tests/test_football_engine.py#L200) | `FootballTests.test_tracker_row_shapes_handled_defensively.VariedTracker.reset` | function |
| [201](tests/test_football_engine.py#L201) | `FootballTests.test_tracker_row_shapes_handled_defensively.VariedTracker.update` | function |
| [213](tests/test_football_engine.py#L213) | `FootballTests.test_camera_motion_drift_reset_on_extreme_matrix_scale` | function |
| [228](tests/test_football_engine.py#L228) | `FootballTests.test_ball_history_time_adaptive_radius` | function |

## tests/test_evaluation.py

| Line | Declaration | Kind |
| --- | --- | --- |
| [10](tests/test_evaluation.py#L10) | `fixture` | function |
| [18](tests/test_evaluation.py#L18) | `EvaluationTests` | class |
| [19](tests/test_evaluation.py#L19) | `EvaluationTests.test_perfect_localization_and_identity` | function |
| [28](tests/test_evaluation.py#L28) | `EvaluationTests.test_missed_and_false_detections` | function |
| [37](tests/test_evaluation.py#L37) | `EvaluationTests.test_switches_are_not_counted_across_camera_resets` | function |
| [44](tests/test_evaluation.py#L44) | `EvaluationTests.test_review_and_source_guards` | function |
| [53](tests/test_evaluation.py#L53) | `EvaluationTests.test_assignment_is_one_to_one_and_role_accuracy_separate` | function |
| [62](tests/test_evaluation.py#L62) | `EvaluationTests.test_interpolated_ball_is_not_scored_as_observed` | function |
| [71](tests/test_evaluation.py#L71) | `EvaluationTests.test_timing_mismatch_is_rejected` | function |
| [78](tests/test_evaluation.py#L78) | `EvaluationTests.test_unprocessed_midpoint_timestamp_is_rejected` | function |
| [85](tests/test_evaluation.py#L85) | `EvaluationTests.test_invalid_labels_are_rejected` | function |

## tests/test_training_export.py

| Line | Declaration | Kind |
| --- | --- | --- |
| [15](tests/test_training_export.py#L15) | `TrainingExportTests` | class |
| [16](tests/test_training_export.py#L16) | `TrainingExportTests.test_match_leakage_is_rejected` | function |
| [20](tests/test_training_export.py#L20) | `TrainingExportTests.test_missing_validation_group_is_rejected` | function |
| [23](tests/test_training_export.py#L23) | `TrainingExportTests.test_reviewed_export_preserves_classes_and_source_groups` | function |

## dist/app.js

| Line | Declaration | Kind |
| --- | --- | --- |
| [6](dist/app.js#L6) | `icon` | function |
| [7](dist/app.js#L7) | `decorate` | function |
| [22](dist/app.js#L22) | `storeTracks` | function |
| [23](dist/app.js#L23) | `autosave` | function |
| [25](dist/app.js#L25) | `toast` | function |
| [26](dist/app.js#L26) | `modal` | function |
| [28](dist/app.js#L28) | `checkpoint` | function |
| [29](dist/app.js#L29) | `undo` | function |
| [30](dist/app.js#L30) | `playerInfo` | function |
| [31](dist/app.js#L31) | `overlayColor` | function |
| [32](dist/app.js#L32) | `teamColor` | function |
| [33](dist/app.js#L33) | `playerEdit` | function |
| [34](dist/app.js#L34) | `drawRounded` | function |
| [35](dist/app.js#L35) | `setPlaying` | function |
| [36](dist/app.js#L36) | `updatePlay` | function |
| [37](dist/app.js#L37) | `seek` | function |
| [38](dist/app.js#L38) | `updateTime` | function |
| [39](dist/app.js#L39) | `setTool` | function |
| [41](dist/app.js#L41) | `fieldPoint` | function |
| [42](dist/app.js#L42) | `fieldPath` | function |
| [43](dist/app.js#L43) | `drawPitch` | function |
| [56](dist/app.js#L56) | `demoPlayers` | function |
| [57](dist/app.js#L57) | `frameIndex` | function |
| [58](dist/app.js#L58) | `playersAt` | function |
| [59](dist/app.js#L59) | `contentRect` | function |
| [60](dist/app.js#L60) | `screenPlayer` | function |
| [61](dist/app.js#L61) | `render` | function |
| [77](dist/app.js#L77) | `drawAthlete` | function |
| [78](dist/app.js#L78) | `annotationBounds` | function |
| [79](dist/app.js#L79) | `wrapLines` | function |
| [80](dist/app.js#L80) | `drawAnnotation` | function |
| [82](dist/app.js#L82) | `pointer` | function |
| [83](dist/app.js#L83) | `hitAnnotation` | function |
| [92](dist/app.js#L92) | `finishPointer` | function |
| [94](dist/app.js#L94) | `updateSelection` | function |
| [96](dist/app.js#L96) | `findSelectedPlayer` | function |
| [97](dist/app.js#L97) | `refreshPlayerPicker` | function |
| [131](dist/app.js#L131) | `initBoard` | function |
| [132](dist/app.js#L132) | `renderBoard` | function |
| [138](dist/app.js#L138) | `solveHomography` | function |
| [139](dist/app.js#L139) | `projectPoint` | function |
| [141](dist/app.js#L141) | `updateSettings` | function |
| [144](dist/app.js#L144) | `renderNotes` | function |
| [149](dist/app.js#L149) | `clearMedia` | function |
| [150](dist/app.js#L150) | `refreshClipUI` | function |
| [151](dist/app.js#L151) | `importVideo` | function |
| [163](dist/app.js#L163) | `finish` | function |
| [202](dist/app.js#L202) | `checkEngine` | function |
| [203](dist/app.js#L203) | `updateEngineStatus` | function |
| [204](dist/app.js#L204) | `runnerDialog` | function |
| [208](dist/app.js#L208) | `startAnalysis` | function |
| [250](dist/app.js#L250) | `pollAnalysis` | function |
| [252](dist/app.js#L252) | `validateTracking` | function |
| [253](dist/app.js#L253) | `loadTracking` | function |
| [255](dist/app.js#L255) | `download` | function |
| [256](dist/app.js#L256) | `saveProject` | function |
| [258](dist/app.js#L258) | `sanitizeProject` | function |
| [268](dist/app.js#L268) | `recordVideo` | function |
| [270](dist/app.js#L270) | `restore` | function |
| [278](dist/app.js#L278) | `mediaTimeAt` | function |
| [280](dist/app.js#L280) | `connectPlayer` | function |
| [291](dist/app.js#L291) | `drawPlayerConnections` | function |
| [305](dist/app.js#L305) | `tick` | function |

## dist/foot-markers.js

| Line | Declaration | Kind |
| --- | --- | --- |
| [8](dist/foot-markers.js#L8) | `begin` | function |
| [15](dist/foot-markers.js#L15) | `position` | function |
| [38](dist/foot-markers.js#L38) | `unique` | function |
| [77](dist/foot-markers.js#L77) | `draw` | function |
| [103](dist/foot-markers.js#L103) | `finish` | function |

## dist/football-features.js

| Line | Declaration | Kind |
| --- | --- | --- |
| [3](dist/football-features.js#L3) | `frameAt` | function |
| [4](dist/football-features.js#L4) | `validateCamera` | function |
| [5](dist/football-features.js#L5) | `determinant3` | function |
| [6](dist/football-features.js#L6) | `inverse3` | function |
| [7](dist/football-features.js#L7) | `transform3` | function |
| [8](dist/football-features.js#L8) | `trackingCameraAt` | function |
| [9](dist/football-features.js#L9) | `sameTrackingScene` | function |
| [10](dist/football-features.js#L10) | `calibrationUsable` | function |
| [11](dist/football-features.js#L11) | `calibratedPosition` | function |
| [12](dist/football-features.js#L12) | `drawBallMarker` | function |
| [13](dist/football-features.js#L13) | `bindFootballControls` | function |

## dist/player-connections.js

| Line | Declaration | Kind |
| --- | --- | --- |
| [3](dist/player-connections.js#L3) | `sanitize` | function |
| [7](dist/player-connections.js#L7) | `visible` | function |

## New JavaScript regression checks

| File | Coverage |
| --- | --- |
| `tests/test_player_connections.cjs` | Saved edge validation, anchor movement, missing tracks and scenes, connection editing, undo, persistence, and frame timestamps. |
| `tests/test_player_labels.cjs` | Label editing/autosave, grouped undo, blank names, overlap overrides, and project sanitization. |

## tests/test_football_ui.cjs

| Line | Declaration | Kind |
| --- | --- | --- |
| [8](tests/test_football_ui.cjs#L8) | `solveHomography` | function |
| [15](tests/test_football_ui.cjs#L15) | `frameIndex` | function |
| [16](tests/test_football_ui.cjs#L16) | `contentRect` | function |
| [24](tests/test_football_ui.cjs#L24) | `validateTracking` | function |
| [24](tests/test_football_ui.cjs#L24) | `loadTracking` | function |

## HTML, styles, and launcher

- `dist/index.html`: semantic sections, element IDs, labels, and script loading. Match each ID to its UI events above.
- `dist/styles.css`: CSS variables and responsive rules define the visual design.
- `Start Touchline.cmd`: executable launcher; read top to bottom for environment checks and server startup.
- `.run/*.run.xml`: PyCharm launch configurations; `.idea/` holds local IDE state.

## Optional private cloud deployment

| File | Responsibility |
| --- | --- |
| `cloud/functions/api/[[path]].js` | Verifies Cloudflare Access JWTs, creates signed R2 uploads, manages D1 job state, proxies authenticated Modal requests, and serves results/candidate downloads. |
| `cloud/modal_app.py` | Exposes the proxy-authenticated Modal API, queues GPU tracking, preserves the verified base checkpoint, writes result/candidate artifacts, and deletes raw uploads. |
| `cloud/pseudo_training.py` | Samples confident, temporally stable predictions into sparse YOLO labels and records source/model provenance. |
| `cloud/migrations/0001_create_jobs.sql` | Creates the D1 job table, including candidate artifact and training status fields. |
| `tests/test_cloud_pseudo_training.py` | Checks sparse sample creation, class mapping, provenance, and rejection of one-frame tracks. |
| `tests/test_cloud_client.cjs` | Checks the browser's signed-upload and job-submission sequence. |

Cloud candidates are trained for one epoch from the original verified teacher and
retained pseudo-label samples. No candidate is automatically activated or described
as an improvement without a separate reviewed benchmark. Deployment steps and
provider configuration are in `cloud/DEPLOY.md`; the portable desktop ZIP remains
separate from those cloud resources.

## training_workflow.py

| Line | Declaration | Kind |
| --- | --- | --- |
| [28](training_workflow.py#L28) | `digest` | function |
| [33](training_workflow.py#L33) | `write_json` | function |
| [39](training_workflow.py#L39) | `TrainingWorkflow` | class |
| [40](training_workflow.py#L40) | `TrainingWorkflow.__init__` | function |
| [55](training_workflow.py#L55) | `TrainingWorkflow.records` | function |
| [83](training_workflow.py#L83) | `TrainingWorkflow.running` | function |
| [87](training_workflow.py#L87) | `TrainingWorkflow.summary` | function |
| [107](training_workflow.py#L107) | `TrainingWorkflow.save_frame` | function |
| [166](training_workflow.py#L166) | `TrainingWorkflow.reviewed_palette` | function |
| [183](training_workflow.py#L183) | `TrainingWorkflow.delete_frame` | function |
| [193](training_workflow.py#L193) | `TrainingWorkflow.build_dataset` | function |
| [227](training_workflow.py#L227) | `TrainingWorkflow.update` | function |
| [231](training_workflow.py#L231) | `TrainingWorkflow.start` | function |
| [246](training_workflow.py#L246) | `TrainingWorkflow._train` | function |
| [264](training_workflow.py#L264) | `TrainingWorkflow._train.check` | function |
| [267](training_workflow.py#L267) | `TrainingWorkflow._train.validation_metrics` | function |
| [279](training_workflow.py#L279) | `TrainingWorkflow._train.report` | function |
| [311](training_workflow.py#L311) | `TrainingWorkflow.artifact` | function |

## tests/test_cloud_pseudo_training.py

| Line | Declaration | Kind |
| --- | --- | --- |
| [14](tests/test_cloud_pseudo_training.py#L14) | `PseudoTrainingTests` | class |
| [15](tests/test_cloud_pseudo_training.py#L15) | `PseudoTrainingTests._video_and_result` | function |
| [41](tests/test_cloud_pseudo_training.py#L41) | `PseudoTrainingTests.test_writes_sparse_confident_pseudolabels_and_provenance` | function |
| [70](tests/test_cloud_pseudo_training.py#L70) | `PseudoTrainingTests.test_single_frame_tracks_are_not_treated_as_labels` | function |
| [78](tests/test_cloud_pseudo_training.py#L78) | `PseudoTrainingTests.test_rejects_class_map_mismatch` | function |
| [86](tests/test_cloud_pseudo_training.py#L86) | `PseudoTrainingTests.test_rejects_changed_class_order` | function |
| [94](tests/test_cloud_pseudo_training.py#L94) | `PseudoTrainingTests.test_training_sample_cap_balances_sources` | function |

## tests/test_launch.py

| Line | Declaration | Kind |
| --- | --- | --- |
| [12](tests/test_launch.py#L12) | `LauncherTests` | class |
| [13](tests/test_launch.py#L13) | `LauncherTests.test_ready_server_is_supervised_until_it_exits` | function |
| [21](tests/test_launch.py#L21) | `LauncherTests.test_existing_server_is_reused` | function |
| [26](tests/test_launch.py#L26) | `LauncherTests.test_foreign_port_is_not_killed_or_replaced` | function |
| [32](tests/test_launch.py#L32) | `LauncherTests.test_dead_child_reports_failure_without_opening_browser` | function |

## tests/test_training_api.py

| Line | Declaration | Kind |
| --- | --- | --- |
| [15](tests/test_training_api.py#L15) | `ReviewedTrainingAPITests` | class |
| [16](tests/test_training_api.py#L16) | `ReviewedTrainingAPITests.setUp` | function |
| [31](tests/test_training_api.py#L31) | `ReviewedTrainingAPITests.request` | function |
| [43](tests/test_training_api.py#L43) | `ReviewedTrainingAPITests.test_review_upload_status_and_delete_round_trip` | function |
| [57](tests/test_training_api.py#L57) | `ReviewedTrainingAPITests.test_host_origin_and_review_confirmation_are_enforced` | function |
| [67](tests/test_training_api.py#L67) | `ReviewedTrainingAPITests.test_training_and_artifacts_are_unavailable_without_reviewed_data` | function |

## tests/test_training_workflow.py

| Line | Declaration | Kind |
| --- | --- | --- |
| [17](tests/test_training_workflow.py#L17) | `packet` | function |
| [28](tests/test_training_workflow.py#L28) | `ReviewedTrainingTests` | class |
| [29](tests/test_training_workflow.py#L29) | `ReviewedTrainingTests.setUp` | function |
| [35](tests/test_training_workflow.py#L35) | `ReviewedTrainingTests.test_review_and_image_identity_are_required` | function |
| [44](tests/test_training_workflow.py#L44) | `ReviewedTrainingTests.test_match_and_content_leakage_are_rejected` | function |
| [50](tests/test_training_workflow.py#L50) | `ReviewedTrainingTests.test_complete_snapshot_preserves_roles_backgrounds_and_labels` | function |
| [67](tests/test_training_workflow.py#L67) | `ReviewedTrainingTests.test_training_requires_class_coverage_and_valid_settings` | function |
| [75](tests/test_training_workflow.py#L75) | `ReviewedTrainingTests.test_palette_uses_distinct_reviewed_outfield_identities` | function |
| [93](tests/test_training_workflow.py#L93) | `ReviewedTrainingTests.test_candidate_uses_best_and_keeps_the_active_checkpoint` | function |
| [99](tests/test_training_workflow.py#L99) | `ReviewedTrainingTests.test_candidate_uses_best_and_keeps_the_active_checkpoint.Model` | class |
| [101](tests/test_training_workflow.py#L101) | `ReviewedTrainingTests.test_candidate_uses_best_and_keeps_the_active_checkpoint.Model.__init__` | function |
| [102](tests/test_training_workflow.py#L102) | `ReviewedTrainingTests.test_candidate_uses_best_and_keeps_the_active_checkpoint.Model.add_callback` | function |
| [103](tests/test_training_workflow.py#L103) | `ReviewedTrainingTests.test_candidate_uses_best_and_keeps_the_active_checkpoint.Model.val` | function |
| [104](tests/test_training_workflow.py#L104) | `ReviewedTrainingTests.test_candidate_uses_best_and_keeps_the_active_checkpoint.Model.val.Result` | class |
| [106](tests/test_training_workflow.py#L106) | `ReviewedTrainingTests.test_candidate_uses_best_and_keeps_the_active_checkpoint.Model.train` | function |

## dist/frame-review.js

| Line | Declaration | Kind |
| --- | --- | --- |
| [14](dist/frame-review.js#L14) | `hashFile` | function |
| [16](dist/frame-review.js#L16) | `proposals` | function |
| [17](dist/frame-review.js#L17) | `nearest` | function |
| [18](dist/frame-review.js#L18) | `validateFrame` | function |
| [19](dist/frame-review.js#L19) | `validateDocument` | function |
| [20](dist/frame-review.js#L20) | `invalidate` | function |
| [21](dist/frame-review.js#L21) | `reviewedDocument` | function |
| [22](dist/frame-review.js#L22) | `color` | function |

## dist/frame-review-ui.js

| Line | Declaration | Kind |
| --- | --- | --- |
| [4](dist/frame-review-ui.js#L4) | `mount` | function |
| [21](dist/frame-review-ui.js#L21) | `persist` | function |
| [22](dist/frame-review-ui.js#L22) | `saveSoon` | function |
| [23](dist/frame-review-ui.js#L23) | `listFrames` | function |
| [24](dist/frame-review-ui.js#L24) | `change` | function |
| [25](dist/frame-review-ui.js#L25) | `remember` | function |
| [26](dist/frame-review-ui.js#L26) | `object` | function |
| [27](dist/frame-review-ui.js#L27) | `fields` | function |
| [28](dist/frame-review-ui.js#L28) | `render` | function |
| [29](dist/frame-review-ui.js#L29) | `waitFor` | function |
| [30](dist/frame-review-ui.js#L30) | `capture` | function |
| [34](dist/frame-review-ui.js#L34) | `finish` | function |
| [52](dist/frame-review-ui.js#L52) | `refreshTraining` | function |
| [54](dist/frame-review-ui.js#L54) | `close` | function |
| [56](dist/frame-review-ui.js#L56) | `open` | function |
