/* The tree — Product Veda Deliverable 2 (Animation System).
 * Source: UX_03_Founder_Dashboard.html — THE NEURAL TREE implementation.
 * This is the authoritative silver/metallic Kalpavriksha tree visual.
 * Wrapped to match the expected KalpavrikshaTree class interface.
 *
 * UI V1/V2 reconciliation (14 August 2026) -- Priority 1: the eight-state
 * character model. Ported from VEDA 02_ANIMATION_SYSTEM section 2.2's own
 * per-state parameter table (docs/audits/... reconciliation), plus two
 * additive states (Executing, Error/Recovery) approved via the Decision
 * Gate. See STATE_PARAMS below -- this is VEDA's own numbers, not
 * HyperAgent's prototype geometry, which this file does not copy.
 *
 * The reconciliation's own central finding: "VEDA specifies the tree's
 * *character*. kv-ui-core specifies its *volume*." Two orthogonal axes:
 *   - STATE (this file, STATE_PARAMS) -- pulseDir/pulsePeriod/pulseCrest/
 *     driftMul/seekStiffness/bloomOpacity/bloomToken/breatheAmp/breathePeriod.
 *   - PROMINENCE (prominence.js, --tree-scale/--tree-alpha/--tree-breathe-amp/
 *     --veil-strength, applied via setBreatheAmplitude() and the canvas's
 *     own CSS transform/opacity in prominence.css) -- untouched here.
 * They multiply; neither redesigns the other.
 */
'use strict';

// ---- Per-state character parameters -- VEDA 02_ANIMATION_SYSTEM §2.2 -----
// Six are VEDA's own six states, values copied verbatim from the spec.
// 'executing' and 'recovering'/'failed' are the two additive states the
// Decision Gate approved (Item 2): Executing shares Thinking's basin
// (steady work rhythm, tighter drift, no wander) and Error/Recovery
// reverses pulseDir to DOWN with loose stiffness and a dimmed bloom --
// "the word carries the failure; the tree carries the loss of composure."
// Ruling on colour (documented in docs/audits/ -- diverges from the
// reconciliation's own single-token recommendation on ONE point): the
// shipped Work Region already colours `recovering` as 'live' tone and
// `failed` as 'risk' tone (workState.js's own toneFor(), pre-existing,
// tested, shipped) -- `--s-risk` is one of the four existing signal
// colours, not a fifth, so failed's bloom uses it too for consistency
// with what the founder already reads in the Work Region for the same
// state. `recovering` keeps `--s-live`, matching the reconciliation.
var STATE_PARAMS = {
  idle:       { breatheAmp: 0.006, breathePeriod: 6400, bloomOpacity: 0.60, bloomToken: '--s-live',   driftMul: 1.0, seekStiffness: 0.020, pulseDir: 1,  pulsePeriod: 8000, pulseCrest: 1.08 },
  listening:  { breatheAmp: 0.010, breathePeriod: 4200, bloomOpacity: 1.00, bloomToken: '--s-live',   driftMul: 0.55, seekStiffness: 0.045, pulseDir: -1, pulsePeriod: 4800, pulseCrest: 1.20 },
  thinking:   { breatheAmp: 0.008, breathePeriod: 5200, bloomOpacity: 0.85, bloomToken: '--s-live',   driftMul: 1.4, seekStiffness: 0.014, pulseDir: 1,  pulsePeriod: 3600, pulseCrest: 1.35 },
  executing:  { breatheAmp: 0.008, breathePeriod: 5200, bloomOpacity: 0.80, bloomToken: '--s-live',   driftMul: 1.1, seekStiffness: 0.020, pulseDir: 1,  pulsePeriod: 3000, pulseCrest: 1.22 },
  speaking:   { breatheAmp: 0.006, breathePeriod: 3200, bloomOpacity: 1.00, bloomToken: '--s-live',   driftMul: 0.8, seekStiffness: 0.032, pulseDir: 1,  pulsePeriod: 2800, pulseCrest: 1.15 },
  waiting:    { breatheAmp: 0.007, breathePeriod: 5800, bloomOpacity: 0.70, bloomToken: '--s-attend', driftMul: 0.9, seekStiffness: 0.025, pulseDir: 1,  pulsePeriod: 7200, pulseCrest: 1.12 },
  completed:  { breatheAmp: 0.008, breathePeriod: 5200, bloomOpacity: 0.85, bloomToken: '--s-settled', driftMul: 1.0, seekStiffness: 0.018, pulseDir: 1, pulsePeriod: 4000, pulseCrest: 1.20 },
  recovering: { breatheAmp: 0.007, breathePeriod: 6000, bloomOpacity: 0.55, bloomToken: '--s-live',   driftMul: 1.25, seekStiffness: 0.011, pulseDir: -1, pulsePeriod: 4400, pulseCrest: 1.10 },
  failed:     { breatheAmp: 0.007, breathePeriod: 6000, bloomOpacity: 0.55, bloomToken: '--s-risk',   driftMul: 1.25, seekStiffness: 0.011, pulseDir: -1, pulsePeriod: 4400, pulseCrest: 1.10 },
};
// Celebration -- NOT a status-driven state; a bounded ~2.2s overlay fired
// exactly once per completion_id by app.js's own confirm_completion
// handler (Decision Gate Item 5). completed's own steady parameters
// above are what shows the rest of the time ("Otherwise Completed is a
// settled return with no bloom burst" -- H2's own footnote).
var CELEBRATION_PARAMS = { breatheAmp: 0.018, breathePeriod: 2800, bloomOpacity: 1.00, bloomToken: '--s-bloom', driftMul: 2.2, seekStiffness: 0.008, pulseDir: 1, pulsePeriod: 2200, pulseCrest: 1.55 };

function stateParams(name) {
  return STATE_PARAMS[name] || STATE_PARAMS.idle;
}

// ---- TreeField: procedural branching structure with silver particles ----
function TreeField(canvas, opts) {
  opts = opts || {};
  var ctx = canvas.getContext('2d'), dpr = Math.min(window.devicePixelRatio || 1, 2);
  var W = 0, H = 0, parts = [], nodes = [], edges = [], t0 = performance.now(), assembled = 0;
  var COUNT = opts.count || 2400, MINI = !!opts.mini;
  var state = 'idle';
  var celebrating = false, celebrationStartedAt = 0;
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

  function frame(now, staticEndpoint) {
    var el = (now - t0) / 1000;
    assembled = staticEndpoint ? 1 : Math.min(1, el / 2.4);
    var ease = 1 - Math.pow(1 - assembled, 3);
    ctx.clearRect(0, 0, W, H);

    // -- state character (VEDA 02_ANIMATION_SYSTEM §2.2 / celebration overlay) --
    var params = celebrating ? CELEBRATION_PARAMS : stateParams(state);
    var cx = W * 0.5, cy = H * (MINI ? 0.5 : 0.52);

    // breathe: the resting heartbeat -- amplitude/period from the state,
    // scaled by the prominence multiplier (breatheAmp, outer var, set via
    // setBreatheAmplitude()). staticEndpoint holds it at rest (1.0): a
    // reduced-motion frame must show the SETTLED tree, not an arbitrary
    // frozen instant of an oscillation that happens to still be running.
    var breathePeriodS = params.breathePeriod / 1000;
    var breathe = staticEndpoint ? 1
      : 1 + Math.sin(el * (2 * Math.PI / breathePeriodS)) * params.breatheAmp * breatheAmp;

    // pulse: the larger, slower envelope that actually carries "what is
    // the tree doing" -- crest 1.08 (idle) to 1.35+ (thinking/executing),
    // direction UP (expansion, the default) or DOWN (a taut inward
    // gathering -- Listening, Error/Recovery). This, not breathing, is
    // the channel VEDA's own H4 finding says carries visible life.
    var pulsePeriodS = params.pulsePeriod / 1000;
    var pulseExtent = params.pulseCrest - 1;
    var pulseOsc = staticEndpoint ? 0 : Math.sin(el * (2 * Math.PI / pulsePeriodS));
    var pulse = 1 + pulseExtent * (0.5 + 0.5 * pulseOsc) * params.pulseDir;

    var envelope = breathe * pulse;
    var drift = staticEndpoint ? 0 : params.driftMul;

    /* branch filaments -- legible skeleton, not a particle cloud.
     * Depth-alpha gradient runs trunk -> canopy (higher e.d is closer to
     * the trunk; increasing, not decreasing, is the anatomically correct
     * direction -- the trunk is the tree's most solid, most visible
     * structural fact, and fine twigs recede toward it, not past it). */
    ctx.lineCap = 'round';
    for (var i = 0; i < edges.length; i++) {
      var e = edges[i];
      var o = (0.08 + e.d * 0.030) * ease;
      ctx.strokeStyle = 'rgba(180,225,255,' + o.toFixed(3) + ')';
      ctx.lineWidth = Math.max(0.8, e.w * 0.8);
      ctx.beginPath();
      ctx.moveTo(cx + (e.x1 - 0.5) * W * envelope, cy + (e.y1 - 0.52) * H * envelope);
      ctx.lineTo(cx + (e.x2 - 0.5) * W * envelope, cy + (e.y2 - 0.52) * H * envelope);
      ctx.stroke();
    }

    /* travelling pulse, root -> canopy (the existing energy-flow glow,
     * independent of the state-envelope pulse above) */
    var pulseY = 1.0 - ((el * 0.30) % 1.35);

    for (var j = 0; j < parts.length; j++) {
      var p = parts[j];
      var pr = staticEndpoint ? 1 : Math.max(0, Math.min(1, (ease - p.del) / (1 - p.del)));
      var wob = staticEndpoint ? 0 : Math.sin(el * p.sp + p.ph) * 0.0032 * drift;
      var wob2 = staticEndpoint ? 0 : Math.cos(el * p.sp * 0.7 + p.ph) * 0.0032 * drift;
      var gx = p.tx + wob, gy = p.ty + wob2;
      if (staticEndpoint) { p.x = p.tx; p.y = p.ty; }
      else {
        // seekStiffness: how tautly a particle chases its target -- 0.012
        // is the original resting chase rate (state-independent, unchanged);
        // the state's own stiffness scales in as the particle settles (pr),
        // the same reveal-weighted shape the original 0.055 constant had.
        var chase = 0.012 + pr * params.seekStiffness;
        p.x += (gx - p.x) * chase;
        p.y += (gy - p.y) * chase;
      }

      var sx = cx + (p.x - 0.5) * W * envelope, sy = cy + (p.y - 0.52) * H * envelope;
      var near = 1 - Math.min(1, Math.abs(p.ty - pulseY) / 0.10);
      var glow = staticEndpoint ? 0 : near * near;
      var twinkle = staticEndpoint ? 1 : (0.55 + 0.45 * Math.abs(Math.sin(el * 0.6 * p.sp + p.ph)));
      var alpha = p.a * pr * twinkle;
      var size = p.s * (1 + glow * 1.5) * 1.25;

      if (glow > 0.02) {
        ctx.fillStyle = 'rgba(210,242,255,' + (alpha * glow * 0.95).toFixed(3) + ')';
        ctx.beginPath(); ctx.arc(sx, sy, size * 2.2, 0, 6.283); ctx.fill();
      }
      ctx.fillStyle = 'rgba(' + (glow > 0.3 ? '230,248,255' : '150,215,250') + ',' + alpha.toFixed(3) + ')';
      ctx.beginPath(); ctx.arc(sx, sy, size, 0, 6.283); ctx.fill();
    }
    // H5 -- every state declares a static endpoint; reduced motion must
    // actually stay reduced. Fixed here: this call previously always
    // rescheduled itself via requestAnimationFrame regardless of
    // `reduced`, so the one static frame below was overwritten by full
    // animation on the very next tick.
    if (!reduced) requestAnimationFrame(frame);
  }

  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion:reduce)').matches;
  buildTree(); seed(); resize();
  window.addEventListener('resize', function() {
    resize();
    // Assigning canvas.width/height (inside resize()) always clears the
    // bitmap. With no rAF loop running, reduced motion has nothing left
    // to repaint it on the next tick the way full motion does -- without
    // this, any resize after the initial paint leaves the canvas blank
    // and the tree simply disappears.
    if (reduced) frame(performance.now(), true);
  });
  if (reduced) { t0 = performance.now() - 3000; ctx && frame(performance.now(), true); }
  else requestAnimationFrame(frame);

  return {
    setState: function(s) {
      state = s;
      if (reduced) frame(performance.now(), true); // re-render the new state's static endpoint
    },
    setBreatheAmplitude: function(x) { breatheAmp = x; },
    // Decision Gate Item 5 -- the one approved celebration trigger (the
    // Founder's own Mark-complete action), fired by app.js, bounded to
    // one CELEBRATION_PARAMS.pulsePeriod-ish burst, never looped.
    celebrate: function() {
      celebrating = true;
      celebrationStartedAt = performance.now();
      if (reduced) { frame(performance.now(), true); celebrating = false; return; }
      setTimeout(function () { celebrating = false; }, CELEBRATION_PARAMS.pulsePeriod);
    },
    // Diagnostic: expose internal state for verification
    _debug: function() {
      var params = celebrating ? CELEBRATION_PARAMS : stateParams(state);
      return {
        W: W, H: H,
        edgesCount: edges.length,
        partsCount: parts.length,
        state: state,
        celebrating: celebrating,
        activeParams: params,
        breatheAmpMultiplier: breatheAmp,
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

  // Decision Gate Item 5 -- see TreeField#celebrate's own comment.
  celebrate() {
    if (this.treeField) {
      this.treeField.celebrate();
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
// UI V1/V2 reconciliation -- single source of truth for the per-state
// bloomOpacity/bloomToken app.js's applyBloom() reads (T6). Keeping the
// table in this file (not duplicated in app.js) is what "the base
// parameters live in the renderer" (H1) actually means in practice.
window.KALPAVRIKSHA_TREE_STATE_PARAMS = STATE_PARAMS;
window.KALPAVRIKSHA_TREE_CELEBRATION_PARAMS = CELEBRATION_PARAMS;