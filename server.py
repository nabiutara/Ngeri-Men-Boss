"""Touchline Studio: local web workspace, reviewed training, and video tracking.

No web framework is required to open the editing workspace. Install requirements.txt
to enable YOLO tracking. Footage is processed locally and deleted from the job cache
after processing. The football checkpoint is checksum-verified; Ultralytics supplies
the general-purpose fallback weights on first use. Optional LAN access uses --lan.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import socket
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
import uuid
import webbrowser

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "work"
JOBS_DIR = DATA / "jobs"
MODELS = DATA / "models"
for directory in (DATA, JOBS_DIR, MODELS):
    directory.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(DATA / "ultralytics"))
os.environ.setdefault("YOLO_AUTOINSTALL", "false")

JOBS: dict[str, dict] = {}
LOCK = threading.Lock()
TRAINING_WORKFLOW = None
TRAINING_INIT_LOCK = threading.Lock()
MAX_UPLOAD = 2 * 1024**3
ALLOWED_MODELS = {"football-best.pt", "yolo26n.pt", "yolo26s.pt"}
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}


def dependencies_ready() -> bool:
    return all(importlib.util.find_spec(name) is not None for name in ("ultralytics", "cv2", "lap", "gdown"))


def training_workflow():
    global TRAINING_WORKFLOW
    with TRAINING_INIT_LOCK:
        if TRAINING_WORKFLOW is None:
            from training_workflow import TrainingWorkflow
            TRAINING_WORKFLOW = TrainingWorkflow(DATA / 'training', MODELS)
    return TRAINING_WORKFLOW


def update_job(job_id: str, **values) -> None:
    with LOCK:
        JOBS[job_id].update(values)


def track_video(source: Path, output: Path, *, model_name="football-best.pt", confidence=.1,
                stride=1, tracker_name="botsort", imgsz=960, source_name=None,
                progress=None, cancel=None, reviewed_palette=None, source_sha256=None) -> dict:
    from football_engine import track_football
    return track_football(source, output, models_dir=MODELS, model_name=model_name,
                          confidence=confidence, stride=stride, tracker_name=tracker_name,
                          imgsz=imgsz, source_name=source_name, progress=progress, cancel=cancel,
                          reviewed_palette=reviewed_palette, source_sha256=source_sha256)


def process_job(job_id: str, source: Path, source_name: str, settings: dict) -> None:
    with LOCK:
        cancel = JOBS[job_id]["cancel"]
    output = JOBS_DIR / f"{job_id}.json"
    try:
        with source.open('rb') as handle:
            source_hash = hashlib.file_digest(handle, 'sha256').hexdigest()
        palette = training_workflow().reviewed_palette(source_hash)
        result = track_video(source, output, source_name=source_name, **settings,
                             reviewed_palette=palette, source_sha256=source_hash,
                             progress=lambda p, m: update_job(job_id, progress=p, message=m), cancel=cancel)
        source.unlink(missing_ok=True)
        update_job(job_id, status="completed", progress=100, message="Tracking complete", **result)
    except InterruptedError:
        update_job(job_id, status="cancelled", message="Analysis cancelled")
        output.unlink(missing_ok=True)
    except Exception as exc:
        update_job(job_id, status="failed", error=str(exc), message="Analysis failed")
        output.unlink(missing_ok=True)
    finally:
        source.unlink(missing_ok=True)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "dist"), **kwargs)

    def log_message(self, format, *args):
        if "/api/jobs/" not in str(args[0] if args else ""):
            super().log_message(format, *args)

    def json_response(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def valid_request(self, mutation=False):
        host = self.headers.get("Host", "")
        hosts = {"127.0.0.1", "localhost"}
        if getattr(self.server, "network_access", False):
            hosts.add(self.server.network_host)
        allowed = {f"{name}:{self.server.server_port}" for name in hosts}
        if host not in allowed:
            self.json_response({"error": "Invalid host"}, 403)
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://{h}" for h in allowed}:
            self.json_response({"error": "This runner only accepts its own local workspace"}, 403)
            return False
        if mutation and self.headers.get("X-Touchline-Client") != "studio":
            self.json_response({"error": "Missing workspace header"}, 403)
            return False
        return True

    def do_GET(self):
        if not self.valid_request():
            return
        path = urlsplit(self.path).path
        if path == "/api/health":
            self.json_response({"app": "touchline-studio", "ready": dependencies_ready(), "version": 3, "reviewed_training": True, "models": sorted(ALLOWED_MODELS), "football_model_ready": (MODELS / "football-best.pt").exists(), "network_access": getattr(self.server, "network_access", False), "phone_url": getattr(self.server, "phone_url", None)})
            return
        if path == '/api/training' or re.fullmatch(r'/api/training/jobs/[a-f0-9]{32}/(candidate|manifest)', path):
            if not dependencies_ready():
                self.json_response({'error': 'Install tracking dependencies with Start Touchline.cmd first'}, 503)
                return
            try:
                workflow = training_workflow()
                if path == '/api/training':
                    self.json_response(workflow.summary())
                else:
                    _, _, _, _, job_id, artifact = path.split('/')
                    file = workflow.artifact(job_id, artifact)
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/octet-stream' if artifact == 'candidate' else 'application/json')
                    self.send_header('Content-Disposition', f'attachment; filename="touchline-{job_id}{file.suffix}"')
                    self.send_header('Content-Length', str(file.stat().st_size))
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    with file.open('rb') as handle:
                        shutil.copyfileobj(handle, self.wfile)
            except (OSError, ValueError) as error:
                self.json_response({'error': str(error)}, 400)
            return
        match = re.fullmatch(r"/api/jobs/([a-f0-9]{32})(/result)?", path)
        if match:
            job_id, result_suffix = match.groups()
            with LOCK:
                job = JOBS.get(job_id)
                status = {k: v for k, v in job.items() if k != "cancel"} if job else None
            if not status:
                self.json_response({"error": "Job not found"}, 404)
                return
            if result_suffix:
                if status["status"] != "completed":
                    self.json_response({"error": "Results are not ready"}, 409)
                    return
                output = JOBS_DIR / f"{job_id}.json"
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(output.stat().st_size))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                with output.open("rb") as handle:
                    shutil.copyfileobj(handle, self.wfile)
            else:
                self.json_response(status)
            return
        if path.startswith("/api/"):
            self.json_response({"error": "Endpoint not found"}, 404)
            return
        super().do_GET()

    def list_directory(self, path):
        self.send_error(404)
        return None

    def do_POST(self):
        if not self.valid_request(mutation=True):
            return
        if urlsplit(self.path).path in {'/api/training/frames', '/api/training/jobs'}:
            if not dependencies_ready():
                self.json_response({'error': 'Install tracking dependencies before saving training samples'}, 503)
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 10 * 1024**2:
                    raise ValueError('Training request must be smaller than 10 MB')
                self.connection.settimeout(60)
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError('Expected a JSON object')
                with LOCK:
                    workflow = training_workflow()
                    if urlsplit(self.path).path == '/api/training/frames':
                        result = workflow.save_frame(body)
                    else:
                        if any(j['status'] in {'uploading', 'running'} for j in JOBS.values()):
                            raise ValueError('Wait for video analysis to finish before training')
                        result = {'id': workflow.start(body)}
                self.json_response(result, 201)
            except (OSError, ValueError, TypeError, KeyError) as error:
                self.json_response({'error': str(error)}, 400)
            return
        if urlsplit(self.path).path != "/api/jobs":
            self.json_response({"error": "Endpoint not found"}, 404)
            return
        if not dependencies_ready():
            self.json_response({"error": "YOLO dependencies are not installed. Run Start Touchline.cmd."}, 503)
            return
        try:
            query = parse_qs(urlsplit(self.path).query)
            filename = Path(query.get("filename", ["match.mp4"])[0]).name
            extension = Path(filename).suffix.lower()
            model_name = query.get("model", ["football-best.pt"])[0]
            confidence = float(query.get("conf", ["0.1"])[0])
            stride = int(query.get("stride", ["1"])[0])
            tracker_name = query.get("tracker", ["botsort"])[0]
            imgsz = int(query.get("imgsz", ["960"])[0])
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_UPLOAD:
                raise ValueError("Upload an actual video smaller than 2 GB")
            if model_name not in ALLOWED_MODELS or extension not in ALLOWED_EXTENSIONS:
                raise ValueError("Unsupported model or video extension")
            if not .05 <= confidence <= .9 or stride not in {1, 2, 3} or tracker_name not in {"bytetrack", "botsort"} or imgsz not in {640, 960, 1280}:
                raise ValueError("Invalid tracking settings")
        except (ValueError, TypeError) as exc:
            self.json_response({"error": str(exc)}, 400)
            return
        with LOCK:
            if TRAINING_WORKFLOW is not None and TRAINING_WORKFLOW.running():
                self.json_response({'error': 'A candidate is training. Wait or cancel it before analyzing video.'}, 409)
                return
            if any(j["status"] in {"uploading", "running"} for j in JOBS.values()):
                self.json_response({"error": "An analysis is already running. Wait or cancel it first."}, 409)
                return
            # Retain at most three completed jobs. Footage itself is never retained.
            completed = [key for key, job in JOBS.items() if job["status"] not in {"uploading", "running"}]
            for old_id in completed[:-2]:
                (JOBS_DIR / f"{old_id}.json").unlink(missing_ok=True)
                del JOBS[old_id]
            job_id = uuid.uuid4().hex
            JOBS[job_id] = {"id": job_id, "status": "uploading", "progress": 0,
                            "message": "Reading local video", "cancel": threading.Event()}
        source = JOBS_DIR / f"{job_id}{extension}"
        try:
            self.connection.settimeout(120)
            remaining = size
            with source.open("wb") as handle:
                while remaining:
                    chunk = self.rfile.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ValueError("The video upload was interrupted")
                    handle.write(chunk)
                    remaining -= len(chunk)
            update_job(job_id, status="running", message="Preparing YOLO")
            threading.Thread(target=process_job, args=(job_id, source, filename,
                {"model_name": model_name, "confidence": confidence, "stride": stride, "tracker_name": tracker_name, "imgsz": imgsz}), daemon=True).start()
            self.json_response({"id": job_id}, 202)
        except Exception as exc:
            source.unlink(missing_ok=True)
            update_job(job_id, status="failed", error=str(exc))
            self.json_response({"error": str(exc)}, 400)

    def do_DELETE(self):
        if not self.valid_request(mutation=True):
            return
        frame_match = re.fullmatch(r'/api/training/frames/([a-f0-9]{64}-[0-9]{12})', urlsplit(self.path).path)
        if frame_match:
            try:
                training_workflow().delete_frame(frame_match[1])
                self.json_response({'deleted': True})
            except (OSError, ValueError) as error:
                self.json_response({'error': str(error)}, 400)
            return
        training_match = re.fullmatch(r'/api/training/jobs/([a-f0-9]{32})', urlsplit(self.path).path)
        if training_match:
            workflow = training_workflow() if dependencies_ready() else None
            with workflow.lock if workflow else LOCK:
                job = workflow.jobs.get(training_match[1]) if workflow else None
                if job:
                    job['cancel'].set()
            self.json_response({'message': 'Cancellation requested'} if job else {'error': 'Training run not found'}, 200 if job else 404)
            return
        match = re.fullmatch(r"/api/jobs/([a-f0-9]{32})", urlsplit(self.path).path)
        if not match:
            self.json_response({"error": "Job not found"}, 404)
            return
        with LOCK:
            job = JOBS.get(match[1])
            if job:
                job["cancel"].set()
        self.json_response({"message": "Cancellation requested"} if job else {"error": "Job not found"}, 200 if job else 404)


def main():
    parser = argparse.ArgumentParser(description="Touchline Studio local soccer video analysis")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--lan", action="store_true", help="Allow devices on the local network to connect")
    parser.add_argument("--open", action="store_true", help="Open the workspace in your default browser")
    parser.add_argument("--input", type=Path, help="Track a video without opening the app")
    parser.add_argument("--output", type=Path, default=Path("tracking.json"))
    parser.add_argument("--model", choices=sorted(ALLOWED_MODELS), default="football-best.pt")
    parser.add_argument("--stride", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--tracker", choices=("bytetrack", "botsort"), default="botsort")
    parser.add_argument("--imgsz", type=int, choices=(640, 960, 1280), default=960)
    parser.add_argument("--confidence", type=float, default=.1)
    args = parser.parse_args()
    if args.input:
        result = track_video(args.input.resolve(), args.output.resolve(), model_name=args.model, stride=args.stride, tracker_name=args.tracker, imgsz=args.imgsz, confidence=args.confidence,
                             progress=lambda percent, message: print(message, flush=True))
        print(json.dumps(result))
        return
    host = "0.0.0.0" if args.lan else "127.0.0.1"
    server = ThreadingHTTPServer((host, args.port), Handler)
    server.network_access = args.lan
    server.network_host = ""
    server.phone_url = None
    if args.lan:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("192.0.2.1", 9))
            server.network_host = str(ipaddress.ip_address(probe.getsockname()[0]))
        finally:
            probe.close()
        if not ipaddress.ip_address(server.network_host).is_private:
            server.server_close()
            raise RuntimeError("Could not identify a private Wi-Fi address for phone access")
        server.phone_url = f"http://{server.network_host}:{server.server_port}"
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Touchline Studio is ready: {url}", flush=True)
    if server.phone_url:
        print(f"Phone link (same Wi-Fi): {server.phone_url}", flush=True)
    print("Close this window or press Ctrl+C to stop. Video analysis stays on this computer.", flush=True)
    if args.open:
        threading.Timer(.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        with LOCK:
            for job in JOBS.values():
                job["cancel"].set()
        server.server_close()


if __name__ == "__main__":
    main()
