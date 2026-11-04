"""Regression tests for generalization beyond the reference repository's sample."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from collections import deque
from unittest.mock import patch
import cv2
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from football_engine import TeamColors, CameraMotion, BallHistory, bounded_ball_fill, jersey_color, role_for, track_football, distinct_people


class FootballTests(unittest.TestCase):
    def test_person_duplicates_keep_roles_aligned_without_merging_neighbors(self):
        people=[[10,20,30,80,.9,0],[10,21,30,80,.6,0],[25,20,45,80,.8,0]]
        rows,roles=distinct_people(people,['goalkeeper','player','player'])
        self.assertEqual(roles,['goalkeeper','player'])
        self.assertEqual([p[4] for p in rows],[.9,.8])

    def test_identity_survives_pan_and_gap_but_resets_on_cut(self):
        from ultralytics.engine.results import Results
        rng=np.random.default_rng(41)
        texture=rng.integers(0,255,(360,640,3),dtype=np.uint8)
        images=[cv2.warpAffine(texture,np.float32([[1,0,12*i],[0,1,0]]),(640,360)) for i in range(5)]
        images.append(rng.integers(0,255,(360,640,3),dtype=np.uint8))
        class FakeModel:
            names={0:'player',1:'goalkeeper'}
            def predict(self,*args,**kwargs):
                for i,image in enumerate(images):
                    # The player disappears for one frame; the goalkeeper remains.
                    boxes=[] if i==2 else [[50+12*i,120,58+12*i,190,.9,0]]
                    boxes += [[300+12*i,120,308+12*i,190,.9,1], [300+12*i,121,308+12*i,190,.6,0]]
                    yield Results(image,'synthetic',self.names,boxes=np.array(boxes,np.float32))
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);video=root/'pan.avi';out=root/'tracks.json'
            writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'MJPG'),20,(640,360))
            self.assertTrue(writer.isOpened())
            for image in images:writer.write(image)
            writer.release()
            with patch('ultralytics.YOLO',return_value=FakeModel()):
                track_football(video,out,models_dir=root,model_name='yolo26n.pt')
            data=json.loads(out.read_text())
            self.assertEqual(data['track_count'],4)
            self.assertEqual(data['camera_resets'],1)
            initial_ids={p['id'] for p in data['frames'][0]['players']}
            self.assertEqual(initial_ids,{p['id'] for p in data['frames'][-2]['players']})
            self.assertTrue(initial_ids.isdisjoint({p['id'] for p in data['frames'][-1]['players']}))
            self.assertEqual(len(data['frames'][2]['players']),1)
            for frame in data['frames']:
                for player in frame['players']:
                    self.assertGreaterEqual(player['x'],0)
                    self.assertLessEqual(player['x'],1)

    def test_jersey_colors_and_outliers(self):
        colors=[]
        for color in [(20,20,220),(210,35,15)]:
            frame=np.full((120,80,3),(35,120,35),np.uint8)
            frame[20:65,20:60]=color
            result=jersey_color(frame,[10,0,70,115])
            self.assertIsNotNone(result);colors.append(result)
        self.assertGreater(np.linalg.norm(colors[0]-colors[1]),50)
        teams=TeamColors()
        for i in range(10):
            for _ in range(4):teams.add(i,colors[i//5])
        for _ in range(4):teams.add(99,np.array([12,128,128],np.float32))
        assignments,palette=teams.fit()
        self.assertEqual(len(assignments),10)
        self.assertEqual(len({assignments[i]['team'] for i in range(5)}),1)
        self.assertNotEqual(assignments[0]['team'],assignments[9]['team'])
        self.assertEqual(set(palette),{'home','away'})
        self.assertIsNone(jersey_color(np.zeros((20,20,3),np.uint8),[1,1,2,2]))

    def test_no_forced_teams_when_evidence_is_insufficient(self):
        teams=TeamColors()
        for i in range(10):
            for _ in range(3):teams.add(i,np.array([130,130,130],np.float32))
        self.assertEqual(teams.fit(),({},{}))
        self.assertEqual(TeamColors().fit(),({},{}))

    def test_green_kit_is_not_discarded_as_grass(self):
        frame=np.full((120,80,3),(35,120,35),np.uint8)
        frame[20:65,20:60]=(70,245,80)
        self.assertIsNotNone(jersey_color(frame,[10,0,70,115]))

    def test_camera_pan_compensation_and_cut(self):
        rng=np.random.default_rng(11)
        texture=rng.integers(0,255,(360,640,3),dtype=np.uint8)
        camera=CameraMotion();camera.update(texture,[])
        shift=np.float32([[1,0,12],[0,1,7]])
        moved=cv2.warpAffine(texture,shift,(640,360))
        result=camera.update(moved,[])
        self.assertFalse(result['reset'])
        matrix=np.array(result['to_reference']).reshape(3,3)
        mapped=matrix@np.array([.5+12/640,.5+7/360,1])
        np.testing.assert_allclose(mapped[:2]/mapped[2],[.5,.5],atol=.004)
        cut=camera.update(rng.integers(0,255,(360,640,3),dtype=np.uint8),[])
        self.assertTrue(cut['reset'])
        self.assertGreater(cut['scene'],result['scene'])

    def test_featureless_frames_do_not_crash(self):
        camera=CameraMotion();frame=np.zeros((120,180,3),np.uint8)
        camera.update(frame,[]);result=camera.update(frame,[])
        self.assertFalse(result['reset'])
        self.assertEqual(len(result['to_reference']),9)

    def test_ball_gap_is_bounded_and_does_not_cross_cut(self):
        a={'x':.1,'y':.3,'w':.01,'h':.01,'conf':.8,'observed':True}
        b={**a,'x':.3}
        empty={'t':.1,'ball':None,'camera':{'scene':0},'_left_ball':{'t':0,'ball':a,'scene':0}}
        right={'t':.2,'ball':b,'camera':{'scene':0}}
        buffer=deque([empty,right]);bounded_ball_fill(buffer)
        self.assertAlmostEqual(empty['ball']['x'],.2)
        self.assertFalse(empty['ball']['observed'])
        for t,scene in [(2.,0),(.2,1)]:
            test={**empty,'ball':None}
            bounded_ball_fill(deque([test,{**right,'t':t,'camera':{'scene':scene}}]))
            self.assertIsNone(test['ball'])
        test={**empty,'ball':None,'_left_ball':None};bounded_ball_fill(deque([test,right]))
        self.assertIsNone(test['ball'])

    def test_ball_selection_does_not_jump_to_distant_false_positive(self):
        history=BallHistory()
        a={'x':.1,'y':.1,'w':.01,'h':.01,'conf':.8}
        history.choose([a],0,0)
        self.assertIsNone(history.choose([{**a,'x':.9}],.1,0))
        self.assertIsNotNone(history.choose([{**a,'x':.9}],.1,1))

    def test_class_mapping(self):
        self.assertEqual(role_for('goalkeeper'),'goalkeeper')
        self.assertEqual(role_for('sports ball'),'ball')
        self.assertIsNone(role_for('car'))

    def test_large_identity_count_uses_bounded_fit(self):
        teams=TeamColors()
        for identity in range(1200):
            color=np.array([170,90,170] if identity%2 else [240,125,125],np.float32)
            for _ in range(3):teams.add(identity,color)
        original=cv2.kmeans
        sizes=[]
        def record_size(data,*args,**kwargs):
            sizes.append(len(data))
            return original(data,*args,**kwargs)
        with patch('football_engine.cv2.kmeans',side_effect=record_size):
            assignments,_=teams.fit()
        self.assertLessEqual(max(sizes),512)
        self.assertEqual(len(assignments),1200)

    def test_empty_video_results_and_cancellation_cleanup(self):
        from ultralytics.engine.results import Results
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);video=root/'empty.avi';out=root/'tracks.json'
            writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'MJPG'),20,(80,80))
            frame=np.zeros((80,80,3),np.uint8)
            for _ in range(3):writer.write(frame)
            writer.release()
            class FakeModel:
                names={0:'player',1:'ball'}
                def predict(self,*args,**kwargs):
                    self.kwargs=kwargs
                    for _ in range(3):
                        yield Results(frame,'test',self.names,boxes=np.empty((0,6),np.float32))
            model=FakeModel()
            with patch('ultralytics.YOLO',return_value=model):
                track_football(video,out,models_dir=root,model_name='yolo26n.pt')
            data=json.loads(out.read_text())
            self.assertTrue(model.kwargs['stream'])
            self.assertEqual([f['t'] for f in data['frames']],[0,.05,.1])
            self.assertTrue(all(not f['players'] and f['ball'] is None for f in data['frames']))
            self.assertEqual(data['team_assignments'],{})
            cancel=threading.Event()
            def progress(p,m):
                if p>0:cancel.set()
            cancelled=root/'cancelled.json'
            with patch('ultralytics.YOLO',return_value=FakeModel()):
                with self.assertRaises(InterruptedError):
                    track_football(video,cancelled,models_dir=root,model_name='yolo26n.pt',cancel=cancel,progress=progress)
            self.assertFalse(cancelled.exists())
            self.assertFalse(list(root.glob('*.partial')))
            self.assertFalse(list(root.glob('*.ndjson')))

    def test_tracker_row_shapes_handled_defensively(self):
        from ultralytics.engine.results import Results
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);video=root/'shape.avi';out=root/'tracks.json'
            writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'MJPG'),20,(100,100))
            frame=np.zeros((100,100,3),np.uint8)
            for _ in range(2):writer.write(frame)
            writer.release()
            class FakeModel:
                names={0:'player',1:'goalkeeper'}
                def predict(self,*args,**kwargs):
                    for _ in range(2):
                        yield Results(frame,'test',self.names,boxes=np.array([[10,10,30,40,.9,0]],np.float32))
            class VariedTracker:
                def __init__(self,cfg):self.calls=0
                def reset(self):pass
                def update(self,detections,img):
                    self.calls+=1
                    if self.calls==1:return np.array([[10,10,30,40,1]],dtype=np.float32)
                    return np.array([[10,10,30,40,1,.95,0,999]],dtype=np.float32)
            with patch('ultralytics.YOLO',return_value=FakeModel()),\
                 patch('ultralytics.trackers.bot_sort.BOTSORT',return_value=VariedTracker(None)):
                track_football(video,out,models_dir=root,model_name='yolo26n.pt')
            data=json.loads(out.read_text())
            self.assertEqual(len(data['frames']),2)
            self.assertEqual(data['frames'][0]['players'][0]['role'],'player')
            self.assertEqual(data['frames'][1]['players'][0]['role'],'player')

    def test_camera_motion_drift_reset_on_extreme_matrix_scale(self):
        rng=np.random.default_rng(11)
        texture=rng.integers(0,255,(360,640,3),dtype=np.uint8)
        motion=CameraMotion()
        motion.update(texture,[])
        # Simulate extreme cumulative zoom drift
        motion.transform=np.diag([4.5,4.5,1.0])
        shift=np.float32([[1,0,2],[0,1,1]])
        moved=cv2.warpAffine(texture,shift,(640,360))
        res=motion.update(moved,[])
        self.assertEqual(res['scene'],1)
        self.assertTrue(res['reset'])
        self.assertEqual(res['method'],'drift-reset')
        self.assertTrue(np.allclose(motion.transform,np.eye(3)))

    def test_ball_history_time_adaptive_radius(self):
        balls=BallHistory()
        balls.choose([{'x':.2,'y':.2,'conf':.9}],0.,0)
        # At dt=0.04s, distance 0.12 exceeds max_radius (~0.08) and is rejected (returns None)
        rejected=balls.choose([{'x':.32,'y':.2,'conf':.9}],.04,0)
        self.assertIsNone(rejected)

        # Separate history
        balls2=BallHistory()
        balls2.choose([{'x':.2,'y':.2,'conf':.9}],0.,0)
        # At dt=0.30s (stride or gap), distance 0.16 is within adaptive max_radius (~0.235) and accepted
        accepted=balls2.choose([{'x':.36,'y':.2,'conf':.85}],.30,0)
        self.assertIsNotNone(accepted)
        self.assertEqual(accepted['x'],.36)

if __name__=='__main__':unittest.main()
