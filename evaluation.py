"""Ground-truth scoring and clearly separated, unlabeled tracking diagnostics."""
from bisect import bisect_left
from collections import Counter, defaultdict
import math

import lap
import numpy as np

ROLES = {'player', 'goalkeeper', 'referee', 'ball'}


def box_iou(a, b):
    left, top = max(a[0], b[0]), max(a[1], b[1])
    right, bottom = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0., right-left) * max(0., bottom-top)
    area_a = (a[2]-a[0]) * (a[3]-a[1])
    area_b = (b[2]-b[0]) * (b[3]-b[1])
    return intersection / max(area_a+area_b-intersection, 1e-12)


def predicted_objects(frame):
    objects = []
    for player in frame['players']:
        x, y, w, h = (player[key] for key in ('x', 'y', 'w', 'h'))
        objects.append({'id': player['id'], 'role': player.get('role', 'player'),
                        'team': player.get('team', 'neutral'),
                        'bbox': [x-w/2, y-h, x+w/2, y]})
    ball = frame.get('ball')
    if ball and ball.get('observed'):
        x, y, w, h = (ball[key] for key in ('x', 'y', 'w', 'h'))
        objects.append({'id': None, 'role': 'ball', 'team': 'neutral',
                        'bbox': [x-w/2, y-h/2, x+w/2, y+h/2]})
    return objects


def validate_ground_truth(data, source_sha256):
    if not isinstance(data, dict) or data.get('schema') != 'touchline-groundtruth-v1':
        raise ValueError('Unsupported ground-truth schema')
    if data.get('source_sha256') != source_sha256:
        raise ValueError('Ground truth belongs to a different video')
    frames = data.get('frames')
    if not isinstance(frames, list) or not frames:
        raise ValueError('Ground truth needs reviewed frames')
    last_time = -1.
    for frame in frames:
        if not isinstance(frame, dict):
            raise ValueError('Every ground-truth frame must be an object')
        timestamp = frame.get('t')
        if not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp) or timestamp <= last_time:
            raise ValueError('Ground-truth timestamps must be finite, increasing, and nonnegative')
        if timestamp < 0:
            raise ValueError('Ground-truth timestamps must be nonnegative')
        last_time = timestamp
        if frame.get('reviewed') is not True or frame.get('fully_annotated') is not True:
            raise ValueError('Every scored frame must be manually reviewed and fully annotated')
        objects = frame.get('objects')
        if not isinstance(objects, list) or len(objects) > 300:
            raise ValueError('Invalid ground-truth object list')
        ids = set()
        for obj in objects:
            if not isinstance(obj, dict):
                raise ValueError('Every labeled object must be an object')
            box = obj.get('bbox', [])
            if obj.get('role') not in ROLES or len(box) != 4 or not all(isinstance(v, (int, float)) and math.isfinite(v) and 0 <= v <= 1 for v in box):
                raise ValueError('Invalid role or normalized xyxy box')
            if box[2] <= box[0] or box[3] <= box[1]:
                raise ValueError('Ground-truth boxes must have positive area')
            identity = obj.get('id')
            if obj['role'] != 'ball':
                if not isinstance(identity, int) or isinstance(identity, bool) or identity < 0 or identity in ids:
                    raise ValueError('Person identities must be unique nonnegative integers within each frame')
                ids.add(identity)
            if obj.get('team', 'neutral') not in {'home', 'away', 'neutral'}:
                raise ValueError('Invalid ground-truth team')
    return data


def match_objects(truth, predictions, threshold):
    if not truth or not predictions:
        return []
    cost = np.full((len(truth), len(predictions)), 2., dtype=np.float64)
    for i, target in enumerate(truth):
        for j, prediction in enumerate(predictions):
            # Person localization and role classification are scored separately.
            if (target['role'] == 'ball') == (prediction['role'] == 'ball'):
                cost[i, j] = 1-box_iou(target['bbox'], prediction['bbox'])
    _, assignment, _ = lap.lapjv(cost, extend_cost=True, cost_limit=1-threshold+1e-9)
    return [(i, int(j), 1-cost[i, j]) for i, j in enumerate(assignment) if j >= 0 and cost[i, j] <= 1-threshold+1e-9]


def score_ground_truth(predictions, truth, source_sha256, iou_threshold=.5):
    """Sampled-frame localization and identities; intentionally not mAP/HOTA/IDF1."""
    validate_ground_truth(truth, source_sha256)
    if not 0 < iou_threshold <= 1:
        raise ValueError('IoU threshold must lie in (0, 1]')
    frames = predictions['frames']
    times = [frame['t'] for frame in frames]
    # Review templates copy the processed timestamp exactly. A half-stride
    # tolerance can silently score a label against an adjacent sampled frame.
    tolerance = 1e-5
    counts = {role: Counter(tp=0, fp=0, fn=0) for role in ('persons', 'ball')}
    identity_history = {}
    ious, foot_errors = [], []
    switches, role_correct, role_total, identity_pairs = 0, 0, 0, 0
    team_pairs = []
    used_predictions = set()
    for annotated in truth['frames']:
        position = bisect_left(times, annotated['t'])
        candidates = [i for i in (position-1, position) if 0 <= i < len(times)]
        if not candidates:
            raise ValueError('Ground truth has no corresponding prediction frame')
        index = min(candidates, key=lambda i: abs(times[i]-annotated['t']))
        if abs(times[index]-annotated['t']) > tolerance or index in used_predictions:
            raise ValueError('Labels must align to distinct processed prediction timestamps')
        used_predictions.add(index)
        frame = frames[index]
        detected = predicted_objects(frame)
        matches = match_objects(annotated['objects'], detected, iou_threshold)
        matched_truth = {i for i, _, _ in matches}
        matched_pred = {j for _, j, _ in matches}
        for i, obj in enumerate(annotated['objects']):
            group = 'ball' if obj['role'] == 'ball' else 'persons'
            counts[group]['tp' if i in matched_truth else 'fn'] += 1
        for j, obj in enumerate(detected):
            if j not in matched_pred:
                counts['ball' if obj['role'] == 'ball' else 'persons']['fp'] += 1
        for i, j, overlap in matches:
            target, prediction = annotated['objects'][i], detected[j]
            ious.append(overlap)
            role_total += 1
            role_correct += target['role'] == prediction['role']
            if target['role'] == 'ball':
                continue
            a, b = target['bbox'], prediction['bbox']
            foot_errors.append(math.hypot(((a[0]+a[2]-b[0]-b[2])/2)*predictions['width'], (a[3]-b[3])*predictions['height']))
            scene = frame.get('camera', {}).get('scene', 0)
            key = (scene, target['id'])
            previous = identity_history.get(key)
            if previous is not None:
                identity_pairs += 1
                switches += previous != prediction['id']
            identity_history[key] = prediction['id']
            if target.get('team') in {'home', 'away'}:
                team_pairs.append((target['team'], prediction.get('team', 'neutral')))
    for value in counts.values():
        value['precision'] = value['tp']/(value['tp']+value['fp']) if value['tp']+value['fp'] else None
        value['recall'] = value['tp']/(value['tp']+value['fn']) if value['tp']+value['fn'] else None
    direct = sum(a == b for a, b in team_pairs)
    swapped = sum((a == 'home' and b == 'away') or (a == 'away' and b == 'home') for a, b in team_pairs)
    return {'status': 'scored-reviewed-labels', 'annotated_frames': len(truth['frames']),
            'iou_threshold': iou_threshold, 'localization': counts,
            'mean_matched_iou': float(np.mean(ious)) if ious else None,
            'role_accuracy_on_matches': role_correct/role_total if role_total else None,
            'sampled_identity_switches_within_scene': switches, 'identity_comparisons': identity_pairs,
            'team_accuracy_best_global_home_away_mapping': max(direct, swapped)/len(team_pairs) if team_pairs else None,
            'mean_bbox_bottom_error_pixels': float(np.mean(foot_errors)) if foot_errors else None,
            'p95_bbox_bottom_error_pixels': float(np.percentile(foot_errors,95)) if foot_errors else None,
            'limits': 'Scored only on reviewed sampled frames. Box-bottom error is not anatomical foot error. No mAP, HOTA, or IDF1 is computed.'}


def diagnostics(data):
    """Do not mistake observation counts for ground-truth accuracy."""
    observations = Counter()
    identities = defaultdict(set)
    frame_counts = []
    observed_ball = interpolated_ball = 0
    for frame in data['frames']:
        frame_counts.append(len(frame['players']))
        for player in frame['players']:
            role = player.get('role', 'player')
            observations[role] += 1
            identities[role].add(player['id'])
        ball = frame.get('ball')
        if ball:
            if ball.get('observed'): observed_ball += 1
            else: interpolated_ball += 1
    return {'status': 'unlabeled-diagnostics-only', 'processed_frames': len(data['frames']),
            'median_person_tracks_per_frame': float(np.median(frame_counts)) if frame_counts else 0,
            'role_observations': dict(observations), 'track_id_count_by_role': {k:len(v) for k,v in identities.items()},
            'observed_ball_frames': observed_ball, 'interpolated_ball_frames': interpolated_ball,
            'camera_reference_resets': data.get('camera_resets',0),
            'automatically_grouped_track_ids': len(data.get('team_assignments',{})),
            'limits': 'Counts may include false positives, missed players and identity fragmentation; they do not measure accuracy.'}
