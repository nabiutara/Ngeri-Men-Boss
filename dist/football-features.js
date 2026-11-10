'use strict';
// Extended results remain compatible with existing Touchline project files.
function frameAt(t){const i=frameIndex(t);return i>=0?frames[i]:null;}
function validateCamera(c){return !!c&&Number.isInteger(c.scene)&&c.scene>=0&&Array.isArray(c.to_reference)&&c.to_reference.length===9&&c.to_reference.every(Number.isFinite)&&Math.abs(determinant3(c.to_reference))>1e-10;}
function determinant3(m){return m[0]*(m[4]*m[8]-m[5]*m[7])-m[1]*(m[3]*m[8]-m[5]*m[6])+m[2]*(m[3]*m[7]-m[4]*m[6]);}
function inverse3(m){const d=determinant3(m);if(Math.abs(d)<1e-10)return null;return [(m[4]*m[8]-m[5]*m[7])/d,(m[2]*m[7]-m[1]*m[8])/d,(m[1]*m[5]-m[2]*m[4])/d,(m[5]*m[6]-m[3]*m[8])/d,(m[0]*m[8]-m[2]*m[6])/d,(m[2]*m[3]-m[0]*m[5])/d,(m[3]*m[7]-m[4]*m[6])/d,(m[1]*m[6]-m[0]*m[7])/d,(m[0]*m[4]-m[1]*m[3])/d];}
function transform3(m,p){const d=m[6]*p.x+m[7]*p.y+m[8];if(Math.abs(d)<1e-10)return null;return {x:(m[0]*p.x+m[1]*p.y+m[2])/d,y:(m[3]*p.x+m[4]*p.y+m[5])/d};}
function trackingCameraAt(t){const c=frameAt(t)?.camera;return validateCamera(c)?JSON.parse(JSON.stringify(c)):null;}
function sameTrackingScene(a,b){return frameAt(a)?.camera?.scene===frameAt(b)?.camera?.scene;}
function calibrationUsable(){if(!state.calibration)return false;if(!trackMeta?.engine_version||trackMeta.engine_version<2)return true;const anchor=state.calibration.camera,now=frameAt(time)?.camera;return validateCamera(anchor)&&validateCamera(now)&&anchor.scene===now.scene;}
function calibratedPosition(p){if(!calibrationUsable())return null;let point={x:p.x,y:p.y};const anchor=state.calibration.camera,now=frameAt(time)?.camera;if(anchor&&now){const ref=transform3(now.to_reference,point),inverse=inverse3(anchor.to_reference);if(!ref||!inverse)return null;point=transform3(inverse,ref);if(!point)return null;}const r=contentRect();return projectPoint(state.calibration.homography,(r.x+point.x*r.w)/1280,(r.y+point.y*r.h)/720);}
function drawBallMarker(){if(state.demo||!state.settings.showBall||needsRelink)return;const f=frameAt(time),b=f?.ball;if(!b||time-f.t>Math.max(.5,(trackMeta?.stride||1)/(trackMeta?.fps||25)*2))return;const r=contentRect(),x=r.x+b.x*r.w,y=r.y+b.y*r.h,radius=Math.max(6,b.w*r.w*.65);ctx.save();ctx.globalAlpha=state.settings.overlayOpacity/100;ctx.strokeStyle='#fff1b1';ctx.lineWidth=2;if(!b.observed)ctx.setLineDash([3,3]);ctx.beginPath();ctx.arc(x,y,radius,0,Math.PI*2);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#fff1b1';ctx.beginPath();ctx.moveTo(x,y-radius-5);ctx.lineTo(x-5,y-radius-13);ctx.lineTo(x+5,y-radius-13);ctx.closePath();ctx.fill();ctx.restore();}
// Offline queries must use each sample's camera, never the current playhead.
// Require camera metadata even for legacy tracks: an unknown shot is not safe to map.
function patternProjector(calibration,rect){
 const anchor=calibration?.camera;
 if(!validateCamera(anchor)||!Array.isArray(calibration?.homography)||calibration.homography.length!==8||!calibration.homography.every(Number.isFinite))throw Error('Calibrate a tracked camera scene before searching patterns. Legacy tracks without camera metadata must be analyzed again.');
 const inverse=inverse3(anchor.to_reference);
 return (p,frame,info)=>{
  const camera=frame.camera;
  if(!validateCamera(camera)||camera.scene!==anchor.scene)return null;
  const point={x:p.x+p.w*(info.footX||0)/100,y:p.y+p.h*(info.footY||0)/100};
  const reference=transform3(camera.to_reference,point),relative=reference&&transform3(inverse,reference);
  if(!relative)return null;
  const q=projectPoint(calibration.homography,(rect.x+relative.x*rect.w)/1280,(rect.y+relative.y*rect.h)/720);
  return Number.isFinite(q.x)&&Number.isFinite(q.y)?q:null;
 };
}
function bindFootballControls(){
$('swapTeams').onclick=()=>{checkpoint();const ids=new Map();if(state.demo){for(const p of demoPlayers(time))ids.set(p.id,p);}else for(const f of frames)for(const p of f.players)if(!ids.has(p.id))ids.set(p.id,p);for(const p of ids.values()){const info=playerInfo(p);if(info.team==='home'||info.team==='away')playerEdit(p).team=info.team==='home'?'away':'home';}state.kitColorsSwapped=!state.kitColorsSwapped;updateSelection();autosave();toast('Home and away assignments swapped. Your overlay colors are unchanged.');};
$('useKitColors').onclick=()=>{const colors=trackMeta?.detected_team_colors;if(!colors?.home||!colors?.away){toast('Run football analysis with enough visible outfield players first.');return;}state.settings.homeColor=cleanColor(state.kitColorsSwapped?colors.away:colors.home);state.settings.awayColor=cleanColor(state.kitColorsSwapped?colors.home:colors.away);state.settings.useJerseyRingColors=false;updateSettings();autosave();toast('Applied the detected kit colors to all overlays.');};
}
