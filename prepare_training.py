"""Export reviewed labels to YOLO format with match-level split guards."""
from pathlib import Path
import argparse
import hashlib
import json

import cv2

from evaluation import validate_ground_truth

CLASSES = {'ball':0,'goalkeeper':1,'player':2,'referee':3}


def validate_plan(plan):
    if not isinstance(plan,dict):
        raise ValueError('A dataset plan must be an object')
    records=plan.get('clips')
    if plan.get('schema')!='touchline-dataset-plan-v1' or not isinstance(records,list) or not records:
        raise ValueError('A dataset plan needs a nonempty clips list')
    groups={}
    for record in records:
        if not isinstance(record,dict):
            raise ValueError('Every clip record must be an object')
        group=record.get('match_id')
        split=record.get('split')
        if not isinstance(group,str) or not group.strip() or split not in {'train','val','test'}:
            raise ValueError('Every clip needs an explicit match_id and train/val/test split')
        if group in groups and groups[group]!=split:
            raise ValueError('Data leakage: clips from one match cannot cross splits')
        groups[group]=split
        for key in ('video','ground_truth'):
            if not isinstance(record.get(key),str) or not record[key]:
                raise ValueError(f'Every clip needs a {key} path')
    if not {'train','val'}<=set(groups.values()):
        raise ValueError('Training data needs separate train and validation match groups')
    return records


def export_dataset(plan_path, output):
    plan_path=Path(plan_path).resolve();output=Path(output).resolve()
    if output.exists():raise ValueError('Choose a new output directory')
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    records=validate_plan(plan)
    verified=[];hash_groups={};seen_frames=set()
    # Preflight every source and label before creating a dataset.
    for record in records:
        source=(plan_path.parent/record['video']).resolve()
        label_path=(plan_path.parent/record['ground_truth']).resolve()
        with source.open('rb') as handle:source_hash=hashlib.file_digest(handle,'sha256').hexdigest()
        identity=(record['match_id'],record['split'])
        if source_hash in hash_groups and hash_groups[source_hash]!=identity:
            raise ValueError('Duplicate video content has inconsistent match groups or splits')
        hash_groups[source_hash]=identity
        truth=json.loads(label_path.read_text(encoding='utf-8'))
        validate_ground_truth(truth,source_hash)
        if truth.get('match_id')!=record['match_id']:raise ValueError('Label match_id does not match the plan')
        cap=cv2.VideoCapture(str(source))
        try:
            fps=cap.get(cv2.CAP_PROP_FPS);count=cap.get(cv2.CAP_PROP_FRAME_COUNT)
        finally:cap.release()
        if fps<=0 or count<=0:raise ValueError('Cannot read video timing')
        for frame in truth['frames']:
            number=round(frame['t']*fps)
            if not 0<=number<count:raise ValueError('Label timestamp is outside the video')
            key=(source_hash,number)
            if key in seen_frames:raise ValueError('The same source frame was included more than once')
            seen_frames.add(key)
        verified.append((record,source,source_hash,truth,fps))
    for split in ('train','val'):
        if not any(frame['objects'] for record,_,_,truth,_ in verified if record['split']==split for frame in truth['frames']):
            raise ValueError(f'The {split} split has no annotated objects')
    output.mkdir(parents=True)
    exported=[]
    try:
        for record,source,source_hash,truth,fps in verified:
            split=record['split']
            image_dir=output/'images'/split;label_dir=output/'labels'/split
            image_dir.mkdir(parents=True,exist_ok=True);label_dir.mkdir(parents=True,exist_ok=True)
            cap=cv2.VideoCapture(str(source))
            try:
                for frame in truth['frames']:
                    number=round(frame['t']*fps)
                    cap.set(cv2.CAP_PROP_POS_FRAMES,number);ok,image=cap.read()
                    if not ok:raise ValueError(f'Cannot decode source frame {number}')
                    stem=f'{source_hash}-{number:08d}'
                    if not cv2.imwrite(str(image_dir/(stem+'.jpg')),image):raise OSError('Could not write dataset image')
                    labels=[]
                    for obj in frame['objects']:
                        x1,y1,x2,y2=obj['bbox']
                        labels.append(f"{CLASSES[obj['role']]} {(x1+x2)/2:.8f} {(y1+y2)/2:.8f} {x2-x1:.8f} {y2-y1:.8f}")
                    (label_dir/(stem+'.txt')).write_text('\n'.join(labels),encoding='utf-8')
                    exported.append({'image':f'images/{split}/{stem}.jpg','match_id':record['match_id'],
                                     'source_sha256':source_hash,'source_frame':number,'split':split})
            finally:cap.release()
        # JSON-quoted paths are valid YAML scalars, including paths with spaces.
        config='path: '+json.dumps(str(output).replace('\\','/'))+'\ntrain: images/train\nval: images/val\n'
        if any(r['split']=='test' for r in records):config+='test: images/test\n'
        config+='names:\n'+''.join(f'  {number}: {role}\n' for role,number in CLASSES.items())
        (output/'data.yaml').write_text(config,encoding='utf-8')
        (output/'provenance.json').write_text(json.dumps({'schema':'touchline-training-export-v1','frames':exported},indent=2),encoding='utf-8')
        (output/'COMPLETE').write_text('Reviewed dataset export completed. Validate labels visually before training.\n',encoding='utf-8')
    except Exception:
        (output/'INCOMPLETE').write_text('Export failed. This directory must not be used for training.\n',encoding='utf-8')
        raise
    return len(exported)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        count=export_dataset(args.plan,args.output)
    except (OSError,ValueError) as error:
        parser.error(str(error))
    print(f'Exported {count} reviewed frames.')


if __name__=='__main__':main()
