import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import cv2
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from prepare_training import export_dataset, validate_plan


class TrainingExportTests(unittest.TestCase):
    def test_match_leakage_is_rejected(self):
        records=[{'match_id':'same-match','split':split,'video':'x','ground_truth':'y'} for split in ('train','val')]
        with self.assertRaises(ValueError):validate_plan({'schema':'touchline-dataset-plan-v1','clips':records})

    def test_missing_validation_group_is_rejected(self):
        with self.assertRaises(ValueError):validate_plan({'schema':'touchline-dataset-plan-v1','clips':[{'match_id':'a','split':'train','video':'x','ground_truth':'y'}]})

    def test_reviewed_export_preserves_classes_and_source_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);records=[]
            for i,split in enumerate(('train','val')):
                video=root/f'{split}.avi'
                writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'MJPG'),20,(80,80))
                self.assertTrue(writer.isOpened())
                writer.write(np.full((80,80,3),40+i*100,np.uint8));writer.release()
                with video.open('rb') as handle:digest=hashlib.file_digest(handle,'sha256').hexdigest()
                label={'schema':'touchline-groundtruth-v1','source_sha256':digest,'match_id':split,
                       'frames':[{'t':0,'reviewed':True,'fully_annotated':True,'objects':[{'id':1,'role':'player','bbox':[.25,.25,.75,.75]}]}]}
                label_path=root/f'{split}.json';label_path.write_text(json.dumps(label))
                records.append({'match_id':split,'split':split,'video':video.name,'ground_truth':label_path.name})
            plan=root/'plan.json';plan.write_text(json.dumps({'schema':'touchline-dataset-plan-v1','clips':records}))
            destination=root/'dataset'
            self.assertEqual(export_dataset(plan,destination),2)
            self.assertTrue((destination/'COMPLETE').exists())
            for split in ('train','val'):
                files=list((destination/'labels'/split).glob('*.txt'))
                self.assertEqual(len(files),1)
                self.assertEqual(files[0].read_text(),'2 0.50000000 0.50000000 0.50000000 0.50000000')
            provenance=json.loads((destination/'provenance.json').read_text())
            self.assertEqual({r['match_id'] for r in provenance['frames']},{'train','val'})
            with self.assertRaises(ValueError):export_dataset(plan,destination)
            # Identical content cannot be disguised as another match across splits.
            records[1]['video']=records[0]['video']
            plan.write_text(json.dumps({'schema':'touchline-dataset-plan-v1','clips':records}))
            with self.assertRaises(ValueError):export_dataset(plan,root/'leaked')
            self.assertFalse((root/'leaked').exists())

if __name__=='__main__':unittest.main()
