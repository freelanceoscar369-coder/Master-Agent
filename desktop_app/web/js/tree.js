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
// COLOUR -- added this mission, reconciled against kv-ui-core's own
// corrected reference (kv-probe-approval-html.html): the tree's body
// (filaments + particles), not only its bloom halo, now tints per state.
// This is what still communicates "human required" once the bloom-gate
// fix below correctly zeroes bloom at `minimum` -- amber has nowhere
// else to appear. Neutral/working states share the tree's own default
// particle token; only the three semantic states (approval-equivalent,
// completed, failed) get a distinct body colour. `recovering` is
// deliberately NOT tinted --s-risk: "retrying is the system alive and
// working, not something wrong" (kv-ui-core's own stated reasoning) --
// its distinctiveness is pulseDir DOWN + looser drift, not colour.
var STATE_PARAMS = {
  idle:       { breatheAmp: 0.006, breathePeriod: 6400, bloomOpacity: 0.60, bloomToken: '--s-live',   driftMul: 1.0, seekStiffness: 0.020, pulseDir: 1,  pulsePeriod: 8000, pulseCrest: 1.08, colour: '--tree-particle' },
  listening:  { breatheAmp: 0.010, breathePeriod: 4200, bloomOpacity: 1.00, bloomToken: '--s-live',   driftMul: 0.55, seekStiffness: 0.045, pulseDir: -1, pulsePeriod: 4800, pulseCrest: 1.20, colour: '--tree-particle' },
  thinking:   { breatheAmp: 0.008, breathePeriod: 5200, bloomOpacity: 0.85, bloomToken: '--s-live',   driftMul: 1.4, seekStiffness: 0.014, pulseDir: 1,  pulsePeriod: 3600, pulseCrest: 1.35, colour: '--tree-particle' },
  executing:  { breatheAmp: 0.008, breathePeriod: 5200, bloomOpacity: 0.80, bloomToken: '--s-live',   driftMul: 1.1, seekStiffness: 0.020, pulseDir: 1,  pulsePeriod: 3000, pulseCrest: 1.22, colour: '--tree-particle' },
  speaking:   { breatheAmp: 0.006, breathePeriod: 3200, bloomOpacity: 1.00, bloomToken: '--s-live',   driftMul: 0.8, seekStiffness: 0.032, pulseDir: 1,  pulsePeriod: 2800, pulseCrest: 1.15, colour: '--tree-particle' },
  waiting:    { breatheAmp: 0.007, breathePeriod: 5800, bloomOpacity: 0.70, bloomToken: '--s-attend', driftMul: 0.9, seekStiffness: 0.025, pulseDir: 1,  pulsePeriod: 7200, pulseCrest: 1.12, colour: '--s-attend' },
  completed:  { breatheAmp: 0.008, breathePeriod: 5200, bloomOpacity: 0.85, bloomToken: '--s-settled', driftMul: 1.0, seekStiffness: 0.018, pulseDir: 1, pulsePeriod: 4000, pulseCrest: 1.20, colour: '--s-settled' },
  recovering: { breatheAmp: 0.007, breathePeriod: 6000, bloomOpacity: 0.55, bloomToken: '--s-live',   driftMul: 1.25, seekStiffness: 0.011, pulseDir: -1, pulsePeriod: 4400, pulseCrest: 1.10, colour: '--tree-particle' },
  failed:     { breatheAmp: 0.007, breathePeriod: 6000, bloomOpacity: 0.55, bloomToken: '--s-risk',   driftMul: 1.25, seekStiffness: 0.011, pulseDir: -1, pulsePeriod: 4400, pulseCrest: 1.10, colour: '--s-risk' },
};
// Celebration -- NOT a status-driven state; a bounded ~2.2s overlay fired
// exactly once per completion_id by app.js's own confirm_completion
// handler (Decision Gate Item 5). completed's own steady parameters
// above are what shows the rest of the time ("Otherwise Completed is a
// settled return with no bloom burst" -- H2's own footnote).
var CELEBRATION_PARAMS = { breatheAmp: 0.018, breathePeriod: 2800, bloomOpacity: 1.00, bloomToken: '--s-bloom', driftMul: 2.2, seekStiffness: 0.008, pulseDir: 1, pulsePeriod: 2200, pulseCrest: 1.55, colour: '--s-bloom' };

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

  // Last CSS-pixel box actually applied, so a ResizeObserver notification
  // that reports no real change becomes a no-op instead of another write.
  var lastCssW = -1, lastCssH = -1;

  function resize() {
    var r = canvas.getBoundingClientRect();

    // Two guards, both load-bearing -- see the ResizeObserver below.
    //
    // 1. CLAMP TO THE VIEWPORT. This canvas is a full-bleed background
    //    layer; it can never legitimately be larger than the window.
    //    Assigning canvas.width/height sets the element's *intrinsic*
    //    size, so a canvas that has lost its CSS box (position/inset/
    //    width/height) sizes itself from those attributes -- and every
    //    observer tick would then multiply it by `dpr` again, growing it
    //    without bound until it exhausts memory. Clamping makes that
    //    runaway arithmetically impossible and, as a bonus, keeps the
    //    tree correct and full-window even if its CSS ever goes missing
    //    again rather than silently rendering into a giant offscreen
    //    buffer.
    // 2. FALL BACK WHEN THE BOX IS ZERO. The first call happens in this
    //    constructor, which can run before the canvas has ever been laid
    //    out; `|| window.innerWidth` paints correctly on that first frame
    //    instead of waiting for a later notification.
    var w = Math.max(1, Math.min(Math.round(r.width) || window.innerWidth, window.innerWidth));
    var h = Math.max(1, Math.min(Math.round(r.height) || window.innerHeight, window.innerHeight));

    // 3. NO-OP ON AN UNCHANGED BOX. Without this the observer re-enters on
    //    every notification it triggers itself, which is what produces the
    //    "ResizeObserver loop completed with undelivered notifications"
    //    warning even when the size has settled.
    if (w === lastCssW && h === lastCssH) return false;

    lastCssW = w; lastCssH = h;
    W = w; H = h;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return true;
  }

  // Resolves a colour token (hex #rrggbb, as most --s-* tokens are, or
  // rgba(...), as --tree-particle is) to [R,G,B]. Read fresh every call,
  // never cached -- the token's own value can change with theme, and this
  // mirrors kv-ui-core's own rgb() helper exactly (kv-probe-approval-html.html).
  var colourCache = {};
  function resolveColour(token) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(token).trim();
    if (colourCache[v]) return colourCache[v];
    var out;
    if (v.indexOf('rgba') === 0 || v.indexOf('rgb') === 0) {
      var m = v.match(/[\d.]+/g);
      out = [Number(m[0]), Number(m[1]), Number(m[2])];
    } else {
      var h = v.replace('#', '');
      out = [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
    }
    colourCache[v] = out;
    return out;
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

    // Per-state body colour -- the tree's own filaments and particles,
    // not only its bloom halo, tint by state (see STATE_PARAMS' own
    // `colour` field comment). Resolved once per frame, not per edge/
    // particle, since it never changes mid-frame.
    var col = resolveColour(params.colour || '--tree-particle');
    var R = col[0], G = col[1], B = col[2];

    /* branch filaments -- legible skeleton, not a particle cloud.
     * Depth-alpha gradient runs trunk -> canopy (higher e.d is closer to
     * the trunk; increasing, not decreasing, is the anatomically correct
     * direction -- the trunk is the tree's most solid, most visible
     * structural fact, and fine twigs recede toward it, not past it). */
    ctx.lineCap = 'round';
    for (var i = 0; i < edges.length; i++) {
      var e = edges[i];
      var o = (0.08 + e.d * 0.030) * ease;
      ctx.strokeStyle = 'rgba(' + R + ',' + G + ',' + B + ',' + o.toFixed(3) + ')';
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
        var hR = Math.min(255, R + 45), hG = Math.min(255, G + 40), hB = Math.min(255, B + 40);
        ctx.fillStyle = 'rgba(' + hR + ',' + hG + ',' + hB + ',' + (alpha * glow * 0.95).toFixed(3) + ')';
        ctx.beginPath(); ctx.arc(sx, sy, size * 2.2, 0, 6.283); ctx.fill();
      }
      var bR = glow > 0.3 ? Math.min(255, R + 20) : R;
      var bG = glow > 0.3 ? Math.min(255, G + 20) : G;
      var bB = glow > 0.3 ? Math.min(255, B + 20) : B;
      ctx.fillStyle = 'rgba(' + bR + ',' + bG + ',' + bB + ',' + alpha.toFixed(3) + ')';
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
  // A real, reproducible race, not just a reduced-motion concern: this
  // constructor's own first resize() call above can run before the
  // canvas has ever been laid out (e.g. a slow first layout pass, fonts
  // still loading, an ancestor flex/grid box not yet resolved), getting
  // a 0x0 bounding rect -- canvas.width/height then stay 0 and NOTHING
  // ever draws, because in full motion the rAF loop keeps calling frame()
  // but frame() never calls resize() itself, and a plain 'resize' window
  // listener only fires on an actual window resize, which may never
  // happen if the embedding window's size never changes after launch.
  // ResizeObserver watches the canvas element's own box directly, fires
  // once immediately with whatever size is available, and fires again
  // the moment layout actually settles -- self-healing the race instead
  // of depending on an unrelated window-level event to happen to occur.
  //
  // SAFETY: observing an element while writing to its size is a feedback
  // loop by construction. resize() above is the guard -- it clamps to the
  // viewport and returns false when nothing actually changed, so the
  // observer settles after one pass instead of driving the canvas
  // upward on every notification. Repaint only when resize() reports a
  // real change (reduced motion has no rAF loop to repaint for it, and
  // assigning canvas.width/height always clears the bitmap).
  function onBoxChange() {
    if (resize() && reduced) frame(performance.now(), true);
  }
  if (typeof ResizeObserver !== 'undefined') {
    new ResizeObserver(onBoxChange).observe(canvas);
  }
  // Kept alongside the observer, not as an either/or: the observer catches
  // the layout race, this catches a window resize that leaves the canvas's
  // own box unchanged but changes the viewport the clamp above reads from.
  window.addEventListener('resize', onBoxChange);
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