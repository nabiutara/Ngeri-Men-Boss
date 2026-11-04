"""Reproducible local comparisons; accuracy requires reviewed ground truth."""
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import time

import cv2
import torch

from evaluation import diagnostics, score_ground_truth
from server import MODELS, track_video

ROOT = Path(__file__).resolve().parent
PRESETS = [
    {'name':'football-byte-960', 'model_name':'football-best.pt', 'tracker_name':'bytetrack', 'imgsz':960, 'stride':2, 'confidence':.1},
    {'name':'football-byte-640', 'model_name':'football-best.pt', 'tracker_name':'bytetrack', 'imgsz':640, 'stride':2, 'confidence':.1},
    {'name':'football-botsort-960', 'model_name':'football-best.pt', 'tracker_name':'botsort', 'imgsz':960, 'stride':2, 'confidence':.1},
]


def digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def write_report(output, report):
    (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    lines=['# Touchline baseline comparison','',f"Match group: `{report['match_id']}`",'',
           f"Source: `{report['source']['filename']}` ({report['source']['duration_seconds']:.2f} seconds)",
           '', 'These are single-pass local measurements, including model setup and result finalization.',
           'Observation counts are not accuracy scores. No model is promoted automatically.', '',
           '| Case | Status | Wall seconds | Analyzed frames | Person tracks/frame (median) | Observed ball frames |',
           '| --- | --- | ---: | ---: | ---: | ---: |']
    for case in report['cases']:
        info=case.get('diagnostics',{})
        lines.append(f"| {case['name']} | {case['status']} | {case.get('wall_seconds','—')} | {info.get('processed_frames','—')} | {info.get('median_person_tracks_per_frame','—')} | {info.get('observed_ball_frames','—')} |")
    lines+=['','## Accuracy evidence','']
    if report.get('ground_truth_provided'):
        lines.append('Reviewed-label scores are recorded per case in report.json; inspect coverage and metric definitions before comparison.')
    else:
        lines.append('No reviewed ground truth was supplied. Detection accuracy, true identity switches, and team accuracy remain unmeasured.')
    lines+=['','## Next action','','Review the sampled images in review/. Fill groundtruth.template.json only with manual labels, marking each completed frame reviewed and fully annotated. Predictions are kept separately as suggestions, never treated as labels.','',
            'Use the same match_id for all clips from a match and keep that entire group in one future train/validation/test split.','']
    (output/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')


def review_packet(source, output, source_hash, match_id, predictions):
    folder=output/'review';folder.mkdir()
    frames=predictions['frames']
    if not frames:return
    chosen=sorted(set(round(i*(len(frames)-1)/5) for i in range(6)))
    labels=[];suggestions=[]
    capture=cv2.VideoCapture(str(source))
    try:
        for n,index in enumerate(chosen):
            record=frames[index]
            frame_number=round(record['t']*predictions['fps'])
            capture.set(cv2.CAP_PROP_POS_FRAMES,frame_number)
            ok,image=capture.read()
            if not ok:raise ValueError(f'Cannot extract review frame {frame_number}')
            filename=f'frame-{frame_number:06d}.jpg'
            if not cv2.imwrite(str(folder/filename),image):raise OSError('Could not write review image')
            labels.append({'t':record['t'],'image':filename,'frame_number':frame_number,
                           'reviewed':False,'fully_annotated':False,'objects':[]})
            suggestions.append({'t':record['t'],'prediction_frame':record})
    finally:capture.release()
    template={'schema':'touchline-groundtruth-v1','source_sha256':source_hash,'match_id':match_id,
              'bbox_format':'normalized xyxy','frames':labels}
    (folder/'groundtruth.template.json').write_text(json.dumps(template,indent=2),encoding='utf-8')
    (folder/'prediction-suggestions.json').write_text(json.dumps(suggestions,indent=2),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video',type=Path,required=True)
    parser.add_argument('--match-id',required=True,help='Use one group ID for every clip of the same match')
    parser.add_argument('--output',type=Path,required=True,help='A new directory; existing runs are never overwritten')
    parser.add_argument('--ground-truth',type=Path)
    parser.add_argument('--max-seconds',type=float,default=30,help='Reject longer inputs before starting three expensive runs; increase explicitly for a larger evaluation')
    parser.add_argument('--predictions',type=Path,help='Score/inspect saved results without repeating inference')
    args=parser.parse_args()
    source=args.video.resolve()
    if not source.is_file():parser.error('Video file does not exist')
    if args.output.exists():parser.error('Output directory already exists; choose a new run folder')
    cap=cv2.VideoCapture(str(source))
    try:
        fps=float(cap.get(cv2.CAP_PROP_FPS));count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:cap.release()
    if fps<=0 or count<=0:parser.error('Video timing cannot be read')
    if args.max_seconds<=0 or count/fps>args.max_seconds:parser.error('Use a shorter evaluation clip or explicitly increase --max-seconds')
    source_hash=digest(source)
    try:
        truth=json.loads(args.ground_truth.read_text(encoding='utf-8')) if args.ground_truth else None
        if args.ground_truth is not None:
            from evaluation import validate_ground_truth
            validate_ground_truth(truth,source_hash)
            if truth.get('match_id')!=args.match_id:raise ValueError('Ground-truth match group does not match')
    except (OSError,ValueError) as error:
        parser.error(str(error))
    output=args.output.resolve();output.mkdir(parents=True)
    report={'schema':'touchline-benchmark-v1','created_utc':datetime.now(timezone.utc).isoformat(),
            'match_id':args.match_id,'source':{'filename':source.name,'sha256':source_hash,'fps':fps,'frames':count,'width':width,'height':height,'duration_seconds':count/fps},
            'environment':{'python':platform.python_version(),'platform':platform.platform(),'processor':platform.processor(),'logical_cpus':os.cpu_count(),'cuda_available':torch.cuda.is_available(),
                           'packages':{name:version(name) for name in ('ultralytics','torch','torchvision','numpy','opencv-python','lap')}},
            'code_sha256':{name:digest(ROOT/name) for name in ('benchmark.py','evaluation.py','football_engine.py')},
            'ground_truth_provided':args.ground_truth is not None,'cases':[]}
    cases=[{'name':'saved-predictions'}] if args.predictions else PRESETS
    first=None
    for settings in cases:
        case={'name':settings['name'],'settings':{k:v for k,v in settings.items() if k!='name'}}
        report['cases'].append(case)
        print('Starting '+case['name'],flush=True)
        started=time.perf_counter()
        try:
            prediction_file=output/(case['name']+'.json')
            if args.predictions:
                data=json.loads(args.predictions.read_text(encoding='utf-8'))
                # Old results lack a source digest, so they cannot establish provenance.
                if data.get('source_sha256')!=source_hash:
                    raise ValueError('Saved predictions must include the exact source_sha256; run fresh inference first')
                case['wall_seconds']=None
            else:
                track_video(source,prediction_file,source_name=source.name,
                            **case['settings'],progress=lambda p,m:print('  '+m,flush=True))
                case['wall_seconds']=round(time.perf_counter()-started,3)
                data=json.loads(prediction_file.read_text(encoding='utf-8'))
                data['source_sha256']=source_hash
                prediction_file.write_text(json.dumps(data,separators=(',',':')),encoding='utf-8')
            if data.get('fps')!=fps or data.get('width')!=width or data.get('height')!=height:
                raise ValueError('Prediction dimensions/timing do not match the source')
            case['model_sha256']=digest(MODELS/data['model']) if (MODELS/data.get('model','')).is_file() else None
            case['diagnostics']=diagnostics(data)
            case['accuracy']=score_ground_truth(data,truth,source_hash) if truth else {'status':'not-measured-no-reviewed-labels'}
            case['status']='completed'
            case['result_file']=prediction_file.name if not args.predictions else str(args.predictions.resolve())
            if first is None:first=data
        except Exception as error:
            case.update(status='failed',error=str(error))
            print('  Failed: '+str(error),flush=True)
        write_report(output,report)
    if first is not None:review_packet(source,output,source_hash,args.match_id,first)
    write_report(output,report)
    print('Report saved: '+str(output/'REPORT.md'),flush=True)
    return 0 if all(case['status']=='completed' for case in report['cases']) else 1


if __name__=='__main__':raise SystemExit(main())
