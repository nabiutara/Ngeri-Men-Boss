"""Reviewed frame collection and isolated supervised football detector training.

The UI supplies reviewed JPEG frames, not retained full videos. Dataset snapshots
are grouped by match. Candidates never replace the checksum-verified runtime model.
"""
from __future__ import annotations

import base64
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import threading
import uuid

import cv2
import numpy as np

from evaluation import validate_ground_truth
from prepare_training import CLASSES


def digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def write_json(path, value):
    temporary = path.with_suffix('.partial')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


class TrainingWorkflow:
    def __init__(self, root, models):
        self.root, self.models = Path(root), Path(models)
        self.lock = threading.RLock()
        self.jobs = {}
        for path in sorted((self.root / 'runs').glob('*/candidate.json')):
            try:
                manifest = json.loads(path.read_text(encoding='utf-8'))
                job_id = manifest['id']
                if re.fullmatch('[a-f0-9]{32}', job_id):
                    self.jobs[job_id] = {'id': job_id, 'status': 'completed', 'progress': 100,
                                         'message': 'Inactive candidate saved', 'manifest': manifest,
                                         'cancel': threading.Event()}
            except (OSError, ValueError, KeyError):
                continue

    def records(self):
        records = []
        matches, sources, images = {}, {}, {}
        for path in sorted((self.root / 'frames').glob('*/review.json')):
            record = json.loads(path.read_text(encoding='utf-8'))
            sha, key, split, match = (record.get(name) for name in ('source_sha256', 'key', 'split', 'match_id'))
            if not isinstance(sha, str) or not re.fullmatch('[a-f0-9]{64}', sha):
                raise ValueError('Stored review has an invalid source identity')
            validate_ground_truth({'schema': 'touchline-groundtruth-v1', 'source_sha256': sha,
                                   'frames': [record.get('frame')]}, sha)
            if isinstance(record['frame']['t'], bool) or record['frame']['t'] >= 4 * 3600:
                raise ValueError('Stored review has invalid source timing')
            expected = f"{sha}-{round(record['frame']['t'] * 1_000_000):012d}"
            if key != expected or path.parent.name != expected or split not in {'train', 'val', 'test'}:
                raise ValueError('Stored review identity or split changed; review this frame again')
            if not isinstance(match, str) or not match.strip() or len(match) > 100:
                raise ValueError('Stored review needs a valid match ID')
            image_sha = record.get('image_sha256', '')
            if not isinstance(image_sha, str) or not re.fullmatch('[a-f0-9]{64}', image_sha):
                raise ValueError('Stored review needs its original JPEG checksum')
            for value, group, identity in ((match, matches, split), (sha, sources, (match, split)),
                                           (image_sha, images, split)):
                if value in group and group[value] != identity:
                    raise ValueError('Stored dataset contains source or match leakage across splits')
                group[value] = identity
            records.append(record)
        return records

    def running(self):
        with self.lock:
            return any(j['status'] in {'queued', 'running'} for j in self.jobs.values())

    def summary(self):
        with self.lock:
            records = self.records()
            splits = {s: {'frames': 0, 'matches': set(), 'classes': Counter(), 'backgrounds': 0}
                      for s in ('train', 'val', 'test')}
            for record in records:
                group = splits[record['split']]
                group['frames'] += 1
                group['matches'].add(record['match_id'])
                group['classes'].update(o['role'] for o in record['frame']['objects'])
                group['backgrounds'] += not record['frame']['objects']
            for group in splits.values():
                group['matches'] = sorted(group['matches'])
                group['classes'] = dict(group['classes'])
            ready = all(all(splits[s]['classes'].get(role, 0) for role in CLASSES) for s in ('train', 'val'))
            jobs = [{k: v for k, v in j.items() if k != 'cancel'} for j in self.jobs.values()]
            return {'schema': 'touchline-training-status-v1', 'splits': splits,
                    'ready': bool(ready), 'jobs': jobs[-10:], 'promotion': 'manual-only',
                    'note': 'Team and shirt colors are retained for review; YOLO learns the four object roles.'}

    def save_frame(self, payload):
        sha = payload.get('source_sha256', '')
        match = payload.get('match_id', '')
        split = payload.get('split')
        if not isinstance(sha, str) or not re.fullmatch('[a-f0-9]{64}', sha):
            raise ValueError('An exact video SHA-256 is required')
        if not isinstance(match, str) or not match.strip() or len(match) > 100:
            raise ValueError('Enter a match ID (up to 100 characters)')
        match = match.strip()
        if split not in {'train', 'val', 'test'}:
            raise ValueError('Choose train, validation, or test for the entire match')
        frame = payload.get('frame')
        validate_ground_truth({'schema': 'touchline-groundtruth-v1', 'source_sha256': sha,
                               'frames': [frame]}, sha)
        if isinstance(frame['t'], bool) or frame['t'] >= 4 * 3600:
            raise ValueError('Reviewed timestamp must lie within a video shorter than four hours')
        # A review is a complete image annotation, including empty/background frames.
        for obj in frame['objects']:
            color = obj.get('kit_color')
            if color is not None and (not isinstance(color, str) or not re.fullmatch('#[a-fA-F0-9]{6}', color)):
                raise ValueError('Invalid reviewed shirt color')
        raw = payload.get('image_base64')
        if not isinstance(raw, str) or len(raw) > 9_000_000:
            raise ValueError('Reviewed frame image is missing or too large')
        try:
            image_bytes = base64.b64decode(raw, validate=True)
        except (ValueError, TypeError) as error:
            raise ValueError('Invalid frame image encoding') from error
        if not image_bytes.startswith(b'\xff\xd8'):
            raise ValueError('Use a JPEG frame')
        image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
        if image is None or image.shape[0] * image.shape[1] > 33_000_000:
            raise ValueError('Frame cannot be decoded or exceeds 33 megapixels')
        if [image.shape[1], image.shape[0]] != [payload.get('width'), payload.get('height')]:
            raise ValueError('Frame dimensions do not match the review')
        stamp = round(frame['t'] * 1_000_000)
        key = f'{sha}-{stamp:012d}'
        record = {'schema': 'touchline-reviewed-frame-v1', 'key': key,
                  'source_sha256': sha, 'source_name': str(payload.get('source_name', ''))[:180],
                  'match_id': match, 'split': split, 'width': image.shape[1], 'height': image.shape[0],
                  'frame': frame, 'image_sha256': hashlib.sha256(image_bytes).hexdigest(),
                  'reviewed_utc': datetime.now(timezone.utc).isoformat()}
        with self.lock:
            for old in self.records():
                if old['match_id'] == match and old['split'] != split:
                    raise ValueError('This match already belongs to another split; keep every clip from it together')
                if old['source_sha256'] == sha and (old['match_id'], old['split']) != (match, split):
                    raise ValueError('This video already has a different match ID or split')
                if old['image_sha256'] == record['image_sha256'] and old['split'] != split:
                    raise ValueError('Identical reviewed image content cannot cross dataset splits')
            folder = self.root / 'frames' / key
            folder.mkdir(parents=True, exist_ok=True)
            temporary = folder / 'frame.partial'
            temporary.write_bytes(image_bytes)
            temporary.replace(folder / 'frame.jpg')
            write_json(folder / 'review.json', record)
        return {'saved': True, 'key': key, 'summary': self.summary(),
                'kit_calibration_ready': bool(self.reviewed_palette(sha))}

    def reviewed_palette(self, source_sha256):
        """Use explicit shirt samples from three distinct reviewed outfield IDs per team."""
        with self.lock:
            samples = {'home': {}, 'away': {}}
            for record in self.records():
                if record['source_sha256'] != source_sha256:
                    continue
                for obj in record['frame']['objects']:
                    team, color = obj['team'], obj.get('kit_color')
                    if obj['role'] == 'player' and team in samples and color:
                        samples[team].setdefault(obj['id'], []).append([int(color[i:i+2], 16) for i in (1, 3, 5)])
            if any(len(group) < 3 for group in samples.values()):
                return None
            return {team: '#' + ''.join(f'{int(v):02x}' for v in np.median(
                [np.median(colors, axis=0) for colors in group.values()], axis=0))
                for team, group in samples.items()}

    def delete_frame(self, key):
        if not re.fullmatch('[a-f0-9]{64}-[0-9]{12}', key):
            raise ValueError('Invalid reviewed frame key')
        with self.lock:
            folder = self.root / 'frames' / key
            for name in ('review.json', 'frame.jpg', 'review.partial', 'frame.partial'):
                (folder / name).unlink(missing_ok=True)
            if folder.exists():
                folder.rmdir()

    def build_dataset(self, run_id):
        with self.lock:
            records = self.records()
            if not self.summary()['ready']:
                raise ValueError('Save all four reviewed roles from separate training and validation matches first')
            target = self.root / 'datasets' / run_id
            target.mkdir(parents=True, exist_ok=False)
            try:
                for record in records:
                    split, key = record['split'], record['key']
                    images, labels = target / 'images' / split, target / 'labels' / split
                    images.mkdir(parents=True, exist_ok=True)
                    labels.mkdir(parents=True, exist_ok=True)
                    source = self.root / 'frames' / key / 'frame.jpg'
                    if digest(source) != record['image_sha256']:
                        raise ValueError('A stored review image changed; review and save it again')
                    shutil.copyfile(source, images / (key + '.jpg'))
                    lines = []
                    for obj in record['frame']['objects']:
                        x1, y1, x2, y2 = obj['bbox']
                        lines.append(f"{CLASSES[obj['role']]} {(x1+x2)/2:.8f} {(y1+y2)/2:.8f} {x2-x1:.8f} {y2-y1:.8f}")
                    (labels / (key + '.txt')).write_text('\n'.join(lines), encoding='utf-8')
                config = f'path: {json.dumps(str(target.resolve()).replace(chr(92), "/"))}\ntrain: images/train\nval: images/val\n'
                if any(r['split'] == 'test' for r in records):
                    config += 'test: images/test\n'
                config += 'names:\n' + ''.join(f'  {n}: {role}\n' for role, n in CLASSES.items())
                (target / 'data.yaml').write_text(config, encoding='utf-8')
                write_json(target / 'provenance.json', {'schema': 'touchline-reviewed-dataset-v1', 'frames': records})
                (target / 'COMPLETE').write_text('Reviewed snapshot; inspect train_batch previews before a longer run.\n')
            except Exception:
                (target / 'INCOMPLETE').write_text('Do not use this incomplete snapshot.\n')
                raise
        return target

    def update(self, job_id, **values):
        with self.lock:
            self.jobs[job_id].update(values)

    def start(self, settings):
        epochs, imgsz, batch = settings.get('epochs', 1), settings.get('imgsz', 640), settings.get('batch', 1)
        if any(type(v) is not int for v in (epochs, imgsz, batch)) or epochs not in {1, 20, 50} or imgsz not in {640, 960, 1280} or batch not in {1, 2, 4}:
            raise ValueError('Invalid training settings')
        with self.lock:
            if self.running():
                raise ValueError('Another training run is active')
            job_id = uuid.uuid4().hex
            dataset = self.build_dataset(job_id)
            self.jobs[job_id] = {'id': job_id, 'status': 'queued', 'progress': 0,
                                 'message': 'Preparing reviewed dataset', 'cancel': threading.Event(),
                                 'settings': {'epochs': epochs, 'imgsz': imgsz, 'batch': batch}}
            threading.Thread(target=self._train, args=(job_id, dataset), daemon=True).start()
        return job_id

    def _train(self, job_id, dataset):
        try:
            import torch
            os.environ['ULTRALYTICS_SAFE_LOAD'] = '1'
            from ultralytics import YOLO
            from football_engine import resolve_model, MODEL_SHA256
            from importlib.metadata import version

            settings = self.jobs[job_id]['settings']
            cancel = self.jobs[job_id]['cancel']
            self.update(job_id, status='running', message='Validating the verified baseline on validation matches')
            base = resolve_model('football-best.pt', self.models)
            model = YOLO(str(base))
            names = {int(k): str(v).lower() for k, v in model.names.items()}
            if names != {n: role for role, n in CLASSES.items()}:
                raise ValueError('Baseline class order does not match the reviewed football dataset')
            device = 0 if torch.cuda.is_available() else 'cpu'
            root = self.root / 'runs'
            def check(*_):
                if cancel.is_set():
                    raise InterruptedError('Training cancelled; runtime model remains active')
            def validation_metrics(network, name):
                network.add_callback('on_val_batch_end', check)
                check()
                result = network.val(data=str(dataset / 'data.yaml'), imgsz=settings['imgsz'],
                                     batch=settings['batch'], device=device, workers=0,
                                     project=str(root), name=name, plots=True, verbose=False)
                metrics = {str(k): float(v) for k, v in result.results_dict.items() if math.isfinite(float(v))}
                if 'metrics/mAP50-95(B)' not in metrics:
                    raise ValueError('Validation did not produce a finite detection mAP50-95 score')
                return metrics
            baseline = validation_metrics(model, job_id + '-baseline')
            check()
            def report(trainer):
                check()
                self.update(job_id, progress=10 + int(70 * (trainer.epoch + 1) / settings['epochs']),
                            message=f"Training candidate: epoch {trainer.epoch+1}/{settings['epochs']}")
            model.add_callback('on_train_batch_end', check)
            model.add_callback('on_train_epoch_end', report)
            self.update(job_id, progress=10, message=f'Training candidate on {device}')
            model.train(data=str(dataset / 'data.yaml'), **settings, device=device, workers=0,
                        val=True, plots=True, cache=False, project=str(root), name=job_id,
                        seed=23, deterministic=True, exist_ok=False, verbose=False)
            checkpoint = root / job_id / 'weights' / 'best.pt'
            if not checkpoint.is_file():
                raise ValueError('No validation-selected best checkpoint was produced')
            self.update(job_id, progress=90, message='Comparing candidate with baseline on validation matches')
            candidate = validation_metrics(YOLO(str(checkpoint)), job_id + '-candidate')
            check()
            manifest = {'schema': 'touchline-supervised-candidate-v1', 'id': job_id,
                        'teacher': 'football-best.pt', 'teacher_sha256': MODEL_SHA256,
                        'candidate_sha256': digest(checkpoint), 'settings': settings, 'device': str(device),
                        'dataset_manifest_sha256': digest(dataset / 'provenance.json'),
                        'baseline_validation': baseline, 'candidate_validation': candidate,
                        'packages': {name: version(name) for name in ('ultralytics', 'torch')},
                        'promotion': 'disabled-candidate-only', 'test_set': 'untouched',
                        'scope': 'Object detector roles only; kit colors and track identities are not trained',
                        'smoke_test_only': settings['epochs'] == 1}
            write_json(root / job_id / 'candidate.json', manifest)
            self.update(job_id, status='completed', progress=100, message='Inactive candidate saved', manifest=manifest)
        except InterruptedError as error:
            self.update(job_id, status='cancelled', message=str(error))
        except Exception as error:
            self.update(job_id, status='failed', message='Candidate training failed', error=str(error)[:1000])

    def artifact(self, job_id, name):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or job['status'] != 'completed':
                raise ValueError('This candidate is not complete')
        return self.root / 'runs' / job_id / ('weights/best.pt' if name == 'candidate' else 'candidate.json')
