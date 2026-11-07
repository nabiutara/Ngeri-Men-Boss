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
from football_engine import (TeamColors, CameraMotion, BallHistory, bounded_ball_fill,
                             jersey_color, role_for, track_football, distinct_people,
                             PlayerAppearanceEncoder, RepRTAKitClassifier)


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

    def test_player_appearance_encoder_discrimination(self):
        encoder = PlayerAppearanceEncoder(mode='lightweight')
        # Red player
        p_red = np.full((120, 60, 3), (255, 255, 255), dtype=np.uint8)
        p_red[20:70, :] = (20, 20, 220)
        # Same red player slightly perturbed
        p_red_pert = np.full((120, 60, 3), (255, 255, 255), dtype=np.uint8)
        p_red_pert[20:70, :] = (22, 25, 215)
        # Blue player
        p_blue = np.full((120, 60, 3), (220, 50, 20), dtype=np.uint8)
        p_blue[20:70, :] = (210, 35, 15)

        feat_red = encoder.extract_patch_feature(p_red)
        feat_red_pert = encoder.extract_patch_feature(p_red_pert)
        feat_blue = encoder.extract_patch_feature(p_blue)

        self.assertIsNotNone(feat_red)
        self.assertIsNotNone(feat_red_pert)
        self.assertIsNotNone(feat_blue)

        # Normalized L2 norm
        self.assertAlmostEqual(float(np.linalg.norm(feat_red)), 1.0, places=4)
        self.assertAlmostEqual(float(np.linalg.norm(feat_blue)), 1.0, places=4)

        dist_same = 1.0 - float(np.dot(feat_red, feat_red_pert))
        dist_diff = 1.0 - float(np.dot(feat_red, feat_blue))

        # Same player cosine distance should be negligible (< 0.05)
        self.assertLess(dist_same, 0.05)
        # Different kit colors cosine distance should be high (> 0.5)
        self.assertGreater(dist_diff, 0.5)

    def test_player_appearance_encoder_edge_cases(self):
        encoder = PlayerAppearanceEncoder(mode='lightweight')
        # Empty / tiny crop
        self.assertIsNone(encoder.extract_patch_feature(np.zeros((2, 2, 3), dtype=np.uint8)))
        self.assertIsNone(encoder.extract_patch_feature(None))

        # Out of bounds / invalid boxes via __call__
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        bboxes = np.array([
            [50, 50, 20, 40, 0],   # Valid
            [0, 0, 0, 0, 1],       # 0-size
            [200, 200, 20, 20, 2], # Out of bounds
        ], dtype=np.float32)
        feats = encoder(frame, bboxes)
        self.assertEqual(len(feats), 3)
        self.assertIsNotNone(feats[0])
        self.assertIsNone(feats[1])
        self.assertIsNone(feats[2])

        # None image
        self.assertEqual(encoder(None, bboxes), [None, None, None])

    def test_track_football_reid_metadata(self):
        from ultralytics.engine.results import Results
        rng = np.random.default_rng(77)
        texture = rng.integers(0, 255, (240, 320, 3), dtype=np.uint8)
        images = [texture.copy() for _ in range(3)]
        class FakeModel:
            names = {0: 'player'}
            def predict(self, *args, **kwargs):
                for img in images:
                    boxes = [[50, 50, 80, 130, .9, 0]]
                    yield Results(img, 'synthetic', self.names, boxes=np.array(boxes, np.float32))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); video = root / 'clip.avi'; out = root / 'tracks.json'
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'MJPG'), 10, (320, 240))
            for img in images: writer.write(img)
            writer.release()

            with patch('ultralytics.YOLO', return_value=FakeModel()):
                track_football(video, out, models_dir=root, model_name='yolo26n.pt', tracker_name='botsort', with_reid=True)
            data = json.loads(out.read_text())
            self.assertTrue(data['reid_enabled'])
            self.assertEqual(data['reid_method'], 'lightweight')
            self.assertEqual(data['association_space'], 'image-with-botsort-gmc-reid')

    def test_botsort_reid_crossing_stability(self):
        from types import SimpleNamespace
        from ultralytics.trackers.bot_sort import BOTSORT
        from ultralytics.engine.results import Boxes

        cfg = SimpleNamespace(track_high_thresh=0.25, track_low_thresh=0.1,
                              new_track_thresh=0.25, track_buffer=30,
                              match_thresh=0.8, fuse_score=False, gmc_method='sparseOptFlow',
                              proximity_thresh=0.25, appearance_thresh=0.75,
                              with_reid=False, model='auto')
        tracker = BOTSORT(cfg)
        tracker.args.with_reid = True
        tracker.args.model = 'custom'
        tracker.encoder = PlayerAppearanceEncoder(mode='lightweight')

        # Red player moves right (100 -> 150), Blue player moves left (160 -> 110)
        positions = [
            [(100, [20, 20, 220]), (160, [220, 30, 20])],
            [(105, [20, 20, 220]), (155, [220, 30, 20])],
            [(110, [20, 20, 220]), (150, [220, 30, 20])],
            [(120, [20, 20, 220]), (140, [220, 30, 20])],
            [(130, [20, 20, 220]), (130, [220, 30, 20])], # Overlap / cross
            [(140, [20, 20, 220]), (120, [220, 30, 20])],
            [(150, [20, 20, 220]), (110, [220, 30, 20])],
        ]
        track_hist = []
        for frame_data in positions:
            img = np.zeros((300, 300, 3), dtype=np.uint8)
            people = []
            for x, color in frame_data:
                img[40:140, x-15:x+15] = color
                people.append([x-15, 40, x+15, 140, 0.9, 0])
            dets = Boxes(np.array(people, dtype=np.float32), (300, 300))
            res = tracker.update(dets, img)
            track_hist.append({int(r[4]): float(r[0]) for r in res if len(r) >= 5})

        # By final frame, both initial tracks must exist and maintain their distinct directions
        initial_ids = set(track_hist[1].keys())
        final_ids = set(track_hist[-1].keys())
        self.assertEqual(initial_ids, final_ids)

        # Track that started at left (<120) should now be at right (>125)
        id_started_left = [tid for tid, x in track_hist[0].items() if x < 120][0]
        self.assertGreater(track_hist[-1][id_started_left], 125)

    def test_reprta_auxiliary_projection_and_reparameterization(self):
        clf = RepRTAKitClassifier(temperature=0.15)
        centers = np.array([[200., 150., 150.], [50., 110., 80.]], dtype=np.float32)
        weights = clf.reparameterize(centers)

        # Reparameterized weights shape: C x 3
        self.assertEqual(weights.shape, (2, 3))
        # Each row should be L2 normalized
        for row in weights:
            self.assertAlmostEqual(float(np.linalg.norm(row)), 1.0, places=4)

    def test_reprta_kit_classification_alignment(self):
        clf = RepRTAKitClassifier(temperature=0.15)
        # Red kit vs Blue kit
        centers = np.array([[60., 190., 150.], [60., 100., 80.]], dtype=np.float32)
        usable = {
            1: np.array([58., 188., 152.], np.float32), # Red
            2: np.array([62., 192., 148.], np.float32), # Red
            3: np.array([59., 102., 82.], np.float32),  # Blue
            4: np.array([61., 98., 78.], np.float32),   # Blue
            99: np.array([10., 128., 128.], np.float32) # Outlier (dark background/noise)
        }
        res = clf.classify(usable, centers, separation=100.0, names=['home', 'away'])

        # Outlier 99 must be rejected
        self.assertNotIn(99, res)
        # Normal players must be assigned correctly
        self.assertEqual(res[1]['team'], 'home')
        self.assertEqual(res[2]['team'], 'home')
        self.assertEqual(res[3]['team'], 'away')
        self.assertEqual(res[4]['team'], 'away')
        # Calibrated confidence must be high
        for p in (1, 2, 3, 4):
            self.assertGreaterEqual(res[p]['confidence'], 0.5)

    def test_reprta_kit_metadata_in_pipeline(self):
        from ultralytics.engine.results import Results
        images = [np.full((120, 160, 3), (35, 120, 35), dtype=np.uint8) for _ in range(3)]
        # Add 6 players (3 red, 3 blue) so TeamColors has sufficient usable samples
        for img in images:
            img[20:65, 20:40] = (20, 20, 220)  # red
            img[20:65, 100:120] = (210, 35, 15) # blue

        class FakeModel:
            names = {0: 'player'}
            def predict(self, *args, **kwargs):
                for img in images:
                    boxes = [
                        [20, 20, 40, 65, .9, 0],
                        [40, 20, 60, 65, .9, 0],
                        [60, 20, 80, 65, .9, 0],
                        [100, 20, 120, 65, .9, 0],
                        [120, 20, 140, 65, .9, 0],
                        [140, 20, 160, 65, .9, 0],
                    ]
                    yield Results(img, 'synthetic', self.names, boxes=np.array(boxes, np.float32))

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); video = root / 'clip.avi'; out = root / 'tracks.json'
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'MJPG'), 10, (160, 120))
            for img in images: writer.write(img)
            writer.release()

            with patch('ultralytics.YOLO', return_value=FakeModel()):
                track_football(video, out, models_dir=root, model_name='yolo26n.pt')
            data = json.loads(out.read_text())
            self.assertEqual(data['kit_classifier'], 'yoloe-reprta')

if __name__=='__main__':unittest.main()
