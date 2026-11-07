"""Exercise real HTTP responses for project identity and fresh browser assets."""
from http.server import ThreadingHTTPServer
from pathlib import Path
import json
import os
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import launch
import server


class AssetServingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / 'dist').mkdir()
        self.file = self.root / 'dist/index.html'
        self.file.write_text('<h1>Old heading</h1>', encoding='utf-8')
        self.root_patch = patch.object(server, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)
        self.url = f'http://127.0.0.1:{self.http.server_port}'
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def close_server(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=3)

    def test_reload_returns_edited_html_even_with_old_timestamp(self):
        stamp = self.file.stat()
        with self.opener.open(self.url + '/') as response:
            modified = response.headers['Last-Modified']
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            self.assertIn(b'Old heading', response.read())
        self.file.write_text('<h1>New heading</h1>', encoding='utf-8')
        os.utime(self.file, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        request = urllib.request.Request(self.url + '/', headers={'If-Modified-Since': modified})
        with self.opener.open(request) as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b'New heading', response.read())
            self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_health_identifies_source_folder_without_disclosing_path(self):
        with self.opener.open(self.url + '/api/health') as response:
            status = json.load(response)
        self.assertEqual(status['project_id'], launch.project_identity(self.root))
        self.assertNotEqual(status['project_id'], launch.project_identity(self.root / 'old-copy'))
        self.assertNotIn(str(self.root), json.dumps(status))


if __name__ == '__main__':
    unittest.main()
