import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

import server
from training_workflow import TrainingWorkflow
from test_training_workflow import packet


class ReviewedTrainingAPITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        workflow = TrainingWorkflow(Path(temporary.name) / 'training', Path(temporary.name) / 'models')
        patcher = patch.object(server, 'TRAINING_WORKFLOW', workflow)
        patcher.start(); self.addCleanup(patcher.stop)
        patcher = patch.object(server, 'dependencies_ready', return_value=True)
        patcher.start(); self.addCleanup(patcher.stop)
        self.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.addCleanup(self.http.server_close)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.addCleanup(self.http.shutdown)
        self.base = f'http://127.0.0.1:{self.http.server_port}'
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(self, path, data=None, method=None, headers=None):
        supplied = {'Content-Type': 'application/json', 'X-Touchline-Client': 'studio', 'Origin': self.base}
        supplied.update(headers or {})
        request = urllib.request.Request(self.base + path,
                                         data=json.dumps(data).encode() if data is not None else None,
                                         method=method, headers=supplied)
        try:
            with self.opener.open(request, timeout=5) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def test_review_upload_status_and_delete_round_trip(self):
        code, status = self.request('/api/health')
        self.assertEqual(code, 200)
        self.assertTrue(status['reviewed_training'])
        code, saved = self.request('/api/training/frames', packet())
        self.assertEqual(code, 201, saved)
        _, summary = self.request('/api/training')
        self.assertEqual(summary['splits']['train']['frames'], 1)
        self.assertFalse(summary['ready'])
        code, _ = self.request('/api/training/frames/' + saved['key'], method='DELETE')
        self.assertEqual(code, 200)
        _, summary = self.request('/api/training')
        self.assertEqual(summary['splits']['train']['frames'], 0)

    def test_host_origin_and_review_confirmation_are_enforced(self):
        code, _ = self.request('/api/training/frames', packet(), headers={'Origin': 'http://unrelated.invalid'})
        self.assertEqual(code, 403)
        code, _ = self.request('/api/training', headers={'Host': 'unrelated.invalid'})
        self.assertEqual(code, 403)
        data = packet(); data['frame']['fully_annotated'] = False
        code, result = self.request('/api/training/frames', data)
        self.assertEqual(code, 400)
        self.assertIn('reviewed', result['error'])

    def test_training_and_artifacts_are_unavailable_without_reviewed_data(self):
        code, result = self.request('/api/training/jobs', {'epochs': 1, 'imgsz': 640, 'batch': 1})
        self.assertEqual(code, 400)
        self.assertIn('four', result['error'])
        code, _ = self.request('/api/training/jobs/' + 'a' * 32 + '/candidate')
        self.assertEqual(code, 400)
        _, summary = self.request('/api/training')
        self.assertEqual(summary['jobs'], [])


if __name__ == '__main__':
    unittest.main()
