"""Modal GPU worker and authenticated job-control API for Touchline Studio."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

sys.path.insert(0, "/root/touchline")

import modal


APP = modal.App("touchline-studio")
DATA_ROOT = Path("/mnt/touchline")
VOLUME = modal.Volume.from_name("touchline-studio-data", create_if_missing=True)
CALLS = modal.Dict.from_name("touchline-studio-calls", create_if_missing=True)
IMAGE = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("libgl1", "libglib2.0-0", "ffmpeg")
    .pip_install("torch", "torchvision", "ultralytics==8.4.192", "lap==0.5.13",
                 "gdown==5.2.2", "opencv-python-headless", "boto3", "fastapi[standard]")
    .add_local_file(str(Path(__file__).resolve().parents[1] / "football_engine.py"),
                    "/root/touchline/football_engine.py", copy=True)
    .add_local_file(str(Path(__file__).resolve().parent / "pseudo_training.py"),
                    "/root/touchline/pseudo_training.py", copy=True)
)
R2_SECRET = modal.Secret.from_name("touchline-r2")
CALLBACK_SECRET = modal.Secret.from_name("touchline-callback")


def _callback(job_id: str, *, status: str, progress: int, message: str,
              **extra) -> None:
    import urllib.request

    endpoint = os.environ["TOUCHLINE_CALLBACK_URL"].rstrip("/")
    secret = os.environ["TOUCHLINE_CALLBACK_SECRET"]
    payload = json.dumps({"status": status, "progress": progress, "message": message,
                          **extra}, separators=(",", ":")).encode()
    request = urllib.request.Request(
        f"{endpoint}/api/internal/jobs/{job_id}", data=payload, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {secret}"})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status >= 300:
            raise RuntimeError(f"Job status callback failed with HTTP {response.status}")


def _train_candidate(job_id: str, source: Path, tracking: dict, source_digest: str,
                     model_dir: Path, client, bucket: str) -> tuple[dict, str | None]:
    from pseudo_training import build_pseudo_samples, write_dataset_config

    sample_root = DATA_ROOT / "pseudo-training" / "samples"
    sample_root.mkdir(parents=True, exist_ok=True)
    sample_info = build_pseudo_samples(source, tracking, sample_root)
    candidate_root = DATA_ROOT / "candidates"
    candidate_root.mkdir(parents=True, exist_ok=True)
    data_yaml = candidate_root / "pseudo-data.yaml"
    sample_count = write_dataset_config(sample_root, data_yaml)
    if sample_count < 4 or sample_info.get("sampled_frames", 0) == 0:
        return ({"status": "skipped", "reason": "Need at least four usable retained sample frames",
                 "sampled_frames": sample_info.get("sampled_frames", 0),
                 "source_sha256": source_digest}, None)

    _callback(job_id, status="training", progress=82,
              message=f"Training an isolated candidate on {sample_count} pseudo-labeled frames")
    from football_engine import resolve_model
    from ultralytics import YOLO

    base = resolve_model("football-best.pt", model_dir)
    model = YOLO(str(base))
    model.train(data=str(data_yaml), epochs=1, imgsz=640, batch=4, workers=2,
                device=0, val=False, plots=False, cache=False,
                project=str(candidate_root / "runs"), name=job_id,
                exist_ok=False, verbose=False)
    checkpoint = candidate_root / "runs" / job_id / "weights" / "last.pt"
    if not checkpoint.is_file():
        raise RuntimeError("YOLO training completed without a candidate checkpoint")
    key = f"candidates/{job_id}.pt"
    client.upload_file(str(checkpoint), bucket, key,
                       ExtraArgs={"ContentType": "application/octet-stream"})
    with checkpoint.open("rb") as handle:
        candidate_hash = hashlib.file_digest(handle, "sha256").hexdigest()
    training_list = data_yaml.parent / "train-images.txt"
    training_sources = sorted({Path(line).parent.parent.name
                               for line in training_list.read_text(encoding="utf-8").splitlines() if line})
    from football_engine import MODEL_SHA256
    manifest_key = f"candidates/{job_id}.json"
    manifest = {"schema": "touchline-candidate-v1", "candidate_sha256": candidate_hash,
                "teacher": "football-best.pt", "teacher_sha256": MODEL_SHA256,
                "training_source_sha256": training_sources,
                "pseudo_sample_count": sample_count, "epochs": 1, "imgsz": 640,
                "batch": 4, "validation": "not-run-no-reviewed-labels",
                "promotion": "disabled-candidate-only"}
    client.put_object(Bucket=bucket, Key=manifest_key,
                      Body=json.dumps(manifest, separators=(",", ":")).encode(),
                      ContentType="application/json")
    return ({"status": "candidate-only", "candidate_key": key, "sha256": candidate_hash,
             "pseudo_sample_count": sample_count, "source_sha256": source_digest,
             "manifest_key": manifest_key, "training_source_count": len(training_sources),
             "teacher": "football-best.pt", "epochs": 1,
             "validation": "not-run-no-reviewed-labels"}, key)


@APP.function(image=IMAGE, gpu="L4", timeout=4 * 60 * 60,
              volumes={str(DATA_ROOT): VOLUME}, secrets=[R2_SECRET, CALLBACK_SECRET],
              max_containers=1)
def process_video(job_id: str, source_key: str, source_name: str, settings: dict) -> None:
    """Track an uploaded match, retain sparse pseudo labels, train a candidate."""
    import boto3
    from football_engine import track_football

    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise ValueError("Invalid job ID")
    if not source_key.startswith(f"uploads/{job_id}/"):
        raise ValueError("Upload key does not belong to this job")
    bucket = None
    client = None
    job_dir = DATA_ROOT / "jobs" / job_id
    source = job_dir / "upload"
    result_path = DATA_ROOT / "results" / f"{job_id}.json"
    result_key = f"results/{job_id}.json"
    candidate_key = None
    source_digest = None
    try:
        bucket = os.environ["R2_BUCKET"]
        client = boto3.client(
            "s3", endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")
        suffix = Path(source_name).suffix.lower()
        if suffix not in {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}:
            raise ValueError("Unsupported video format")
        job_dir.mkdir(parents=True, exist_ok=False)
        source = job_dir / ("upload" + suffix)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        _callback(job_id, status="running", progress=1, message="Downloading video to GPU worker")
        client.download_file(bucket, source_key, str(source))
        with source.open("rb") as handle:
            source_digest = hashlib.file_digest(handle, "sha256").hexdigest()

        last_report = 0.0
        def report(percent: float, message: str) -> None:
            nonlocal last_report
            now = time.monotonic()
            if now - last_report < 2 and percent < 94:
                return
            last_report = now
            _callback(job_id, status="running", progress=min(74, max(1, int(percent * .74))),
                      message=message)

        model_dir = DATA_ROOT / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        from football_engine import track_football
        track_football(source, result_path, models_dir=model_dir,
                       model_name="football-best.pt", progress=report, **settings)
        tracking = json.loads(result_path.read_text(encoding="utf-8"))
        client.upload_file(str(result_path), bucket, result_key,
                           ExtraArgs={"ContentType": "application/json"})
        _callback(job_id, status="training", progress=77,
                  message="Tracking complete · extracting prediction-labeled samples",
                  result_key=result_key, source_sha256=source_digest)

        try:
            candidate_info, candidate_key = _train_candidate(
                job_id, source, tracking, source_digest, model_dir, client, bucket)
        except Exception as training_error:
            # Tracking output remains successful and downloadable if candidate training fails.
            candidate_info = {"status": "failed", "reason": str(training_error)[:500],
                              "source_sha256": source_digest}

        client.delete_object(Bucket=bucket, Key=source_key)
        _callback(job_id, status="completed", progress=100,
                  message="Tracking complete · candidate training finished",
                  result_key=result_key, source_sha256=source_digest,
                  training=candidate_info, candidate_key=candidate_key)
    except Exception as exc:
        try:
            _callback(job_id, status="failed", progress=100,
                      message="Cloud job failed", error=str(exc), result_key=result_key,
                      source_sha256=source_digest)
        except Exception:
            pass
        raise
    finally:
        if client and bucket:
            try:
                client.delete_object(Bucket=bucket, Key=source_key)
            except Exception:
                pass
        source.unlink(missing_ok=True)
        VOLUME.commit()


api = __import__("fastapi").FastAPI()


@api.get("/health")
def cloud_health():
    return {"ready": True, "app": "touchline-studio-cloud-worker"}


@api.post("/submit")
def submit_job(payload: dict):
    job_id = payload.get("job_id", "")
    source_key = payload.get("source_key", "")
    source_name = Path(str(payload.get("source_name", ""))).name
    settings = payload.get("settings")
    if not re.fullmatch(r"[a-f0-9]{32}", job_id) or not source_key.startswith(f"uploads/{job_id}/"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid job or upload key")
    if not isinstance(settings, dict):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid tracking settings")
    try:
        call = process_video.spawn(job_id, source_key, source_name, settings)
        CALLS[job_id] = call.object_id
    except Exception as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Could not queue GPU job") from exc
    return {"queued": True, "call_id": call.object_id}


@api.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    from fastapi import HTTPException
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")
    call_id = CALLS.get(job_id)
    if not call_id:
        raise HTTPException(status_code=409, detail="Job submission is still being recorded")
    try:
        modal.FunctionCall.from_id(call_id).cancel()
        return {"cancelled": True}
    except Exception as exc:
        raise HTTPException(status_code=409, detail="Job can no longer be cancelled") from exc


@APP.function(image=IMAGE, secrets=[R2_SECRET, CALLBACK_SECRET],
              volumes={str(DATA_ROOT): VOLUME})
@modal.asgi_app(requires_proxy_auth=True)
def web_api():
    return api
