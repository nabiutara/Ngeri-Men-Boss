'use strict';

// Presentation only: never modify detections or saved tracking coordinates.
var FootMarkers = (() => {
  const positions = new Map();
  let previousTime = null;

  function begin(time, playing, scene) {
    const delta = previousTime === null ? 0 : time - previousTime;
    if (!playing || delta < 0 || delta > 0.25) positions.clear();
    previousTime = time;
    return {delta: Math.max(0, delta), scene};
  }

  function position(id, target, radius, motion) {
    const key = `${motion.scene}:${id}`;
    const old = positions.get(key);
    // Video time often repeats between display refreshes. Hold the last rendered
    // point rather than alternating between the smoothed and raw coordinates.
    if (old && motion.delta === 0) return {x: old.x, y: old.y};
    let x = target.x, y = target.y;
    if (old && motion.delta > 0 && Math.hypot(x-old.x, y-old.y) < radius*2) {
      const weight = 1-Math.exp(-motion.delta*24);
      x = old.x+(x-old.x)*weight;
      y = old.y+(y-old.y)*weight;
      // Keep any smoothing lag within a small fraction of the marker width.
      const distance = Math.hypot(target.x-x, target.y-y);
      const maximum = radius*0.08;
      if (distance > maximum) {
        x = target.x+(x-target.x)*maximum/distance;
        y = target.y+(y-target.y)*maximum/distance;
      }
    }
    positions.set(key, {x, y});
    return {x, y};
  }

  function unique(players, teamOf = p => p.team, keepVisible = () => false) {
    // Saved results may predate detector deduplication. Filter markers only;
    // retain every source track for inspection and manual correction.
    const byId = new Map();
    for (const p of players) {
      const old = byId.get(p.id);
      if (!old || (p.conf || 0) > (old.conf || 0)) byId.set(p.id, p);
    }
    const kept = [];
    const ordered = [...byId.values()].sort((a,b) => b.w*b.h-a.w*a.h || (b.conf||0)-(a.conf||0) || a.id-b.id);
    for (const p of ordered) {
      const duplicate = kept.some(q => {
        if (keepVisible(p) || keepVisible(q)) return false;
        // Proximity alone cannot distinguish two players during a challenge.
        const team = teamOf(p), otherTeam = teamOf(q);
        const opposing = team && otherTeam && team !== 'neutral' && otherTeam !== 'neutral' && team !== otherTeam;
        const intersection = Math.max(0,Math.min(p.x+p.w/2,q.x+q.w/2)-Math.max(p.x-p.w/2,q.x-q.w/2)) *
          Math.max(0,Math.min(p.y,q.y)-Math.max(p.y-p.h,q.y-q.h));
        const area = p.w*p.h, otherArea = q.w*q.h;
        if (!(area > 0 && otherArea > 0)) return false;
        const iou = intersection/(area+otherArea-intersection);
        const height = Math.max(p.h,q.h);
        const aligned = Math.abs(p.x-q.x) <= Math.min(p.w,q.w)*0.3;
        const sameFeet = Math.abs(p.y-q.y) <= height*0.12;
        const sameHead = Math.abs((p.y-p.h)-(q.y-q.h)) <= height*0.08;
        // MATCH1 contains torso-only duplicates: same head, shorter box, and a
        // false foot anchor at the knee. Automatic kit groups can disagree.
        // Require near containment and aligned bodies, not just nearby feet.
        const partialBody = intersection/Math.min(area,otherArea) >= 0.95 &&
          Math.min(p.h,q.h)/height <= 0.9 && (sameFeet || sameHead) &&
          Math.abs(p.y-q.y) <= height*0.35;
        return aligned && (partialBody || (!opposing && sameFeet && iou >= 0.65));
      });
      if (!duplicate) kept.push(p);
    }
    const selected = new Set(kept);
    return [...byId.values()].filter(p => selected.has(p));
  }

  function draw(context, point, radius, color, time = 0) {
    context.save();
    context.translate(point.x, point.y+2);
    // A fixed gap at the rear center leaves room for the player's legs while
    // the single ellipse sits on the ground plane.
    context.beginPath();
    context.rect(-radius-12, -radius-12, radius*2+24, radius*2+24);
    context.rect(-radius*0.29, -radius-12, radius*0.58, radius+12);
    context.clip('evenodd');
    context.strokeStyle = color;
    context.lineCap = 'round';
    context.lineWidth = 1.5;
    context.shadowColor = color;
    context.shadowBlur = 5;
    // Three arcs on ONE ellipse. Phase follows video time, so pause, seek and
    // export reproduce the same ring, independent of display refresh rate.
    const phase = (time*0.7) % (Math.PI*2), sector = Math.PI*2/3;
    for (let segment=0; segment<3; segment++) {
      const start = phase+segment*sector;
      context.beginPath();
      context.ellipse(0, 0, radius, radius*0.34, 0, start+0.16, start+sector-0.16);
      context.stroke();
    }
    context.restore();
  }

  function finish(visibleIds, scene) {
    const visible = new Set(visibleIds.map(id => `${scene}:${id}`));
    for (const key of positions.keys()) if (!visible.has(key)) positions.delete(key);
  }

  return {begin, position, unique, draw, finish};
})();
