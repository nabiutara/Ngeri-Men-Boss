"""Host-checked library routes; Explorer opens only registered library folders."""
import ipaddress
import json
import mimetypes
import os
import re
import uuid
from urllib.parse import parse_qs, urlsplit


def send_file(handler, path):
    size = path.stat().st_size
    start, end = 0, size - 1
    requested = handler.headers.get('Range')
    if requested:
        match = re.fullmatch(r'bytes=(\d+)-(\d*)', requested)
        if not match or int(match[1]) >= size:
            handler.send_response(416)
            handler.send_header('Content-Range', f'bytes */{size}')
            handler.end_headers()
            return
        start = int(match[1])
        end = min(int(match[2]) if match[2] else end, end)
        if end < start:
            raise ValueError('Invalid byte range')
    handler.send_response(206 if requested else 200)
    handler.send_header('Content-Type', mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
    handler.send_header('Content-Length', str(max(0, end - start + 1)))
    handler.send_header('Accept-Ranges', 'bytes')
    handler.send_header('Cache-Control', 'no-store')
    handler.send_header('X-Content-Type-Options', 'nosniff')
    if requested:
        handler.send_header('Content-Range', f'bytes {start}-{end}/{size}')
    handler.end_headers()
    with path.open('rb') as file:
        file.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            block = file.read(min(1024 * 1024, remaining))
            if not block:
                break
            handler.wfile.write(block)
            remaining -= len(block)


def get(handler, library):
    path = urlsplit(handler.path).path
    try:
        if path == '/api/library':
            handler.json_response(library.catalog())
        elif path.startswith('/api/library/reviews/'):
            key = path.removeprefix('/api/library/reviews/')
            if re.fullmatch('[a-f0-9]{64}', key):
                handler.json_response({'records': library.reviews(key)})
            elif re.fullmatch('[a-f0-9]{64}-[0-9]{12}/(frame.jpg|review.json)', key):
                send_file(handler, library.path('reviewed-frames/frames/' + key))
            else:
                raise ValueError('Invalid review key')
        else:
            match = re.fullmatch(r'/api/library/(videos|analyses|projects)/([a-f0-9]{32}|[a-f0-9]{64})', path)
            if not match:
                raise ValueError('Unknown library resource')
            row = library.item(match[1], match[2])
            if not row['path']:
                raise ValueError('No result file for this run')
            send_file(handler, library.path(row['path']))
    except (OSError, ValueError, TypeError) as error:
        handler.json_response({'error': str(error)}, 400)


def post(handler, library):
    path = urlsplit(handler.path).path
    temporary = None
    try:
        size = int(handler.headers.get('Content-Length', '0'))
        handler.connection.settimeout(120)
        if path == '/api/library/videos':
            if not 0 < size <= 2 * 1024**3:
                raise ValueError('Video must be between 1 byte and 2 GB')
            name = parse_qs(urlsplit(handler.path).query).get('filename', ['match.mp4'])[0]
            temporary = library.path('imports/' + uuid.uuid4().hex + '.partial')
            remaining = size
            with temporary.open('wb') as output:
                while remaining:
                    block = handler.rfile.read(min(1024 * 1024, remaining))
                    if not block:
                        raise ValueError('Video copy was interrupted')
                    output.write(block)
                    remaining -= len(block)
            handler.json_response(library.retain(temporary, name), 201)
            return
        if not 0 < size <= (400 * 1024**2 if path == '/api/library/projects' else 4096):
            raise ValueError('Invalid library request size')
        body = json.loads(handler.rfile.read(size))
        if not isinstance(body, dict):
            raise ValueError('Expected a JSON object')
        if path == '/api/library/projects':
            handler.json_response(library.save_project(body))
        elif path == '/api/library/open':
            if not ipaddress.ip_address(handler.client_address[0]).is_loopback:
                raise ValueError('Open File Explorer on the PC running Touchline')
            category = body.get('category', '')
            if category not in {'', 'videos', 'analyses', 'projects', 'reviewed-frames'}:
                raise ValueError('Unknown library folder')
            folder = library.path(category)
            if body.get('review'):
                key = body['review']
                if not isinstance(key, str) or not re.fullmatch('[a-f0-9]{64}-[0-9]{12}', key):
                    raise ValueError('Invalid review key')
                folder = library.path('reviewed-frames/frames/' + key)
            if not folder.is_dir():
                raise ValueError('Folder is missing')
            if os.name != 'nt':
                raise ValueError('File Explorer is available on Windows only')
            os.startfile(str(folder))
            handler.json_response({'opened': True})
        else:
            raise ValueError('Unknown library action')
    except (OSError, ValueError, TypeError, KeyError) as error:
        handler.json_response({'error': str(error)}, 400)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
