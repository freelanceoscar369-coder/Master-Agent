/* The tree — Product Veda Deliverable 2 (Animation System).
 * Source: UX_03_Founder_Dashboard.html — THE NEURAL TREE implementation.
 * This is the authoritative silver/metallic Kalpavriksha tree visual.
 * Wrapped to match the expected KalpavrikshaTree class interface.
 */
'use strict';

// ---- TreeField: procedural branching structure with silver particles ----
function TreeField(canvas, opts) {
  opts = opts || {};
  var ctx = canvas.getContext('2d'), dpr = Math.min(window.devicePixelRatio || 1, 2);
  var W = 0, H = 0, parts = [], nodes = [], edges = [], t0 = performance.now(), assembled = 0;
  var COUNT = opts.count || 2400, MINI = !!opts.mini;
  var state = 'idle';
  // Phase 1 port (prominence.js) -- multiplies the breathing oscillation's
  // amplitude below; 1 = unchanged existing motion, set via
  // KalpavrikshaTree#setBreatheAmplitude() from --tree-breathe-amp.
  var breatheAmp = 1;

  function rnd(a, b) { return a + Math.random() * (b - a); }

  /* build a branching skeleton */
  function buildTree() {
    nodes = []; edges = [];
    var baseY = MINI ? 0.94 : 0.96, topLen = MINI ? 0.30 : 0.26;
    function branch(x, y, ang, len, depth, w) {
      if (depth <= 0 || len < 0.008) return;
      var segs = Math.max(2, Math.round(len * (MINI ? 30 : 46)));
      var px = x, py = y, pa = ang;
      for (var i = 0; i < segs; i++) {
        pa += rnd(-0.055, 0.055);
        var nx = px + Math.cos(pa) * (len / segs), ny = py + Math.sin(pa) * (len / segs);
        edges.push({x1: px, y1: py, x2: nx, y2: ny, d: depth, w: w});
        px = nx; py = ny;
      }
      nodes.push({x: px, y: py, d: depth});
      var n = depth > 4 ? 2 : (Math.random() < 0.72 ? 2 : 3);
      for (var k = 0; k < n; k++) {
        var spread = rnd(0.34, 0.78) * (k % 2 ? 1 : -1) * (1 + (3 - Math.min(depth, 3)) * 0.1);
        branch(px, py, pa + spread + rnd(-0.12, 0.12), len * rnd(0.60, 0.78), depth - 1, w * 0.68);
      }
    }
    branch(0.5, baseY, -Math.PI / 2, topLen, MINI ? 4 : 6, 2.2);
  }

  function seed() {
    parts = [];
    var n = MINI ? 260 : COUNT;
    for (var i = 0; i < n; i++) {
      var e = edges[(Math.random() * edges.length) | 0];
      var f = Math.random();
      var tx = e.x1 + (e.x2 - e.x1) * f, ty = e.y1 + (e.y2 - e.y1) * f;
      var jitter = 0.004 + (7 - e.d) * 0.0016;
      parts.push({
        tx: tx + rnd(-jitter, jitter), ty: ty + rnd(-jitter, jitter),
        x: 0.5 + rnd(-0.5, 0.5), y: 1.15 + rnd(-0.1, 0.35),
        ph: Math.random() * Math.PI * 2, sp: rnd(0.55, 1.5),
        d: e.d, s: rnd(0.5, 1.7), a: rnd(0.18, 0.85), del: Math.random() * 0.55
      });
    }
  }

  function resize() {
    var r = canvas.getBoundingClientRect();
    W = r.width; H = r.height;
    canvas.width = W * dpr; canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function frame(now) {
    var el = (now - t0) / 1000;
    assembled = Math.min(1, el / 2.4);
    var ease = 1 - Math.pow(1 - assembled, 3);
    ctx.clearRect(0, 0, W, H);

    var breathe = 1 + Math.sin(el * 1.05) * 0.012 * breatheAmp;
    var cx = W * 0.5, cy = H * (MINI ? 0.5 : 0.52);
    var thinking = state === 'thinking' ? (Math.sin(el * 3.1) * 0.5 + 0.5) : 0;

    /* faint branch filaments */
    ctx.lineCap = 'round';
    for (var i = 0; i < edges.length; i++) {
      var e = edges[i];
      var o = (0.080 + (7 - e.d) * 0.030) * ease;
      ctx.strokeStyle = 'rgba(180,225,255,' + o.toFixed(3) + ')';
      ctx.lineWidth = Math.max(0.8, e.w * 0.8);
      ctx.beginPath();
      ctx.moveTo(cx + (e.x1 - 0.5) * W * breathe, cy + (e.y1 - 0.52) * H * breathe);
      ctx.lineTo(cx + (e.x2 - 0.5) * W * breathe, cy + (e.y2 - 0.52) * H * breathe);
      ctx.stroke();
    }

    /* travelling pulse, root -> canopy */
    var pulseY = 1.0 - ((el * 0.30) % 1.35);

    for (var j = 0; j < parts.length; j++) {
      var p = parts[j];
      var pr = Math.max(0, Math.min(1, (ease - p.del) / (1 - p.del)));
      var wob = Math.sin(el * p.sp + p.ph) * 0.0032 * (1 + thinking * 3);
      var wob2 = Math.cos(el * p.sp * 0.7 + p.ph) * 0.0032 * (1 + thinking * 3);
      var gx = p.tx + wob, gy = p.ty + wob2;
      p.x += (gx - p.x) * (0.012 + pr * 0.055);
      p.y += (gy - p.y) * (0.012 + pr * 0.055);

      var sx = cx + (p.x - 0.5) * W * breathe, sy = cy + (p.y - 0.52) * H * breathe;
      var near = 1 - Math.min(1, Math.abs(p.ty - pulseY) / 0.10);
      var glow = near * near;
      var alpha = p.a * pr * (0.55 + 0.45 * Math.abs(Math.sin(el * 0.6 * p.sp + p.ph))) * (1 - thinking * 0.15);
      var size = p.s * (1 + glow * 1.5) * 1.25;

      if (glow > 0.02) {
        ctx.fillStyle = 'rgba(210,242,255,' + (alpha * glow * 0.95).toFixed(3) + ')';
        ctx.beginPath(); ctx.arc(sx, sy, size * 2.2, 0, 6.283); ctx.fill();
      }
      ctx.fillStyle = 'rgba(' + (glow > 0.3 ? '230,248,255' : '150,215,250') + ',' + alpha.toFixed(3) + ')';
      ctx.beginPath(); ctx.arc(sx, sy, size, 0, 6.283); ctx.fill();
    }
    requestAnimationFrame(frame);
  }

  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion:reduce)').matches;
  buildTree(); seed(); resize();
  window.addEventListener('resize', function() { resize(); });
  if (reduce) { t0 = performance.now() - 3000; ctx && frame(performance.now()); }
  else requestAnimationFrame(frame);

  return {
    setState: function(s) { state = s; },
    setBreatheAmplitude: function(x) { breatheAmp = x; },
    // Diagnostic: expose internal state for verification
    _debug: function() {
      return {
        W: W, H: H,
        edgesCount: edges.length,
        partsCount: parts.length,
        state: state,
        canvasWidth: canvas.width,
        canvasHeight: canvas.height,
        clientWidth: canvas.clientWidth,
        clientHeight: canvas.clientHeight
      };
    }
  };
}

// ---- KalpavrikshaTree class wrapper matching expected interface ----
class KalpavrikshaTree {
  constructor(canvas, opts) {
    this.canvas = canvas;
    this.opts = opts || {};
    this.treeField = null;
    this.seed = null;
    this.growthStart = null;
    this.reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    console.log('TREE_INIT', { canvas: !!canvas, opts: this.opts });
  }

  build(seed) {
    console.log('TREE_BUILD_STARTED', { seed });
    this.seed = seed >>> 0;
    // Pass count from opts or default
    const count = this.opts.count || 2400;
    this.treeField = TreeField(this.canvas, { count: count, mini: false });
    console.log('TREE_BUILD_COMPLETED', this.treeField._debug());
  }

  beginGrowth(startTimestamp) {
    console.log('TREE_BEGIN_GROWTH', { startTimestamp });
    this.growthStart = startTimestamp;
  }

  start() {
    console.log('TREE_START_STARTED');
    // TreeField starts animation automatically in constructor
  }

  stop() {
    // TreeField doesn't have explicit stop, but we could cancel animation frame if needed
  }

  setState(name) {
    console.log('TREE_SETSTATE', { name });
    if (this.treeField) {
      this.treeField.setState(name);
    }
  }

  // Phase 1 port (prominence.js) -- see TreeField's own comment above.
  setBreatheAmplitude(x) {
    if (this.treeField) {
      this.treeField.setBreatheAmplitude(x);
    }
  }

  renderStaticFrame() {
    console.log('TREE_RENDER_STATIC');
    // TreeField handles reduced motion in constructor
  }

  // Diagnostic methods
  getDebugInfo() {
    if (this.treeField) {
      return this.treeField._debug();
    }
    return null;
  }
}

// Export for app.js compatibility
window.KalpavrikshaTree = KalpavrikshaTree;
window.__TREE_FALLBACK_VOICE_ENVELOPE = 0.55;