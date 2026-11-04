"""Create conservative pseudo-label samples and isolated YOLO candidates.

These outputs are experimental. They are never promoted automatically, and their
training metrics are not treated as evidence that a candidate is better.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import math
import shutil

import cv2


ROLES = {"ball": 0, "goalkeeper": 1, "player": 2, "referee": 3}


def build_pseudo_samples(video: Path, tracking: dict, destination: Path,
                         *, sample_seconds: float = 1.0, min_confidence: float = .65,
                         min_track_observations: int = 3, max_frames: int = 600) -> dict:
    """Write sparse YOLO labels only for confident, repeatedly tracked objects."""
    if sample_seconds <= 0 or not 0 < min_confidence <= 1:
        raise ValueError("Invalid pseudo-label sampling settings")
    if tracking.get("schema") != "touchline-tracks-v1":
        raise ValueError("Unsupported tracking result schema")
    names = {str(k): str(v).lower() for k, v in tracking.get("class_names", {}).items()}
    class_ids = {role: int(class_id) for class_id, role in names.items() if role in ROLES}
    if class_ids != ROLES:
        raise ValueError("Teacher class names and IDs must match the reviewed football model order")
    frames = tracking.get("frames")
    if not isinstance(frames, list) or not frames:
        raise ValueError("Tracking result has no frames")
    occurrences: dict[tuple[int, int], int] = {}
    for frame in frames:
        scene = int((frame.get("camera") or {}).get("scene", 0))
        for person in frame.get("players") or []:
            key = (scene, int(person.get("id", -1)))
            occurrences[key] = occurrences.get(key, 0) + 1

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError("Could not reopen uploaded video for training-sample extraction")
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if not math.isfinite(fps) or fps <= 0 or min(count, width, height) <= 0:
        cap.release()
        raise ValueError("Uploaded video timing is invalid")

    with video.open("rb") as source_handle:
        digest = hashlib.file_digest(source_handle, "sha256").hexdigest()
    sample_dir = destination / digest
    if sample_dir.exists():
        existing = len(list((sample_dir / "images").glob("*.jpg")))
        return {"source_sha256": digest, "sample_directory": str(sample_dir),
                "sampled_frames": existing, "source_frame_count": count,
                "teacher": tracking.get("model"), "class_ids": class_ids,
                "duplicate_upload": True}
    partial_dir = destination / (digest + ".partial")
    if partial_dir.exists():
        shutil.rmtree(partial_dir)
    images = partial_dir / "images"
    labels = partial_dir / "labels"
    images.mkdir(parents=True, exist_ok=False)
    labels.mkdir()
    selected = []
    last_time = -1e9
    try:
        for index, record in enumerate(frames):
            timestamp = float(record.get("t", -1))
            if timestamp < 0 or timestamp - last_time < sample_seconds:
                continue
            if len(selected) >= max_frames:
                break
            selected.append((index, record))
            last_time = timestamp
        written = 0
        included = []
        for index, record in selected:
            frame_number = round(float(record["t"]) * fps)
            if not 0 <= frame_number < count:
                continue
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ok, image = cap.read()
            if not ok:
                continue
            lines = []
            scene = int((record.get("camera") or {}).get("scene", 0))
            for person in record.get("players") or []:
                role = person.get("role")
                confidence = float(person.get("conf", 0))
                key = (scene, int(person.get("id", -1)))
                if role not in class_ids or confidence < min_confidence:
                    continue
                if occurrences.get(key, 0) < min_track_observations:
                    continue
                x, y = float(person["x"]), float(person["y"]) - float(person["h"]) / 2
                w, h = float(person["w"]), float(person["h"])
                if min(x, y, w, h) < 0 or max(x, y, w, h) > 1 or w <= 0 or h <= 0:
                    continue
                lines.append(f"{class_ids[role]} {x:.8f} {y:.8f} {w:.8f} {h:.8f}")
            ball = record.get("ball")
            if ball and ball.get("observed") and float(ball.get("conf", 0)) >= max(.75, min_confidence):
                x, y, w, h = (float(ball[k]) for k in ("x", "y", "w", "h"))
                if min(x, y, w, h) >= 0 and max(x, y, w, h) <= 1 and w > 0 and h > 0:
                    lines.append(f"{class_ids['ball']} {x:.8f} {y:.8f} {w:.8f} {h:.8f}")
            if not lines:
                continue
            stem = f"{frame_number:08d}"
            if not cv2.imwrite(str(images / f"{stem}.jpg"), image, [cv2.IMWRITE_JPEG_QUALITY, 90]):
                raise OSError("Could not save a training sample")
            (labels / f"{stem}.txt").write_text("\n".join(lines), encoding="utf-8")
            written += 1
            included.append({"frame": frame_number, "timestamp": float(record["t"]),
                             "object_count": len(lines)})
    finally:
        cap.release()
    if written == 0:
        # Keep failed attempts out of the training pool.
        shutil.rmtree(partial_dir)
    else:
        manifest = {"schema": "touchline-pseudo-samples-v1", "source_sha256": digest,
                    "teacher": tracking.get("model"), "class_ids": class_ids,
                    "sample_seconds": sample_seconds, "min_confidence": min_confidence,
                    "min_track_observations": min_track_observations,
                    "frames": included}
        (partial_dir / "provenance.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        partial_dir.replace(sample_dir)
    return {"source_sha256": digest, "sample_directory": str(sample_dir),
            "sampled_frames": written, "source_frame_count": count,
            "teacher": tracking.get("model"), "class_ids": class_ids}


def write_dataset_config(samples_root: Path, output: Path, *, max_images: int = 10_000) -> int:
    """Write a bounded, balanced subset spanning retained uploads."""
    if max_images < 1:
        raise ValueError("max_images must be positive")
    groups = [directory for directory in samples_root.glob("*/images") if directory.is_dir()]
    groups.sort(key=lambda directory: directory.stat().st_mtime)
    if len(groups) > max_images:
        groups = groups[-max_images:]
    per_source = max(1, max_images // max(1, len(groups)))
    image_paths = []
    for directory in groups:
        source_images = sorted(directory.glob("*.jpg"))
        if len(source_images) > per_source:
            indices = [round(i * (len(source_images) - 1) / max(1, per_source - 1))
                       for i in range(per_source)]
            source_images = [source_images[index] for index in indices]
        image_paths.extend(source_images)
    image_paths = sorted(image_paths)
    if len(image_paths) < 4:
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    list_path = output.parent / "train-images.txt"
    list_path.write_text("\n".join(str(path.resolve()) for path in image_paths) + "\n", encoding="utf-8")
    image_list = json.dumps(str(list_path.resolve()).replace("\\", "/"))
    config = ("path: " + json.dumps(str(samples_root.resolve()).replace("\\", "/")) + "\n"
              "train: " + image_list + "\n"
              "val: " + image_list + "\n"
              "names:\n  0: ball\n  1: goalkeeper\n  2: player\n  3: referee\n")
    output.write_text(config, encoding="utf-8")
    return len(image_paths)
