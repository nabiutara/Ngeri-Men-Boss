"""Local media library. SQLite indexes ordinary files; no model dependencies."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import threading
import uuid


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.partial')
    try:
        temporary.write_text(json.dumps(value, allow_nan=False), encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class Library:
    def __init__(self, root, legacy):
        self.root, self.legacy = Path(root).resolve(), Path(legacy).resolve()
        self.lock = threading.RLock()
        for name in ('videos', 'analyses', 'projects', 'reviewed-frames', 'imports'):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        self.database = self.root / 'library.sqlite3'
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS videos(id TEXT PRIMARY KEY, name TEXT, path TEXT, size INTEGER, created TEXT);
                CREATE TABLE IF NOT EXISTS analyses(id TEXT PRIMARY KEY, video_id TEXT, name TEXT, status TEXT, settings TEXT, path TEXT, created TEXT, error TEXT);
                CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, video_id TEXT, run_id TEXT, title TEXT, path TEXT, updated TEXT);
                CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
            ''')
        self.migrate()
        with self.connect() as db:
            db.execute("UPDATE analyses SET status='interrupted', error='Server stopped before completion' WHERE status='running'")

    def connect(self):
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = sqlite3.Row
        return closing_connection(db)

    def path(self, relative):
        target = (self.root / relative).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError('Library path must stay inside its folder')
        return target

    def migrate(self):
        with self.lock, self.connect() as db:
            if db.execute("SELECT 1 FROM meta WHERE key='legacy-v1'").fetchone():
                return
            # Copy only missing files. Never overwrite newer reviews or remove originals.
            old = self.legacy / 'training'
            if old.exists():
                for source in old.rglob('*'):
                    if source.is_file() and not source.is_symlink():
                        target = self.path('reviewed-frames/' + source.relative_to(old).as_posix())
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if not target.exists():
                            shutil.copy2(source, target)
            for source in (self.legacy / 'jobs').glob('*.json'):
                if not re.fullmatch('[a-f0-9]{32}', source.stem):
                    continue
                try:
                    data = json.loads(source.read_text(encoding='utf-8'))
                    if data.get('schema') != 'touchline-tracks-v1':
                        continue
                    relative = 'analyses/' + source.name
                    target = self.path(relative)
                    if not target.exists():
                        shutil.copy2(source, target)
                    sha = data.get('source_sha256')
                    if not isinstance(sha, str) or not re.fullmatch('[a-f0-9]{64}', sha):
                        sha = None
                    settings = {k: data.get(k) for k in ('model', 'tracker', 'stride', 'imgsz')}
                    db.execute('INSERT OR IGNORE INTO analyses VALUES(?,?,?,?,?,?,?,?)',
                               (source.stem, sha, data.get('source_name', source.name), 'completed', json.dumps(settings), relative,
                                datetime.fromtimestamp(source.stat().st_mtime, timezone.utc).isoformat(), None))
                except (ValueError, TypeError):
                    continue
            db.execute("INSERT INTO meta VALUES('legacy-v1',?)", (now(),))

    def retain(self, source, name):
        source = Path(source)
        with source.open('rb') as handle:
            sha = hashlib.file_digest(handle, 'sha256').hexdigest()
        extension = Path(name).suffix.lower()
        if extension not in {'.mp4', '.mov', '.m4v', '.webm', '.mkv', '.avi'}:
            raise ValueError('Unsupported video extension')
        with self.lock, self.connect() as db:
            row = db.execute('SELECT * FROM videos WHERE id=?', (sha,)).fetchone()
            if row and self.path(row['path']).is_file():
                return dict(row)
            relative = f'videos/{sha}{extension}'
            target = self.path(relative)
            temporary = target.with_suffix('.' + uuid.uuid4().hex + '.partial')
            try:
                shutil.copy2(source, temporary)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
            db.execute('INSERT OR REPLACE INTO videos VALUES(?,?,?,?,?)', (sha, Path(name).name[:255], relative, target.stat().st_size, now()))
            return dict(db.execute('SELECT * FROM videos WHERE id=?', (sha,)).fetchone())

    def item(self, table, identity):
        if table not in {'videos', 'analyses', 'projects'}:
            raise ValueError('Invalid collection')
        with self.connect() as db:
            row = db.execute(f'SELECT * FROM {table} WHERE id=?', (identity,)).fetchone()
        if not row:
            raise ValueError('Library item not found')
        return dict(row)

    def begin_run(self, identity, video, settings):
        self.item('videos', video['id'])
        with self.connect() as db:
            db.execute('INSERT INTO analyses VALUES(?,?,?,?,?,?,?,?)', (identity, video['id'], video['name'], 'running', json.dumps(settings), None, now(), None))

    def finish_run(self, identity, status, output=None, error=None):
        relative = None
        if output is not None:
            relative = f'analyses/{identity}.json'
            target = self.path(relative)
            temporary = target.with_suffix('.partial')
            shutil.copy2(output, temporary)
            temporary.replace(target)
        with self.connect() as db:
            db.execute('UPDATE analyses SET status=?,path=?,error=? WHERE id=?', (status, relative, error, identity))

    def save_project(self, data):
        video_id, identity, run_id = data.get('libraryVideoId'), data.get('libraryProjectId'), data.get('libraryRunId')
        if not isinstance(identity, str) or not re.fullmatch('[a-f0-9]{32}', identity):
            raise ValueError('Invalid project identity')
        self.item('videos', video_id)
        if data.get('version') != 1 or not isinstance(data.get('annotations'), list):
            raise ValueError('Invalid project document')
        tracking = data.get('tracking')
        if tracking and (not isinstance(tracking, dict) or tracking.get('source_sha256') not in (None, video_id)):
            raise ValueError('Tracking belongs to another video')
        if run_id:
            run = self.item('analyses', run_id)
            if run['video_id'] != video_id or run['status'] != 'completed':
                raise ValueError('Analysis belongs to another video or is incomplete')
        with self.lock, self.connect() as db:
            old = db.execute('SELECT video_id FROM projects WHERE id=?', (identity,)).fetchone()
            if old and old['video_id'] != video_id:
                raise ValueError('Project belongs to another video')
            relative = f'projects/{identity}.json'
            # Tracking is stored once by the browser for imported/manual results,
            # then retained during subsequent lightweight autosaves.
            path = self.path(relative)
            if 'tracking' not in data and path.exists():
                previous = json.loads(path.read_text(encoding='utf-8'))
                if previous.get('libraryRunId') == run_id and 'tracking' in previous:
                    data = {**data, 'tracking': previous['tracking']}
            atomic_json(path, data)
            db.execute('INSERT OR REPLACE INTO projects VALUES(?,?,?,?,?,?)', (identity, video_id, run_id, str(data.get('title', 'Analysis'))[:100], relative, now()))
        return {'saved': True, 'id': identity}

    def reviews(self, sha=None):
        records = []
        for path in self.path('reviewed-frames/frames').glob('*/review.json'):
            try:
                record = json.loads(path.read_text(encoding='utf-8'))
                key = record.get('key', '')
                if not re.fullmatch('[a-f0-9]{64}-[0-9]{12}', key) or key != path.parent.name:
                    continue
                if sha is None or record.get('source_sha256') == sha:
                    records.append(record)
            except (OSError, ValueError):
                continue
        return sorted(records, key=lambda r: (r['source_sha256'], r['frame']['t']))

    def catalog(self):
        with self.connect() as db:
            result = {table: [dict(row) for row in db.execute(f'SELECT * FROM {table} ORDER BY {"updated" if table == "projects" else "created"} DESC')] for table in ('videos', 'analyses', 'projects')}
        for row in result['analyses']:
            row['settings'] = json.loads(row['settings'])
        result['reviews'] = self.reviews()
        result['folder'] = str(self.root)
        return result


class closing_connection:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self.db

    def __exit__(self, *args):
        try:
            self.db.__exit__(*args)
        finally:
            self.db.close()
