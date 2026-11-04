import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evaluation import box_iou, diagnostics, match_objects, score_ground_truth, validate_ground_truth


def fixture():
    frames=[{'t':t,'camera':{'scene':0},'players':[{'id':11,'x':.5,'y':.8,'w':.2,'h':.6,'role':'player','team':'home'}],'ball':None} for t in (0,.1)]
    prediction={'fps':10,'stride':1,'width':1000,'height':500,'frames':frames}
    labels={'schema':'touchline-groundtruth-v1','source_sha256':'fixture',
            'frames':[{'t':t,'reviewed':True,'fully_annotated':True,'objects':[{'id':1,'role':'player','team':'home','bbox':[.4,.2,.6,.8]}]} for t in (0,.1)]}
    return prediction,labels


class EvaluationTests(unittest.TestCase):
    def test_perfect_localization_and_identity(self):
        prediction,truth=fixture()
        result=score_ground_truth(prediction,truth,'fixture')
        self.assertEqual(result['localization']['persons']['tp'],2)
        self.assertEqual(result['localization']['persons']['precision'],1)
        self.assertEqual(result['localization']['persons']['recall'],1)
        self.assertEqual(result['sampled_identity_switches_within_scene'],0)
        self.assertAlmostEqual(result['mean_bbox_bottom_error_pixels'],0)

    def test_missed_and_false_detections(self):
        prediction,truth=fixture()
        prediction['frames'][0]['players']=[]
        prediction['frames'][1]['players'].append({'id':20,'x':.9,'y':.8,'w':.1,'h':.2,'role':'player'})
        metrics=score_ground_truth(prediction,truth,'fixture')['localization']['persons']
        self.assertEqual((metrics['tp'],metrics['fp'],metrics['fn']),(1,1,1))
        self.assertEqual(metrics['precision'],.5)
        self.assertEqual(metrics['recall'],.5)

    def test_switches_are_not_counted_across_camera_resets(self):
        prediction,truth=fixture()
        prediction['frames'][1]['players'][0]['id']=12
        self.assertEqual(score_ground_truth(prediction,truth,'fixture')['sampled_identity_switches_within_scene'],1)
        prediction['frames'][1]['camera']['scene']=1
        self.assertEqual(score_ground_truth(prediction,truth,'fixture')['sampled_identity_switches_within_scene'],0)

    def test_review_and_source_guards(self):
        prediction,truth=fixture()
        with self.assertRaises(ValueError):score_ground_truth(prediction,truth,'wrong-video')
        truth['frames'][0]['reviewed']=False
        with self.assertRaises(ValueError):score_ground_truth(prediction,truth,'fixture')
        truth['frames'][0]['reviewed']=True
        truth['frames'][0]['fully_annotated']=False
        with self.assertRaises(ValueError):validate_ground_truth(truth,'fixture')

    def test_assignment_is_one_to_one_and_role_accuracy_separate(self):
        prediction,truth=fixture()
        prediction['frames'][0]['players'][0]['role']='referee'
        result=score_ground_truth(prediction,truth,'fixture')
        self.assertEqual(result['localization']['persons']['tp'],2)
        self.assertEqual(result['role_accuracy_on_matches'],.5)
        obj={'role':'player','bbox':[.1,.1,.3,.5]}
        self.assertEqual(len(match_objects([obj,obj],[obj],.5)),1)

    def test_interpolated_ball_is_not_scored_as_observed(self):
        prediction,truth=fixture()
        prediction['frames'][0]['ball']={'x':.2,'y':.2,'w':.02,'h':.02,'observed':False}
        truth['frames'][0]['objects'].append({'id':None,'role':'ball','bbox':[.19,.19,.21,.21]})
        result=score_ground_truth(prediction,truth,'fixture')
        self.assertEqual(result['localization']['ball']['fn'],1)
        self.assertEqual(result['localization']['ball']['tp'],0)
        self.assertEqual(diagnostics(prediction)['interpolated_ball_frames'],1)

    def test_timing_mismatch_is_rejected(self):
        prediction,truth=fixture()
        truth['frames'][1]['t']=10
        with self.assertRaises(ValueError):score_ground_truth(prediction,truth,'fixture')
        truth['frames'][1]['t']=.01
        with self.assertRaises(ValueError):score_ground_truth(prediction,truth,'fixture')

    def test_unprocessed_midpoint_timestamp_is_rejected(self):
        prediction,truth=fixture()
        prediction['stride']=2
        prediction['frames']=[prediction['frames'][0],{**prediction['frames'][1],'t':.2}]
        truth['frames'][1]['t']=.1
        with self.assertRaises(ValueError):score_ground_truth(prediction,truth,'fixture')

    def test_invalid_labels_are_rejected(self):
        _,truth=fixture()
        for box in ([.4,.2,.3,.8],[float('nan'),0,1,1],[0,0,2,1]):
            invalid=copy.deepcopy(truth);invalid['frames'][0]['objects'][0]['bbox']=box
            with self.assertRaises(ValueError):validate_ground_truth(invalid,'fixture')
        invalid=copy.deepcopy(truth);invalid['frames'][0]['objects']*=2
        with self.assertRaises(ValueError):validate_ground_truth(invalid,'fixture')
        self.assertEqual(box_iou([0,0,1,1],[2,2,3,3]),0)
        for invalid in (None, {'schema':'touchline-groundtruth-v1','source_sha256':'fixture','frames':[None]}):
            with self.assertRaises(ValueError):validate_ground_truth(invalid,'fixture')

if __name__=='__main__':unittest.main()
