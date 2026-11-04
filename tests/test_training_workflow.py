import base64
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from training_workflow import TrainingWorkflow
from football_engine import TeamColors


def packet(source='a', match='match-a', split='train', pixel=20):
    image=np.full((80,120,3),pixel,np.uint8)
    ok,encoded=cv2.imencode('.jpg',image)
    assert ok
    objects=[{'id':i,'role':role,'team':'neutral','bbox':[.1,.1,.3,.8]}
             for i,role in enumerate(('ball','goalkeeper','player','referee'))]
    return {'source_sha256':source*64,'source_name':'match.mp4','match_id':match,'split':split,
            'width':120,'height':80,'image_base64':base64.b64encode(encoded).decode(),
            'frame':{'t':0,'reviewed':True,'fully_annotated':True,'objects':objects}}


class ReviewedTrainingTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.workflow=TrainingWorkflow(self.root/'training',self.root/'models')

    def test_review_and_image_identity_are_required(self):
        data=packet();data['frame']['reviewed']=False
        with self.assertRaisesRegex(ValueError,'reviewed'):self.workflow.save_frame(data)
        data=packet();data['width']=121
        with self.assertRaisesRegex(ValueError,'dimensions'):self.workflow.save_frame(data)
        data=packet();data['image_base64']='not-a-jpeg'
        with self.assertRaises(ValueError):self.workflow.save_frame(data)
        self.assertEqual(self.workflow.records(),[])

    def test_match_and_content_leakage_are_rejected(self):
        self.workflow.save_frame(packet())
        with self.assertRaisesRegex(ValueError,'match already'):self.workflow.save_frame(packet('b','match-a','val',90))
        with self.assertRaisesRegex(ValueError,'video already'):self.workflow.save_frame(packet('a','renamed','val',90))
        with self.assertRaisesRegex(ValueError,'Identical'):self.workflow.save_frame(packet('b','other','val',20))

    def test_complete_snapshot_preserves_roles_backgrounds_and_labels(self):
        self.workflow.save_frame(packet())
        self.workflow.save_frame(packet('b','match-b','val',90))
        background=packet('a','match-a','train',50);background['frame']['t']=1;background['frame']['objects']=[]
        self.workflow.save_frame(background)
        self.assertTrue(self.workflow.summary()['ready'])
        target=self.workflow.build_dataset('snapshot')
        labels=sorted((target/'labels'/'train').glob('*.txt'))
        self.assertEqual(len(labels),2)
        labeled=[p.read_text() for p in labels if p.read_text()][0]
        self.assertEqual([line.split()[0] for line in labeled.splitlines()],['0','1','2','3'])
        self.assertIn('0.20000000 0.45000000 0.20000000 0.70000000',labeled)
        before=(target/'provenance.json').read_bytes()
        self.workflow.delete_frame('a'*64+'-000000000000')
        self.assertEqual(before,(target/'provenance.json').read_bytes())
        self.assertEqual(len(list((target/'images'/'train').glob('*.jpg'))),2)

    def test_training_requires_class_coverage_and_valid_settings(self):
        self.workflow.save_frame(packet())
        data=packet('b','match-b','val',90);data['frame']['objects']=data['frame']['objects'][2:3]
        self.workflow.save_frame(data)
        self.assertFalse(self.workflow.summary()['ready'])
        with self.assertRaisesRegex(ValueError,'all four'):self.workflow.build_dataset('no-coverage')
        with self.assertRaisesRegex(ValueError,'settings'):self.workflow.start({'epochs':True})

    def test_palette_uses_distinct_reviewed_outfield_identities(self):
        data=packet();data['frame']['objects']=[]
        for team,color in [('home','#ee2211'),('away','#1144ee')]:
            for i in range(3):data['frame']['objects'].append({'id':i+(0 if team=='home' else 3),'role':'player','team':team,'bbox':[.1,.1,.3,.8],'kit_color':color})
        self.workflow.save_frame(data)
        palette=self.workflow.reviewed_palette('a'*64)
        self.assertEqual(palette,{'home':'#ee2211','away':'#1144ee'})
        self.assertIsNone(self.workflow.reviewed_palette('b'*64))
        colors=TeamColors()
        for identity,hexcolor in [(1,palette['home']),(2,palette['away'])]:
            rgb=np.uint8([[[int(hexcolor[i:i+2],16) for i in (1,3,5)]]])
            lab=cv2.cvtColor(rgb,cv2.COLOR_RGB2LAB)[0,0]
            for _ in range(3):colors.add(identity,lab)
        assignments,_=colors.fit(palette)
        self.assertEqual(assignments[1]['team'],'home')
        self.assertEqual(assignments[2]['team'],'away')
        self.assertEqual(colors.fit({'home':'#eeeeee','away':'#eeeeee'})[0],{})

    def test_candidate_uses_best_and_keeps_the_active_checkpoint(self):
        self.workflow.save_frame(packet());self.workflow.save_frame(packet('b','match-b','val',90))
        job='1'*32;dataset=self.workflow.build_dataset(job)
        active=self.root/'active.pt';active.write_bytes(b'verified-baseline-fixture')
        active_hash=hashlib.sha256(active.read_bytes()).hexdigest()
        self.workflow.jobs[job]={'id':job,'status':'queued','settings':{'epochs':1,'imgsz':640,'batch':1},'cancel':threading.Event()}
        class Model:
            names={0:'ball',1:'goalkeeper',2:'player',3:'referee'}
            def __init__(self,path):self.path=path
            def add_callback(self,*_):pass
            def val(self,**kwargs):
                class Result:results_dict={'metrics/mAP50-95(B)':.2 if 'active.pt' in str(self.path) else .3}
                return Result()
            def train(self,**kwargs):
                weights=Path(kwargs['project'])/kwargs['name']/'weights';weights.mkdir(parents=True)
                (weights/'best.pt').write_bytes(b'validation-selected-candidate')
                (weights/'last.pt').write_bytes(b'last-checkpoint')
        with patch('football_engine.resolve_model',return_value=active),patch('ultralytics.YOLO',side_effect=Model),patch('importlib.metadata.version',return_value='fixture'):
            self.workflow._train(job,dataset)
        result=self.workflow.jobs[job]
        self.assertEqual(result['status'],'completed',result.get('error'))
        self.assertEqual(active_hash,hashlib.sha256(active.read_bytes()).hexdigest())
        manifest=result['manifest']
        self.assertEqual(manifest['candidate_sha256'],hashlib.sha256(b'validation-selected-candidate').hexdigest())
        self.assertEqual(manifest['promotion'],'disabled-candidate-only')
        self.assertEqual(manifest['test_set'],'untouched')
        restored=TrainingWorkflow(self.workflow.root,self.workflow.models)
        self.assertEqual(restored.jobs[job]['status'],'completed')


if __name__=='__main__':unittest.main()
