"""Football analysis fundamentals, independently implemented for Touchline Studio.

Reference: nabiutara/football_analysis @ e4799632cdf271cf57f4eb0c4d872cf1b7ab0f17.
Uses Ultralytics' built-in ByteTrack/BoT-SORT instead of vendoring tracker code.
"""
from __future__ import annotations
from collections import defaultdict, deque
from itertools import islice
import hashlib
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

REPO_REVISION = "e4799632cdf271cf57f4eb0c4d872cf1b7ab0f17"
MODEL_ID = "1DC2kCygbBWUKheQ_9cFziCsYVSRw6axK"
# Populated from the verified upstream download before release.
MODEL_SHA256 = "53fcd08a5e5283d7bba705f07fc04022a6ab73a2ba2a847d3bc8143c9ecad2eb"
MODEL_NAMES = {"football-best.pt", "yolo26n.pt", "yolo26s.pt"}


def resolve_model(name: str, directory: Path, progress=None, cancel=None) -> Path:
    if name not in MODEL_NAMES:
        raise ValueError("Unsupported model")
    path = directory / name
    if name != "football-best.pt":
        return path
    if not path.exists():
        import gdown
        if progress:
            progress(0, "Downloading the football model (173 MB)…")
        temporary = path.with_suffix(".download")
        try:
            result = gdown.download(id=MODEL_ID, output=str(temporary), quiet=True, use_cookies=False)
            if not result:
                raise ValueError("The football model download is unavailable. Choose a YOLO26 fallback.")
            if cancel and cancel.is_set():
                raise InterruptedError("Analysis cancelled")
            with temporary.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            if digest != MODEL_SHA256:
                raise ValueError("Football model checksum mismatch; the upstream file may have changed.")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    with path.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != MODEL_SHA256:
            raise ValueError("Football model checksum mismatch. Remove it and retry the download.")
    return path


def role_for(name):
    name = str(name).lower().replace("_", " ").replace("-", " ").strip()
    return {"player":"player", "person":"player", "goalkeeper":"goalkeeper",
            "goal keeper":"goalkeeper", "referee":"referee", "ball":"ball",
            "football":"ball", "sports ball":"ball"}.get(name)


def jersey_color(frame, bbox):
    """Cluster upper-body pixels in Lab, suppressing grass and crop-background corners."""
    height, width = frame.shape[:2]
    x1,y1,x2,y2 = map(float, bbox)
    w,h=x2-x1,y2-y1
    left,right=max(0,int(x1+.12*w)),min(width,int(x2-.12*w))
    top,bottom=max(0,int(y1+.16*h)),min(height,int(y1+.53*h))
    if right-left < 4 or bottom-top < 4:
        return None
    patch=cv2.resize(frame[top:bottom,left:right],(24,24),interpolation=cv2.INTER_AREA)
    lab=cv2.cvtColor(patch,cv2.COLOR_BGR2LAB).astype(np.float32)
    # Estimate the local background outside the box. A broad green-hue mask
    # would incorrectly remove green kits (including the repository's sample).
    context=[]
    for xa,xb in [(max(0,int(x1-.3*w)),max(0,int(x1))),
                  (min(width,int(x2)),min(width,int(x2+.3*w)))]:
        region=frame[max(0,int(y1)):min(height,int(y2)),xa:xb]
        if region.size:context.append(region.reshape(-1,3))
    if context:
        background=np.median(np.concatenate(context),axis=0).astype(np.uint8)
        background_lab=cv2.cvtColor(background.reshape(1,1,3),cv2.COLOR_BGR2LAB)[0,0].astype(np.float32)
        grass=np.linalg.norm(lab-background_lab,axis=2)<18
    else:
        grass=np.zeros((24,24),dtype=bool)
    pixels=lab.reshape(-1,3)
    cv2.setRNGSeed(31)
    _, labels, centers=cv2.kmeans(pixels,2,None,(cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,30,.3),3,cv2.KMEANS_PP_CENTERS)
    labels=labels.reshape(24,24)
    scores=[]
    for k in range(2):
        mask=(labels==k)&~grass
        # Jersey should occupy the torso center. Background dominance is not enough.
        scores.append(int(mask[4:20,5:19].sum())-.25*int((labels[[0,0,-1,-1],[0,-1,0,-1]]==k).sum()))
    chosen=int(np.argmax(scores))
    mask=(labels==chosen)&~grass
    if mask.sum()<24 or scores[chosen]<12:
        return None
    return np.median(lab[mask],axis=0)


class TeamColors:
    def __init__(self):
        self.samples=defaultdict(lambda:deque(maxlen=15))

    def add(self, track_id, color):
        if color is not None:
            self.samples[track_id].append(color)

    def fit(self, reviewed_palette=None):
        usable={i:np.median(s,axis=0) for i,s in self.samples.items() if len(s)>=3}
        if reviewed_palette:
            # Human team semantics are meaningful within this exact source video.
            names=['home','away'];centers=[]
            for team in names:
                color=reviewed_palette.get(team,'')
                if not isinstance(color,str) or len(color)!=7 or color[0]!='#':
                    raise ValueError('Invalid reviewed team palette')
                try:rgb=np.uint8([[[int(color[i:i+2],16) for i in (1,3,5)]]])
                except ValueError as error:raise ValueError('Invalid reviewed team palette') from error
                centers.append(cv2.cvtColor(rgb,cv2.COLOR_RGB2LAB)[0,0].astype(np.float32))
            centers=np.array(centers);separation=float(np.linalg.norm(centers[0]-centers[1]))
            assignments={}
            if separation>=20:
                for identity,color in usable.items():
                    distances=np.linalg.norm(centers-color,axis=1);best=int(np.argmin(distances))
                    margin=(float(max(distances))-float(min(distances)))/max(float(max(distances)),1.)
                    if margin>=.25 and float(min(distances))<min(65,separation*.65):
                        assignments[identity]={'team':names[best],'confidence':round(margin,3)}
            return assignments,dict(reviewed_palette)
        if len(usable)<6:
            return {}, {}
        data=np.array(list(usable.values()),dtype=np.float32)
        # Fit on a bounded, evenly distributed sample. A full match can produce
        # thousands of fragmented identities; an N-by-N matrix is unnecessary.
        if len(data)>512:
            rng=np.random.default_rng(23)
            data=data[np.sort(rng.choice(len(data),size=512,replace=False))]
        # Isolated dark uniforms / bad crops must not become one of the two teams.
        pairwise=np.linalg.norm(data[:,None,:]-data[None,:,:],axis=2)
        np.fill_diagonal(pairwise,np.inf)
        neighbor=np.sort(pairwise,axis=1)[:,1]
        core=data[neighbor<=max(30.,float(np.median(neighbor))*3)]
        if len(core)<6:
            return {}, {}
        cv2.setRNGSeed(23)
        _,labels,centers=cv2.kmeans(core,2,None,(cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,60,.1),10,cv2.KMEANS_PP_CENTERS)
        labels=labels.ravel()
        separation=float(np.linalg.norm(centers[0]-centers[1]))
        if separation<20 or min(np.bincount(labels,minlength=2))<3:
            return {}, {}
        # Color groups are deterministic; their home/away semantics are user-editable.
        order=np.argsort(centers[:,0])
        names={int(order[0]):"home",int(order[1]):"away"}
        assignments={}
        for i,color in usable.items():
            distances=np.linalg.norm(centers-color,axis=1)
            best=int(np.argmin(distances))
            margin=(float(max(distances))-float(min(distances)))/max(float(max(distances)),1.)
            if margin>=.25 and float(min(distances))<min(65,separation*.65):
                assignments[i]={"team":names[best],"confidence":round(margin,3)}
        palette={}
        for k,center in enumerate(centers):
            rgb=cv2.cvtColor(np.uint8([[np.clip(center,0,255)]]),cv2.COLOR_LAB2RGB)[0,0]
            palette[names[k]]='#'+''.join(f'{int(v):02x}' for v in rgb)
        return assignments,palette


def distinct_people(people, roles):
    """Suppress near-identical person boxes across detector roles before association.

    Ball candidates never enter this suppression. Keep the selected row's original
    role/index alignment; overlapping people below 0.70 IoU remain separate.
    """
    if not people:
        return [], []
    boxes=[[p[0],p[1],p[2]-p[0],p[3]-p[1]] for p in people]
    indices=cv2.dnn.NMSBoxes(boxes,[float(p[4]) for p in people],0.,.7)
    keep=sorted(np.asarray(indices).reshape(-1).tolist())
    return [people[i] for i in keep], [roles[i] for i in keep]


class CameraMotion:
    """RANSAC optical flow; each scene has a cumulative normalized reference plane.

    A failed motion estimate starts a new reference segment. Never carry a pitch
    calibration silently across a cut or an untrackable interval.
    """
    def __init__(self):
        self.previous=None
        self.previous_boxes=[]
        self.transform=np.eye(3)
        self.scene=0

    def update(self, frame, boxes):
        h,w=frame.shape[:2]
        scaled=(640,max(1,round(h*640/w)))
        gray=cv2.cvtColor(cv2.resize(frame,scaled),cv2.COLOR_BGR2GRAY)
        changed=False
        quality=1.
        reason="reference"
        if self.previous is not None:
            mask=np.full_like(self.previous,255)
            for b in self.previous_boxes:
                x1,y1,x2,y2=b
                cv2.rectangle(mask,(max(0,int(x1*640/w)-5),max(0,int(y1*640/w)-5)),
                              (int(x2*640/w)+5,int(y2*640/w)+5),0,-1)
            points=cv2.goodFeaturesToTrack(self.previous,maxCorners=350,qualityLevel=.015,minDistance=8,mask=mask)
            affine=None
            if points is not None and len(points)>=12:
                new,status,_=cv2.calcOpticalFlowPyrLK(self.previous,gray,points,None,winSize=(21,21),maxLevel=3)
                if new is not None:
                    back,back_status,_=cv2.calcOpticalFlowPyrLK(gray,self.previous,new,None,winSize=(21,21),maxLevel=3)
                    if back is not None:
                        good=(status.ravel()==1)&(back_status.ravel()==1)&(np.linalg.norm(points-back,axis=2).ravel()<1.5)
                        if good.sum()>=12:
                            affine,inliers=cv2.estimateAffinePartial2D(points[good],new[good],method=cv2.RANSAC,ransacReprojThreshold=2,maxIters=2000)
                            quality=float(inliers.mean()) if inliers is not None else 0
            if affine is not None:
                scale=float(np.hypot(affine[0,0],affine[1,0]))
                displacement=float(np.linalg.norm(affine[:,2]))
                if quality<.55 or not .85<scale<1.18 or displacement>160:
                    affine=None
            if affine is None and float(cv2.absdiff(self.previous,gray).mean())<.15:
                affine=np.array([[1.,0.,0.],[0.,1.,0.]])
                quality=1.
            if affine is None:
                self.scene+=1
                self.transform=np.eye(3)
                changed=True
                quality=0.
                reason="cut-or-motion-lost"
            else:
                step=np.eye(3);step[:2]=affine
                norm=np.diag([scaled[0],scaled[1],1.])
                normalized=np.linalg.inv(norm)@step@norm
                candidate=normalized@self.transform
                det=float(np.linalg.det(candidate))
                scale=float(np.hypot(candidate[0,0],candidate[1,0]))
                if not np.all(np.isfinite(candidate)) or abs(det)<.05 or abs(det)>20. or not .3<scale<3.:
                    self.scene+=1
                    self.transform=np.eye(3)
                    changed=True
                    quality=0.
                    reason="drift-reset"
                else:
                    self.transform=candidate;reason="optical-flow"

        self.previous=gray
        self.previous_boxes=boxes
        try:
            inverse=np.linalg.inv(self.transform)
        except np.linalg.LinAlgError:
            self.scene+=1;inverse=np.eye(3);self.transform=np.eye(3);changed=True;quality=0
        return {"scene":self.scene,"to_reference":inverse.round(9).ravel().tolist(),
                "quality":round(quality,3),"reset":changed,"method":reason}


class BallHistory:
    """Interpolate short, bracketed gaps only. Never fill leading/trailing absences."""
    def __init__(self, max_gap=.4):
        self.previous=None
        self.max_gap=max_gap

    def choose(self, detections, timestamp, scene):
        if not detections:
            return None
        dt=max(0.,float(timestamp-self.previous[0])) if self.previous else 0.
        if self.previous and self.previous[2]==scene and dt<self.max_gap:
            old=self.previous[1]
            max_radius=min(.35,max(.08,.65*dt+.04))
            candidates=[b for b in detections if math.hypot(b['x']-old['x'],b['y']-old['y'])<max_radius]
            if not candidates:
                return None
            best=min(candidates,key=lambda b:math.hypot(b['x']-old['x'],b['y']-old['y'])/max_radius-.15*b['conf'])
        else:
            best=max(detections,key=lambda b:b['conf'])
        self.previous=(timestamp,best,scene)
        return {**best,"observed":True}


def bounded_ball_fill(buffer):
    """Flush-time interpolation on a short lookahead buffer, preserving scene cuts."""
    if not buffer or buffer[0].get('ball') is not None:
        return
    # The caller attaches its last observed sample as interpolation context.
    left=buffer[0].get('_left_ball')
    right=next((f for f in islice(buffer,1,None) if f.get('ball') and f['camera']['scene']==buffer[0]['camera']['scene']),None)
    if left is None or right is None or right['t']-left['t']>.4 or left['scene']!=right['camera']['scene']:
        return
    ratio=(buffer[0]['t']-left['t'])/(right['t']-left['t'])
    if not 0<ratio<1:
        return
    a,b=left['ball'],right['ball']
    buffer[0]['ball']={key:round(a[key]+(b[key]-a[key])*ratio,6) for key in ('x','y','w','h')}
    buffer[0]['ball'].update(conf=min(a['conf'],b['conf']),observed=False)


def track_football(source, output, *, models_dir, model_name="football-best.pt", confidence=.1,
                   stride=1, tracker_name="botsort", imgsz=960, source_name=None,
                   progress=None, cancel=None, reviewed_palette=None, source_sha256=None):
    import torch
    os.environ["ULTRALYTICS_SAFE_LOAD"]="1"
    from ultralytics import YOLO
    from ultralytics.engine.results import Boxes
    from ultralytics.trackers.byte_tracker import BYTETracker
    from ultralytics.trackers.bot_sort import BOTSORT

    def check_cancel():
        if cancel and cancel.is_set():
            raise InterruptedError("Analysis cancelled")

    if tracker_name not in {'bytetrack','botsort'}:
        raise ValueError('Unsupported tracker')
    if stride not in {1,2,3} or imgsz not in {640,960,1280} or not .05<=confidence<=.9:
        raise ValueError('Invalid analysis settings')
    cap=cv2.VideoCapture(str(source))
    try:
        fps=float(cap.get(cv2.CAP_PROP_FPS));count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if not cap.isOpened() or not math.isfinite(fps) or fps<=0 or min(width,height,count)<=0:
            raise ValueError('The video cannot be decoded or has invalid timing')
    finally:
        cap.release()
    if count/fps>4*3600 or count/stride>250000:
        raise ValueError('Use a shorter clip or larger frame stride')
    check_cancel()
    path=resolve_model(model_name,models_dir,progress,cancel)
    if progress:progress(0,'Loading football analysis model…')
    model=YOLO(str(path))
    class_roles={int(k):role_for(v) for k,v in model.names.items()}
    classes=[k for k,v in class_roles.items() if v]
    if not any(v in {'player','goalkeeper'} for v in class_roles.values()):
        raise ValueError('This checkpoint has no player/person classes')
    device=0 if torch.cuda.is_available() else 'cpu'
    cfg=SimpleNamespace(track_high_thresh=max(.25,confidence),track_low_thresh=.1,
                        new_track_thresh=max(.25,confidence),track_buffer=max(5,round(fps/stride)),
                        match_thresh=.8,fuse_score=False,gmc_method='sparseOptFlow',
                        proximity_thresh=.5,appearance_thresh=.8,with_reid=False,model='auto')
    tracker=(BYTETracker if tracker_name=='bytetrack' else BOTSORT)(cfg)
    camera=CameraMotion();teams=TeamColors();balls=BallHistory();ids={};next_id=1;processed=0;cuts=0
    metadata={'schema':'touchline-tracks-v1','engine_version':3,'source_name':source_name or source.name,
              'fps':fps,'stride':stride,'width':width,'height':height,'duration':count/fps,
              'model':model_name,'tracker':tracker_name,'imgsz':imgsz,'device':str(device),
              'association_space':'image-with-botsort-gmc' if tracker_name=='botsort' else 'image',
              'person_duplicate_iou':.7,'score_fusion':False,
              'class_names':model.names,'coordinate_system':'normalized-bottom-center',
              'reference_repository':'nabiutara/football_analysis','reference_commit':REPO_REVISION}
    if source_sha256:metadata['source_sha256']=source_sha256
    spool=output.with_suffix('.frames.ndjson');partial=output.with_suffix('.partial')
    stream=model.predict(str(source),stream=True,classes=classes,conf=confidence,imgsz=imgsz,
                         vid_stride=stride,device=device,verbose=False,save=False,max_det=100)
    try:
        with spool.open('w',encoding='utf-8') as handle:
            for result in stream:
                check_cancel();processed+=1
                timestamp=((processed-1)*stride)/fps
                raw=result.boxes.cpu().numpy().data if result.boxes is not None else np.empty((0,6),np.float32)
                people=[];roles=[];ball_detections=[]
                for row in raw:
                    role=class_roles.get(int(row[5]));x1,y1,x2,y2=map(float,row[:4]);score=float(row[4])
                    x1,x2=max(0,x1),min(width,x2);y1,y2=max(0,y1),min(height,y2)
                    if x2<=x1 or y2<=y1:continue
                    if role=='ball':
                        ball_detections.append({'x':(x1+x2)/2/width,'y':(y1+y2)/2/height,'w':(x2-x1)/width,'h':(y2-y1)/height,'conf':score})
                    elif role:
                        people.append([x1,y1,x2,y2,score,1 if role=='referee' else 0]);roles.append(role)
                people,roles=distinct_people(people,roles)
                motion=camera.update(result.orig_img,[p[:4] for p in people])
                if motion['reset']:
                    tracker.reset();ids={};cuts+=1
                detections=Boxes(np.asarray(people,dtype=np.float32).reshape(-1,6),(height,width))
                tracked=tracker.update(detections,result.orig_img)
                players=[]
                for row in tracked:
                    if len(row) < 5: continue
                    x1, y1, x2, y2 = map(float, row[:4])
                    local_id = int(row[4])
                    score = float(row[5]) if len(row) > 5 else 1.0
                    if len(row) >= 8: role = roles[int(row[7])] if 0 <= int(row[7]) < len(roles) else 'player'
                    elif len(row) == 7: role = roles[int(row[6])] if 0 <= int(row[6]) < len(roles) else 'player'
                    else: role = 'player'
                    x1,x2=max(0.,float(x1)),min(float(width),float(x2))
                    y1,y2=max(0.,float(y1)),min(float(height),float(y2))
                    if x2<=x1 or y2<=y1:continue

                    if local_id not in ids:ids[local_id]=next_id;next_id+=1
                    track_id=ids[local_id]
                    player={'id':track_id,'x':round(float((x1+x2)/2/width),6),'y':round(float(y2/height),6),
                            'w':round(float((x2-x1)/width),6),'h':round(float((y2-y1)/height),6),
                            'conf':round(float(score),4),'role':role}
                    players.append(player)
                    if role=='player' and processed%3==1:
                        teams.add(track_id,jersey_color(result.orig_img,(x1,y1,x2,y2)))
                record={'t':round(timestamp,6),'players':players,'camera':motion,
                        'ball':balls.choose(ball_detections,timestamp,motion['scene'])}
                handle.write(json.dumps(record,separators=(',',':'))+'\n')
                if progress and (processed%5==0 or processed==1):
                    pct=min(94,processed*stride/count*94)
                    progress(pct,f'Tracking football · {pct:.0f}% · {next_id-1} identities')
        if not processed:raise ValueError('No video frames could be decoded')
        check_cancel()
        assignments,palette=teams.fit(reviewed_palette)
        if progress:progress(95,'Grouping shirt colors and finalizing ball tracks…')
        metadata.update(track_count=next_id-1,team_assignments={str(k):v for k,v in assignments.items()},
                        detected_team_colors=palette,camera_resets=cuts,
                        team_assignment_method='reviewed-source-shirt-colors' if reviewed_palette else 'automatic-kit-clusters',
                        team_note='Reviewed shirt samples set home/away semantics for this video; uncertain tracks remain unassigned.' if reviewed_palette else 'Home/Away are kit-color groups. Review or swap them; goalkeeper teams remain manual.')
        with partial.open('w',encoding='utf-8') as out, spool.open(encoding='utf-8') as inp:
            out.write(json.dumps(metadata)[:-1]+',"frames":[')
            buffer=deque();left_ball=None;written=0
            def emit():
                nonlocal written
                check_cancel();bounded_ball_fill(buffer);record=buffer.popleft();record.pop('_left_ball',None)
                for p in record['players']:
                    a=assignments.get(p['id'])
                    p['team']=a['team'] if a and p['role']=='player' else 'neutral'
                    p['team_confidence']=a['confidence'] if a and p['role']=='player' else 0
                # A possession candidate is descriptive, never a fabricated carried-forward owner.
                ball=record.get('ball');record['possession_candidate']=None
                if ball and ball.get('observed'):
                    candidates=[p for p in record['players'] if p['role']!='referee' and
                                math.hypot((p['x']-ball['x'])*width,(p['y']-ball['y'])*height)<max(14,p['h']*height*.65)]
                    if candidates:
                        record['possession_candidate']=min(candidates,key=lambda p:math.hypot((p['x']-ball['x'])*width,(p['y']-ball['y'])*height))['id']
                if written:out.write(',')
                json.dump(record,out,separators=(',',':'));written+=1
            for line in inp:
                check_cancel();record=json.loads(line)
                if record['ball']:left_ball={'t':record['t'],'ball':record['ball'],'scene':record['camera']['scene']}
                else:record['_left_ball']=left_ball
                buffer.append(record)
                while buffer and record['t']-buffer[0]['t']>=.4:emit()
            while buffer:emit()
            out.write(']}')
        check_cancel();partial.replace(output)
        return {'track_count':next_id-1,'processed_frames':processed,'fps':fps,'duration':count/fps,
                'assigned_tracks':len(assignments),'camera_resets':cuts,'model':model_name}
    finally:
        stream.close();spool.unlink(missing_ok=True);partial.unlink(missing_ok=True)
