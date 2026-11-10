import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.request
import urllib.error

from library_store import Library, atomic_json
import server


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.legacy = self.root / 'work'
        self.library = Library(self.root / 'Library', self.legacy)

    def video(self, content=b'video', name='match.mp4'):
        source = self.root / name
        source.write_bytes(content)
        return source, self.library.retain(source, name)

    def test_copy_dedup_same_name_and_restart(self):
        source, first = self.video()
        self.assertTrue(source.exists())
        self.assertEqual(self.library.path(first['path']).read_bytes(), b'video')
        second = self.library.retain(source, 'renamed.mp4')
        self.assertEqual(first['id'], second['id'])
        _, third = self.video(b'different video')
        self.assertNotEqual(first['id'], third['id'])
        reopened = Library(self.library.root, self.legacy)
        self.assertEqual(len(reopened.catalog()['videos']), 2)

    def test_legacy_copy_preserves_originals_and_is_one_time(self):
        legacy = self.root / 'old'
        folder = legacy / 'training' / 'frames' / ('a'*64+'-000000000000')
        folder.mkdir(parents=True)
        record = {'key': folder.name, 'source_sha256': 'a'*64, 'frame': {'t': 0, 'objects': []}}
        atomic_json(folder/'review.json', record)
        (folder/'frame.jpg').write_bytes(b'image')
        (legacy/'jobs').mkdir()
        atomic_json(legacy/'jobs'/('b'*32+'.json'), {'schema':'touchline-tracks-v1','frames':[],'source_name':'old.mp4'})
        library = Library(self.root/'migrated', legacy)
        self.assertEqual(len(library.catalog()['reviews']), 1)
        self.assertEqual(len(library.catalog()['analyses']), 1)
        self.assertTrue((folder/'frame.jpg').exists())
        copied = library.path('reviewed-frames/frames/'+folder.name+'/frame.jpg')
        copied.write_bytes(b'newer')
        Library(library.root, legacy)
        self.assertEqual(copied.read_bytes(), b'newer')

    def test_project_round_trip_preserves_tracking_and_notes(self):
        _, video = self.video()
        project = {'version':1,'annotations':[],'libraryVideoId':video['id'],'libraryProjectId':'a'*32,
                   'title':'Match','timedNotes':[{'time':1,'text':'keep'}], 'tracking':{'frames':[],'source_sha256':video['id']}}
        self.library.save_project(project)
        project.pop('tracking');project['title']='Changed'
        self.library.save_project(project)
        row=self.library.item('projects','a'*32)
        restored=json.loads(self.library.path(row['path']).read_text())
        self.assertEqual(restored['tracking']['source_sha256'], video['id'])
        self.assertEqual(restored['timedNotes'][0]['text'],'keep')
        with self.assertRaises(ValueError):
            self.library.save_project({**project,'libraryProjectId':'../bad'})
        with self.assertRaises(ValueError):
            self.library.path('../outside')
        with self.assertRaises(ValueError):
            self.library.save_project({**project,'tracking':{'source_sha256':'b'*64}})

    def test_run_history_is_durable_and_interruptions_marked(self):
        _, video = self.video()
        self.library.begin_run('a'*32,video,{'stride':1})
        output=self.root/'tracking.json';atomic_json(output,{'frames':[]})
        self.library.finish_run('a'*32,'completed',output)
        self.library.begin_run('b'*32,video,{})
        reopened=Library(self.library.root,self.legacy)
        self.assertEqual(reopened.item('analyses','b'*32)['status'],'interrupted')
        self.assertTrue(reopened.path(reopened.item('analyses','a'*32)['path']).exists())

    def test_process_job_archives_video_and_result(self):
        source=self.root/'incoming.mp4';source.write_bytes(b'clip')
        jobs=self.root/'jobs';jobs.mkdir()
        identity='c'*32
        def track(source, output, **kwargs):
            atomic_json(output, {'schema':'touchline-tracks-v1','frames':[], 'source_sha256':kwargs['source_sha256']})
            return {'frame_count':0}
        with patch.object(server,'LIBRARY',self.library), patch.object(server,'JOBS_DIR',jobs), \
             patch.object(server,'JOBS',{identity:{'cancel':threading.Event(),'status':'running'}}), \
             patch.object(server,'training_workflow') as training, patch.object(server,'track_video',side_effect=track):
            training.return_value.reviewed_palette.return_value=None
            server.process_job(identity,source,'match.mp4',{})
            self.assertEqual(server.JOBS[identity]['status'],'completed')
        self.assertFalse(source.exists())
        self.assertEqual(len(self.library.catalog()['videos']),1)
        self.assertEqual(self.library.item('analyses',identity)['status'],'completed')


class LibraryAPITests(unittest.TestCase):
    video = LibraryTests.video

    def setUp(self):
        LibraryTests.setUp(self)
        patcher=patch.object(server,'LIBRARY',self.library);patcher.start();self.addCleanup(patcher.stop)
        self.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.close)
        self.base=f'http://127.0.0.1:{self.http.server_port}'
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def close(self):
        self.http.shutdown();self.http.server_close();self.thread.join(timeout=3)

    def request(self,path,data=None,headers=None):
        request=urllib.request.Request(self.base+path,data=data,headers={'X-Touchline-Client':'studio',**(headers or {})})
        try:
            with self.opener.open(request) as response:return response.status,response.read(),response.headers
        except urllib.error.HTTPError as error:return error.code,error.read(),error.headers

    def test_upload_range_and_host_guards(self):
        status,body,_=self.request('/api/library/videos?filename=match.mp4',b'0123456789')
        self.assertEqual(status,201);video=json.loads(body)
        status,body,headers=self.request('/api/library/videos/'+video['id'],headers={'Range':'bytes=2-5'})
        self.assertEqual((status,body),(206,b'2345'));self.assertEqual(headers['Content-Range'],'bytes 2-5/10')
        self.assertEqual(self.request('/api/library',headers={'Origin':'https://evil.test'})[0],403)
        self.assertEqual(self.request('/api/library/videos?filename=x.mp4',b'x',headers={'X-Touchline-Client':''})[0],403)
        self.assertEqual(self.request('/api/library/videos/../../server.py')[0],400)

    def test_project_route_and_explorer_allowlist(self):
        _,video=self.video()
        project={'version':1,'annotations':[],'libraryVideoId':video['id'],'libraryProjectId':'d'*32}
        self.assertEqual(self.request('/api/library/projects',json.dumps(project).encode())[0],200)
        self.assertEqual(self.request('/api/library/projects/'+'d'*32)[0],200)
        self.assertEqual(self.request('/api/library/open',b'{"category":"../../"}')[0],400)
        if os.name=='nt':
            with patch('library_http.os.startfile') as start:
                self.assertEqual(self.request('/api/library/open',b'{"category":"videos"}')[0],200)
                start.assert_called_once_with(str(self.library.path('videos')))

    def test_analysis_can_use_retained_video_without_reupload(self):
        _,video=self.video(b'stored clip')
        jobs=self.root/'jobs';jobs.mkdir()
        observed=[];finished=threading.Event()
        def process(identity, source, name, settings):
            observed.append((source.read_bytes(),name));finished.set()
        with patch.object(server,'JOBS',{}), patch.object(server,'JOBS_DIR',jobs), \
             patch.object(server,'TRAINING_WORKFLOW',None), patch.object(server,'dependencies_ready',return_value=True), \
             patch.object(server,'process_job',side_effect=process):
            status,_,_=self.request('/api/jobs?video_id='+video['id'],b'')
            self.assertEqual(status,202);self.assertTrue(finished.wait(2))
        self.assertEqual(observed,[(b'stored clip','match.mp4')])
        self.assertTrue(self.library.path(video['path']).exists())


if __name__=='__main__':
    unittest.main()
