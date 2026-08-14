/* Founder Surface application logic.
 * Wires the tree (tree.js) and the DOM to the Python bridge
 * (`window.pywebview.api`, exposed by founder_edition/desktop_shell.py).
 * Every runtime fact — greeting, replies, dashboard data, and (as of
 * C34.1) every voice state/amplitude/transcript — comes from the bridge.
 * This file never composes Somesh's words and never touches a speech
 * API of its own; see Engineering/HEALTH_C34_1.md for the boundary this
 * keeps and why Web Speech API was removed entirely.
 */
'use strict';

const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const $ = (sel) => document.querySelector(sel);

// ---------------------------------------------------------------- bridge --
// A founder-visible P0: pywebviewready failing to fire used to hang every
// Bridge.call forever — no tree, no greeting, no voice, no text, the whole
// app looking dead with nothing to diagnose. A bounded wait means the rest
// of startup (tree build, greeting slot, diagnostics overlay below) always
// eventually proceeds, degrading honestly instead of hanging silently.
const BRIDGE_READY_TIMEOUT_MS = 8000;
let bridgeTimedOut = false;

const Bridge = {
  ready: false,
  async call(name, ...args) {
    if (!window.pywebview || !window.pywebview.api) {
      await Promise.race([
        new Promise((resolve) => {
          window.addEventListener('pywebviewready', resolve, { once: true });
        }),
        new Promise((_resolve, reject) => {
          setTimeout(() => {
            bridgeTimedOut = true;
            reject(new Error('pywebview bridge did not become ready in time'));
          }, BRIDGE_READY_TIMEOUT_MS);
        }),
      ]);
    }
    return window.pywebview.api[name](...args);
  },
};

// ------------------------------------------------------------- elements --
const canvas = $('#treeCanvas');
console.log('TREE_CANVAS_FOUND', {
  exists: !!canvas,
  width: canvas?.width,
  height: canvas?.height,
  clientWidth: canvas?.clientWidth,
  clientHeight: canvas?.clientHeight,
  rect: canvas?.getBoundingClientRect(),
  display: canvas ? getComputedStyle(canvas).display : null,
  visibility: canvas ? getComputedStyle(canvas).visibility : null,
  opacity: canvas ? getComputedStyle(canvas).opacity : null,
  zIndex: canvas ? getComputedStyle(canvas).zIndex : null,
  position: canvas ? getComputedStyle(canvas).position : null
});

const els = {
  wordmark: $('.wordmark'),
  startupDiagnostics: $('.startup-diagnostics'),
  chevron: $('.dashboard-chevron'),
  fieldBase: $('.field-base'),
  bloom: $('.bloom'),
  greeting: $('.greeting'),
  presence: $('.presence-line'),
  micWrap: $('.mic-wrap'),
  mic: $('.mic'),
  micLabel: $('.mic-label'),
  micSecondary: $('.mic-secondary'),
  listeningBar: $('.listening-bar'),
  waveform: $('.waveform'),
  composerWrap: $('.composer-wrap'),
  composer: $('.composer'),
  composerInput: $('.composer-input'),
  composerPlaceholder: $('.composer-placeholder'),
  composerSend: $('.composer-send'),
  footerHint: $('.footer-hint'),
  modeSwitch: $('.mode-switch'),
  conversationScroll: $('.conversation-scroll'),
  conversation: $('.conversation'),
  workRegionSlot: $('.work-region-slot'),
  thinking: $('.thinking-indicator'),
  dashboardBackdrop: $('.dashboard-backdrop'),
  dashboardClose: $('.dashboard-close'),
  dashboardBody: $('#dashboard-body'),
  themeButtons: document.querySelectorAll('.theme-control button'),
};

const tree = new window.KalpavrikshaTree(canvas, {
  onBloomChange: (state) => applyBloom(state),
});

// ------------------------------------------------------------- bloom/UI --
// UI V1/V2 reconciliation (14 Aug 2026) -- bloomOpacity/bloomToken per
// state now come from tree.js's own STATE_PARAMS (window.
// KALPAVRIKSHA_TREE_STATE_PARAMS), not a second, hand-copied table here --
// "the base parameters live in the renderer" (H1). This function stays
// the one place that turns those numbers into the actual .bloom element,
// since bloom is a DOM div, not part of the canvas.
//
// RULING -- Priority 2 Item 1, "Waiting/Attention bloom conflict"
// (documented per the mission's own instruction not to silently pick
// one): VEDA's per-state table gives Waiting bloomOpacity 0.70; prominence.js
// (unedited, per the hard rule) gates --tree-bloom-opacity to 0 at BOTH
// `reduced` and `minimum`. Applying that gate literally would mean
// Waiting's 0.70 -- and Error/Recovery's 0.55 -- can never actually be
// seen, since both states are only ever reached at `minimum` prominence.
// Read for INTENT rather than applied as a blind override: prominence's
// zero exists for one stated reason -- "bloom is a light source competing
// with text... the single largest contributor to the reported 'tree over
// work' feeling" -- which is the Work Region's text, present at `reduced`
// (a live work sentence). At `minimum`, H3 gives the state's own bloom a
// DIFFERENT, deliberate job: "local warmth... a human is required there."
// So: prominence's bloom-to-zero is authoritative at `reduced` (unchanged,
// already-shipped, no regression); at `minimum` the state's own
// bloomOpacity governs instead of being forced to 0. `ambient` never
// disagrees between the two axes (idle's 0.60 already equals prominence's
// own 0.6). prominence.js itself is never edited -- this ruling lives
// entirely in how the renderer/wiring layer (here) combines the two
// numbers, which is exactly the judgment call the handoff leaves to the
// implementer.
//
// RULING -- Priority 2 Item 2, "Error/Recovery colour": diverges from the
// reconciliation's own single-token recommendation (`--s-live` for both
// recovering and failed) on ONE point -- see tree.js's own STATE_PARAMS
// comment for the full reasoning (consistency with the Work Region's own
// already-shipped tone-to-colour mapping in workState.js/work-region.css).
const BLOOM_TRANS_DURATION = {
  idle: 'var(--d-8)', listening: 'var(--d-8)', thinking: 'var(--d-8)',
  executing: 'var(--d-8)', speaking: 'var(--d-4)', waiting: 'var(--d-8)',
  completed: 'var(--d-8)', recovering: 'var(--d-8)', failed: 'var(--d-8)',
  celebration: 'var(--d-6)',
};
// Internal glow-colour alpha (the radial gradient's own colour strength --
// distinct from the element opacity above; not a VEDA-specified number,
// an existing visual-tuning knob this port extends rather than redefines).
const BLOOM_GLOW_ALPHA = {
  idle: 0.055, listening: 0.055, thinking: 0.065, executing: 0.065,
  speaking: 0.050, waiting: 0.045, completed: 0.065,
  recovering: 0.040, failed: 0.040, celebration: 0.075,
};
// 03_VOICE_EXPERIENCE §3.5 — "Tree while denied: tree holds whatever
// state it was in. The bloom dims to 0.4 at --d-8 --e-settle." `denied`
// is a mic state, not a tree state (tree.setState never receives it),
// so the dim has to be layered on top of whatever the tree's own bloom
// opacity currently is, independent of which tree state that happens
// to be — set/cleared by setMicState below.
let micDenied = false;
// Tracks the CURRENT prominence level (not just a derived 0/1 multiplier)
// so applyBloom() can apply the ruling above precisely: force 0 only at
// `reduced`; let the state's own bloomOpacity govern at `ambient`/`minimum`.
let currentProminenceLevel = 'ambient';
let lastBloomState = 'idle';
function applyBloom(state) {
  lastBloomState = state;
  const stateParams = state === 'celebration'
    ? (window.KALPAVRIKSHA_TREE_CELEBRATION_PARAMS || { bloomOpacity: 1.0, bloomToken: '--s-bloom' })
    : ((window.KALPAVRIKSHA_TREE_STATE_PARAMS || {})[state] || { bloomOpacity: 0.60, bloomToken: '--s-live' });
  const bloomGate = currentProminenceLevel === 'reduced' ? 0 : 1;
  const p = micDenied ? 0.4 : (stateParams.bloomOpacity * bloomGate);
  const dur = micDenied ? 'var(--d-8)' : (BLOOM_TRANS_DURATION[state] || 'var(--d-8)');
  els.bloom.style.transitionDuration = `${dur}, ${dur}`;
  els.bloom.style.opacity = String(p);
  const hueVar = stateParams.bloomToken || '--s-live';
  const alpha = BLOOM_GLOW_ALPHA[state] ?? 0.055;
  const hex = getComputedStyle(document.documentElement).getPropertyValue(hueVar).trim();
  const rgb = hexToRgb(hex);
  if (rgb) {
    els.bloom.style.background = `radial-gradient(circle, rgba(${rgb.r},${rgb.g},${rgb.b},${alpha}) 0%, transparent 70%)`;
  }
}
function hexToRgb(hex) {
  const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return m ? { r: parseInt(m[1], 16), g: parseInt(m[2], 16), b: parseInt(m[3], 16) } : null;
}

// ------------------------------------------------- tree state arbiter --
// UI V1/V2 reconciliation -- one source of truth for which of the tree's
// nine character states (tree.js STATE_PARAMS) is showing, combining the
// voice signal and the execution status per VEDA 02_ANIMATION_SYSTEM
// §2.3.2's own priority order (Celebration > Speaking > Listening >
// Thinking > Waiting > Idle). Executing sits in Thinking's slot,
// Error/Recovery in Waiting's -- both pairs are already mutually
// exclusive by construction (they derive from the single
// ExecutionStatus.status field VEDA's own Thinking/Waiting never had to
// share with anything), so nothing about VEDA's ordering itself changes;
// this only names where the two additive states sit in it.
//
// Replaces every previously-scattered direct tree.setState() call in
// this file (nine call sites) with one arbiter, so voice events and
// execution-status polling can never independently disagree about which
// state should currently be showing -- and fixes a pre-existing bug:
// applyBloom(tree.state) (setMicState, below) read a property
// KalpavrikshaTree never actually set.
let voiceTreeSignal = 'idle'; // 'idle' | 'listening' | 'speaking'
let conversationalThinking = false; // a plain conversational round-trip in flight
let currentTreeState = 'idle';

function setTreeState(name) {
  if (name === currentTreeState) return;
  currentTreeState = name;
  tree.setState(name);
  applyBloom(name);
}

// Mirrors deriveProminence()'s own precedence (prominence.js, unedited)
// so the tree's character and its prominence level never disagree about
// which backend condition is "the" current one. Reads the module-level
// executionStatus/resultAcknowledged declared later in this file --
// safe: this function is only ever invoked from event handlers, after
// the whole script has already run top-to-bottom once.
function executionTreeState() {
  const exec = executionStatus;
  if (!exec) return null;
  const needsFounder = exec.requires_founder_completion ||
    exec.status === 'awaiting_founder_completion' ||
    exec.status === 'awaiting_approval' || exec.status === 'blocked';
  if (needsFounder) return 'waiting';
  if (exec.status === 'failed' && !resultAcknowledged) return 'failed';
  if (exec.status === 'recovering') return 'recovering';
  if (exec.status === 'completed' || exec.terminal_state) {
    return resultAcknowledged ? null : 'completed';
  }
  if (exec.status === 'executing' || exec.status === 'observing') return 'executing';
  if (exec.status === 'understanding' || exec.status === 'planning' || exec.status === 'verifying') return 'thinking';
  return null;
}

function recomputeTreeState() {
  if (voiceTreeSignal === 'speaking') { setTreeState('speaking'); return; }
  if (voiceTreeSignal === 'listening') { setTreeState('listening'); return; }
  const ex = executionTreeState();
  if (ex) { setTreeState(ex); return; }
  if (conversationalThinking) { setTreeState('thinking'); return; }
  setTreeState('idle');
}

// ------------------------------------------------------------- greeting --
let greetingText = null;
let presenceText = null;

async function fetchGreeting() {
  try {
    const result = await Bridge.call('greet');
    greetingText = result.reply || null;
    presenceText = result.presence || null;
  } catch (e) {
    greetingText = null;
  }
}

function applyGreeting() {
  if (greetingText) {
    els.greeting.textContent = greetingText;
    els.greeting.classList.add('is-visible');
  }
  if (presenceText) {
    els.presence.textContent = presenceText;
    els.presence.classList.add('is-visible');
  } else {
    els.presence.textContent = '—';
    els.presence.classList.add('is-visible');
  }
}

// --------------------------------------------------------------- mic ----
// Voice is entirely Python-side (founder_edition.voice_pipeline —
// local Whisper STT, local Piper TTS, C34.1). This file never opens a
// microphone, never calls a speech API, and never synthesises audio —
// it only reflects state the bridge pushes through onVoiceState /
// onVoiceAmplitude / onTranscript, and asks the bridge to toggle mute.
let micState = 'idle';

function openMicrophoneSettings() {
  Bridge.call('open_microphone_settings').catch(() => {});
}

// The clickable "here" inside the `denied` secondary line — built fresh
// on every state entry (setMicState clears micSecondary's children each
// time) rather than kept as a persistent element with a static listener.
function micSettingsLink() {
  const link = document.createElement('a');
  link.href = '#';
  link.textContent = 'here';
  link.addEventListener('click', (event) => {
    event.preventDefault();
    openMicrophoneSettings();
  });
  return link;
}

// ----------------------------------------------------------- interrupt --
// 03_VOICE_EXPERIENCE §3.4 — tracked here (not read off the tree) because
// the tree's own state can lag a frame behind the push that set it, and
// the mic-click/typing handlers need a synchronous answer to "is Somesh
// talking right now".
let isSpeaking = false;
let isSending = false;  // P2: guards against duplicate submitMessage calls
let lastSomeshMessageEl = null;

function runInterruptVisuals(treeTarget) {
  els.waveform.style.transitionDuration = 'var(--d-2)'; // §3.4 "waveform... drops to opacity 0 at --d-2"
  els.waveform.style.opacity = '0';
  markLastSomeshMessageInterrupted();
  voiceTreeSignal = treeTarget;
  recomputeTreeState();
}

function markLastSomeshMessageInterrupted() {
  if (!lastSomeshMessageEl) return;
  if (lastSomeshMessageEl.querySelector('.somesh-message__interrupted')) return;
  const marker = document.createElement('div');
  marker.className = 'somesh-message__interrupted';
  marker.textContent = '— interrupted';
  lastSomeshMessageEl.querySelector('.somesh-message__body').after(marker);
  requestAnimationFrame(() => marker.classList.add('is-visible'));
}

// Triggers 1/3/4 (mic click, typing, Escape) — the founder acted, so this
// tells the bridge to actually stop playback. Trigger 2 (VAD onset) is
// handled inside setVoiceState below instead: the pipeline detects that
// one itself and has already called VoicePipeline.interrupt_speech() by
// the time its state push arrives here, so calling the bridge again
// would be redundant (interrupt_speech() is a no-op once not speaking,
// so it would be harmless either way — this just avoids the extra call).
function interruptSpeech(treeTarget) {
  if (!isSpeaking) return;
  isSpeaking = false;
  Bridge.call('interrupt_speech').catch(() => {});
  runInterruptVisuals(treeTarget);
}

// §3.7 "Founder starts typing mid-utterance" — a distinct scenario from
// interruptSpeech() above: the founder's own voice capture is discarded,
// not Somesh's playback. Safe to call unconditionally at every typing
// trigger — the backend's own abandon_capture() is a no-op unless the
// mic is actually mid-utterance, so this never needs a micState check
// here (mirroring interrupt_speech()'s own unconditional-safe design).
function abandonVoiceCapture() {
  Bridge.call('abandon_voice_capture').catch(() => {});
}

// 'speaking' is a tree-only concept (02_ANIMATION_SYSTEM §2.2.4) — the
// mic component's own state vocabulary (03_VOICE_EXPERIENCE §3.1) has
// no "speaking" entry, because the founder's mic is not the one making
// sound. It arrives on the same push channel because the same pipeline
// drives both; it updates only the tree, never the mic button/label.
function setVoiceState(name) {
  if (name === 'speaking') {
    isSpeaking = true;
    voiceTreeSignal = 'speaking';
    recomputeTreeState();
    return;
  }
  if (isSpeaking && (name === 'listening' || name === 'capturing-speech')) {
    // Trigger 2 — the VAD confirmed the founder speaking over Somesh.
    // The pipeline has already stopped playback on its own; this just
    // runs the same visual sequence the other three triggers use.
    runInterruptVisuals('listening');
  }
  isSpeaking = false;
  setMicState(name);
}

// 03_VOICE_EXPERIENCE §3.1 — "error auto-recovers: after 8000ms, if the
// runtime has not reported resolution, return to unavailable." The
// backend keeps retrying to reopen the device on its own 1.5s poll
// (voice_pipeline.py's _device_watch_loop) and will push 'armed' the
// moment it succeeds; this timer is the UI's own fallback for a device
// that never comes back, so 'error' — which reads as transient — does
// not linger forever once it's clear it isn't resolving.
let errorRecoveryTimer = null;

function setMicState(name) {
  micState = name;
  els.mic.dataset.state = name;
  if (errorRecoveryTimer) {
    clearTimeout(errorRecoveryTimer);
    errorRecoveryTimer = null;
  }
  if (name === 'error') {
    errorRecoveryTimer = setTimeout(() => {
      errorRecoveryTimer = null;
      if (micState === 'error') setMicState('unavailable');
    }, 8000);
  }
  const labels = {
    idle: 'TAP TO SPEAK', armed: 'LISTENING', listening: 'LISTENING',
    'capturing-speech': 'CAPTURING', processing: 'PROCESSING', muted: 'MUTED',
    denied: 'MICROPHONE BLOCKED', unavailable: 'NO MICROPHONE', error: 'VOICE UNAVAILABLE',
  };
  els.micLabel.textContent = labels[name] || '';
  const secondary = {
    unavailable: 'No microphone found. Type to continue.',
    error: 'Voice hit a problem. Type to continue.',
  };
  if (name === 'denied') {
    // 03_VOICE_EXPERIENCE §3.5 — the word "here" is a clickable deep-link
    // into Windows' own microphone privacy settings, not plain text.
    els.micSecondary.textContent = '';
    els.micSecondary.append(
      document.createTextNode('Microphone access was blocked. Click '),
      micSettingsLink(),
      document.createTextNode(' to open settings.'),
    );
    els.micSecondary.classList.add('is-visible');
  } else if (secondary[name]) {
    els.micSecondary.textContent = secondary[name];
    els.micSecondary.classList.add('is-visible');
  } else {
    els.micSecondary.classList.remove('is-visible');
  }

  // Tree states (02_ANIMATION_SYSTEM §2.2) are a different, nine-member
  // vocabulary from mic states (03_VOICE_EXPERIENCE §3.1) — 'armed' is a
  // mic state only. Armed maps to tree Idle: the tree enters Listening
  // only once the founder is actually being heard. `unavailable` also
  // maps to Idle explicitly — §3.5 "Tree while unavailable: tree holds
  // idle" — rather than being left wherever the tree happened to be
  // (e.g. still Listening if the device vanished mid-utterance).
  // `processing` (Whisper transcribing what was just captured) is
  // genuinely Thinking in VEDA's own sense -- "active when the runtime is
  // processing, no audio I/O active" -- routed through the same
  // conversationalThinking flag submitMessage()'s own round-trip uses,
  // not a direct tree.setState(), so the two can never disagree.
  if (name === 'listening' || name === 'capturing-speech') {
    voiceTreeSignal = 'listening';
  } else if (name === 'processing') {
    voiceTreeSignal = 'idle';
    conversationalThinking = true;
  } else if (name === 'armed' || name === 'idle' || name === 'muted' || name === 'unavailable') {
    voiceTreeSignal = 'idle';
    conversationalThinking = false;
  }
  recomputeTreeState();

  const wasDenied = micDenied;
  micDenied = name === 'denied';
  if (micDenied !== wasDenied) applyBloom(currentTreeState); // apply/clear the §3.5 dim now, even if the tree's own state didn't change this call

  updateListeningBar(name);
  updateWaveformVisibility(name);

  if (name === 'denied' || name === 'unavailable' || name === 'error') {
    expandComposer(true);
  }
}

function updateListeningBar(name) {
  if (name === 'capturing-speech') {
    els.listeningBar.style.width = '80px';
    els.listeningBar.style.opacity = '1.0';
  } else if (name === 'listening') {
    els.listeningBar.style.width = '40px';
    els.listeningBar.style.opacity = '0.55';
  } else {
    els.listeningBar.style.width = '40px';
    els.listeningBar.style.opacity = '0';
  }
}

function updateWaveformVisibility(name) {
  const opacity = { 'capturing-speech': 1.0, processing: 0.30 }[name] ?? 0;
  els.waveform.style.opacity = String(opacity);
}

// 03_VOICE_EXPERIENCE §3.3 — 9 bars, triangular envelope from one scalar.
const WAVEFORM_BARS = Array.from(els.waveform.querySelectorAll('.bar'));
const smoothedBars = new Array(WAVEFORM_BARS.length).fill(0);
function renderWaveform(amplitude) {
  for (let i = 0; i < WAVEFORM_BARS.length; i++) {
    const shape = 1.0 - Math.abs(i - 4) / 4;
    const target = amplitude * shape;
    smoothedBars[i] = smoothedBars[i] * 0.72 + target * 0.28;
    const height = 3 + 33 * smoothedBars[i];
    WAVEFORM_BARS[i].style.height = `${height}px`;
  }
}

/* Called by the bridge (`desktop_shell._push`) — a voice state arrived
 * from the real local pipeline: a mic state, or 'speaking'. */
window.onVoiceState = function onVoiceState(state) {
  setVoiceState(state);
};

/* Called by the bridge — one real amplitude sample, [0,1], from either
 * the live microphone (listening) or the synthesised reply (speaking). */
window.onVoiceAmplitude = function onVoiceAmplitude(amplitude) {
  renderWaveform(amplitude);
};

/* Called by the bridge — one committed transcript from local Whisper.
 * Submitted exactly like a typed message, through the same pipeline. */
window.onTranscript = function onTranscript(text) {
  if (text && text.trim()) submitMessage(text.trim(), 'voice');
};

els.mic.addEventListener('click', () => {
  // §3.4 trigger 1 — clicking the mic while Somesh is speaking
  // interrupts instead of toggling mute.
  if (isSpeaking) {
    interruptSpeech('listening');
    return;
  }
  // 03_VOICE_EXPERIENCE §3.5 — clicking the mic itself while `denied`
  // opens settings too, same as the "here" link in the secondary copy.
  if (micState === 'denied') {
    openMicrophoneSettings();
    return;
  }
  if (micState === 'unavailable' || micState === 'error') return;
  Bridge.call('toggle_mute').catch(() => {});
});

// ----------------------------------------------------------- composer ----
let hasInteracted = false;
let firstMessageSent = false;

function expandComposer(force) {
  els.composer.classList.add('is-expanded');
  if (force) els.composerInput.focus();
}
function collapseComposerIfEmpty() {
  if (micState === 'unavailable' || micState === 'denied') return; // 3.5 — cannot collapse
  if (!els.composerInput.textContent.trim()) {
    els.composer.classList.remove('is-expanded');
  }
}
function markInteracted() {
  if (hasInteracted) return;
  hasInteracted = true;
  els.footerHint.classList.add('is-hidden');
}

els.composer.addEventListener('click', () => expandComposer(true));
els.composerInput.addEventListener('focus', () => {
  // §3.4 trigger 3 — "any printable keypress OR focus on composer".
  if (isSpeaking) interruptSpeech('listening');
  abandonVoiceCapture(); // §3.7 — same trigger, the founder's own capture
  expandComposer(false);
});
els.composerInput.addEventListener('input', () => {
  markInteracted();
  els.composer.classList.toggle('has-text', !!els.composerInput.textContent.trim());
});
els.composerInput.addEventListener('blur', () => setTimeout(collapseComposerIfEmpty, 100));
els.composerInput.addEventListener('keydown', (ev) => {
  // §3.4 triggers 3 and 4 — any keypress while typing (composer already
  // focused, so the 'focus' listener above didn't fire) and Escape both
  // land here.
  if (isSpeaking) interruptSpeech('listening');
  abandonVoiceCapture(); // §3.7 — every keystroke here, including Enter
  if (ev.key === 'Enter' && !ev.shiftKey) {
    ev.preventDefault();
    const text = els.composerInput.textContent.trim();
    if (!text) return;
    els.composerInput.textContent = '';
    els.composer.classList.remove('has-text');
    submitMessage(text, 'text');
  } else if (ev.key === 'Escape') {
    if (els.composerInput.textContent.trim()) {
      els.composerInput.textContent = '';
      els.composer.classList.remove('has-text');
    } else {
      els.composerInput.blur();
      collapseComposerIfEmpty();
    }
  }
});
els.composerSend.addEventListener('click', () => {
  const text = els.composerInput.textContent.trim();
  if (!text) return;
  els.composerInput.textContent = '';
  els.composer.classList.remove('has-text');
  submitMessage(text, 'text');
});

// 1.6 — any printable keypress anywhere expands the composer and becomes
// the first character.
document.addEventListener('keydown', (ev) => {
  if (!startupDone) return; // startup owns keydown until Ready/fast-forward
  const active = document.activeElement;
  if (active === els.composerInput) return;
  if (els.dashboardBackdrop.classList.contains('is-open')) return;
  // §3.4 trigger 4 — Escape interrupts even without the composer
  // focused; the composer's own keydown handler covers it once focused.
  if (ev.key === 'Escape') {
    if (isSpeaking) interruptSpeech('listening');
    abandonVoiceCapture(); // §3.7
    return;
  }
  if (ev.key.length === 1 && !ev.ctrlKey && !ev.metaKey && !ev.altKey) {
    // §3.4 trigger 3 — typing from anywhere, before focus lands.
    if (isSpeaking) interruptSpeech('listening');
    abandonVoiceCapture(); // §3.7
    markInteracted();
    expandComposer(true);
    // let the browser's own focus + keypress land the character naturally
  }
});

// ---------------------------------------------------------- conversation --
function fmtTime(d) {
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${hh}:${mm}`;
}

function enterConversationView() {
  if (firstMessageSent) return;
  firstMessageSent = true;
  els.greeting.style.transition = `opacity var(--d-3) var(--e-exit)`;
  els.greeting.style.opacity = '0';
  els.presence.style.opacity = '0';
  els.footerHint.style.opacity = '0';
  els.conversationScroll.classList.add('is-visible');
  document.querySelector('.stack').classList.add('is-conversation');
}

function appendFounderMessage(text, at) {
  const wrap = document.createElement('div');
  wrap.className = 'founder-message';
  wrap.innerHTML = `<div class="founder-message-col">
      <div class="founder-message__bubble"></div>
      <div class="founder-message__time"></div>
    </div>`;
  wrap.querySelector('.founder-message__bubble').textContent = text;
  wrap.querySelector('.founder-message__time').textContent = fmtTime(at);
  els.conversation.appendChild(wrap);
  scrollToBottom();
}

function appendSomeshMessage(text) {
  const wrap = document.createElement('div');
  wrap.className = 'somesh-message';
  const length = text.length > 240 ? 'long' : 'short';
  wrap.innerHTML = `<div class="somesh-message__hairline"></div>
    <div class="somesh-message__body" data-length="${length}"></div>`;
  wrap.querySelector('.somesh-message__body').textContent = text;
  els.conversation.appendChild(wrap);
  lastSomeshMessageEl = wrap;
  scrollToBottom();
  // Speaking happens on the Python side (desktop_shell.send_message()
  // already called voice.speak() before this reply arrived) — the tree's
  // own transition to Speaking, and back, comes from onVoiceState pushes,
  // not from anything called here.
}

function scrollToBottom() {
  els.conversationScroll.scrollTop = els.conversationScroll.scrollHeight;
}

let thinkingTimer = null;
let thinkingTimeout = null;  // P2: timeout guard — auto-recover if engine hangs
function showThinkingSoon() {
  thinkingTimer = setTimeout(() => {
    els.thinking.classList.add('is-visible');
    conversationalThinking = true;
    recomputeTreeState();
    // P2: safety — if no response within 15s, stop asserting "thinking"
    // and let the arbiter fall back to whatever is actually true (idle,
    // or a real in-flight mission the execution-status poller already
    // knows about independently). Previously forced 'waiting' (amber,
    // "needs your approval") here -- wrong under the reconciled model:
    // a slow reply is not a founder-approval request, and forcing amber
    // for one taught the founder to distrust amber generally.
    thinkingTimeout = setTimeout(() => {
      if (isSending) {
        hideThinking();
        conversationalThinking = false;
        recomputeTreeState();
        isSending = false;
      }
    }, 15000);
  }, 400); // --d-gate
}
function hideThinking() {
  clearTimeout(thinkingTimer);
  clearTimeout(thinkingTimeout);
  els.thinking.classList.remove('is-visible');
  conversationalThinking = false;
}

async function submitMessage(text, source) {
  if (!text.trim()) return;
  if (isSending) return;  // P2: prevent duplicate/concurrent submissions
  isSending = true;
  // Phase 1/3 port -- sending a new message is the founder's own "moving
  // on" signal: whatever terminal result (completed/failed) was showing
  // is now acknowledged, which is what lets tree prominence return to
  // ambient (prominence.js's own resultAcknowledged input) instead of
  // staying reduced forever after a result nobody dismissed.
  resultAcknowledged = true;
  markInteracted();
  enterConversationView();
  appendFounderMessage(text, new Date());
  showThinkingSoon();
  try {
    const result = await Bridge.call('send_message', text, source);
    hideThinking(); // clears conversationalThinking
    if (result && result.reply) {
      appendSomeshMessage(result.reply);
    }
    // Let the arbiter decide -- forcing 'idle' here would fight a real
    // in-flight mission the execution-status poller already knows about
    // independently (e.g. this reply was the founder's own objective,
    // now genuinely executing in the background).
    recomputeTreeState();
    refreshDashboard();
  } catch (e) {
    // A bridge/network failure, not a founder-approval request -- 'waiting'
    // (amber) would misrepresent it under the reconciled model. Recompute
    // instead of asserting a specific wrong state.
    hideThinking();
    recomputeTreeState();
  } finally {
    isSending = false;  // P2: always release the guard
  }
}

// ------------------------------------------------------------ dashboard --
function signalFor(bool) { return bool ? 'settled' : 'attend'; }

function row(label, value, signal) {
  return `<div class="dash-row"><span class="dash-row__label">${label}</span>
    <span class="dash-row__value"${signal ? ` data-signal="${signal}"` : ''}>${value}</span></div>`;
}

// UI V1/V2 reconciliation, Decision Gate Item 3 -- four canonical views,
// locked: Missions · Record · Rules & Learning · System. Replaces the
// prior single undifferentiated panel. Every row below is either real
// data from get_dashboard()/the live execution-status poller, or an
// honest "not yet available" placeholder -- Record and Rules & Learning
// have no backend data source today (Gate 0 D5/D8, non-blocking, not
// invented here) and say so rather than showing fabricated content.
const DASHBOARD_VIEWS = ['missions', 'record', 'rules', 'system'];
let currentDashboardView = 'missions';
let lastDashboardData = null;

async function refreshDashboard() {
  try {
    lastDashboardData = await Bridge.call('get_dashboard');
    renderCurrentDashboardView();
  } catch (e) { /* honest absence — leave the last known view */ }
}

function renderCurrentDashboardView() {
  const d = lastDashboardData || {};
  const identity = d.identity || {};
  let html = `<div class="dashboard-title">${identity.assistant_name || 'Somesh'}</div>
    <div class="dashboard-sub">for ${identity.founder_name || ''} · ${identity.edition || ''}</div>`;
  if (currentDashboardView === 'missions') html += renderMissionsView();
  else if (currentDashboardView === 'record') html += renderRecordView();
  else if (currentDashboardView === 'rules') html += renderRulesView();
  else html += renderSystemView(d);
  els.dashboardBody.innerHTML = html;
  if (currentDashboardView === 'system') wireThemeButtonsInDashboard();
}

// View 1 -- Missions: what is running, queued, or held, and why. Real
// data source: the same get_execution_status() poll driving the Work
// Region (executionStatus, module-level, already live). No queue/held
// concept exists in the backend yet (Gate 0 D3) -- shown honestly.
function renderMissionsView() {
  const exec = executionStatus || window.KalpavrikshaWorkState.IDLE_EXECUTION;
  const presentation = window.KalpavrikshaWorkState.presentWork(exec);
  let html = `<div class="dash-section"><div class="dash-section-title">Now</div>`;
  if (presentation.visible) {
    html += row('Working on', presentation.headline, presentation.tone);
    if (exec.current_step && exec.total_steps) {
      html += row('Step', `${exec.current_step} of ${exec.total_steps}`);
    }
  } else {
    html += `<div class="dash-empty">Nothing running.</div>`;
  }
  html += `</div>`;
  html += `<div class="dash-section"><div class="dash-section-title">Queued &amp; held</div>
    <div class="dash-empty">Not yet available — mission queue/held-state reporting is not wired to this dashboard yet.</div></div>`;
  return html;
}

// View 2 -- Record: what happened, what changed, evidence. No backend
// record/audit-ledger source exists yet (Gate 0 D8) -- honest placeholder,
// not fabricated history.
function renderRecordView() {
  return `<div class="dash-section"><div class="dash-section-title">What changed</div>
    <div class="dash-empty">Not yet available — Record has no backend data source wired yet.</div></div>`;
}

// View 3 -- Rules & Learning: what Kalpavriksha may do alone, what it
// proposes, what expires. No rule-object source exists yet (Gate 0 D5) --
// honest placeholder. This is also where the AUTONOMY % this mission was
// asked to keep removed would have lived; it was never real, and nothing
// here invents a replacement number.
function renderRulesView() {
  return `<div class="dash-section"><div class="dash-section-title">Active rules</div>
    <div class="dash-empty">Not yet available — Rules &amp; Learning has no backend data source wired yet.</div></div>`;
}

// View 4 -- System: the pre-existing dashboard content (Session,
// Environment & Presence, Desktop, Runtime sources, Appearance),
// unchanged, now under its own named view instead of the whole panel.
function renderSystemView(d) {
  const session = d.session || {};
  const presence = d.presence || {};
  const coverage = presence.coverage;
  const desktop = d.desktop;
  const sources = d.sources || [];

  let html = `<div class="dash-section"><div class="dash-section-title">Session</div>`;
  html += row('Active', session.active ? 'yes' : 'no', signalFor(session.active));
  html += row('Turns', (d.conversation && d.conversation.entries ? d.conversation.entries.length : 0));
  html += `</div>`;

  html += `<div class="dash-section"><div class="dash-section-title">Environment &amp; Presence</div>`;
  html += row('Environment', d.environment ? 'known' : 'not scanned yet', signalFor(!!d.environment));
  html += row('Vigilance', coverage ? `complete=${coverage.complete}` : 'no domain registered', signalFor(!!(coverage && coverage.complete)));
  html += `</div>`;

  html += `<div class="dash-section"><div class="dash-section-title">Desktop</div>`;
  if (desktop) {
    (desktop.layers || []).forEach((l) => { html += row(l.component + ' ' + l.name, l.wired ? 'wired' : 'absent', signalFor(l.wired)); });
  } else {
    html += row('Desktop layer', 'not wired', 'attend');
  }
  html += `</div>`;

  html += `<div class="dash-section"><div class="dash-section-title">Runtime sources</div>`;
  sources.forEach((s) => { html += row(s.name, s.present ? 'yes' : 'no', signalFor(s.present)); });
  html += `</div>`;

  html += `<div class="dash-section"><div class="dash-section-title">Appearance</div>
    <div class="theme-control" id="theme-control-inner">
      <button data-theme-choice="auto">Auto</button>
      <button data-theme-choice="dark">Dark</button>
      <button data-theme-choice="light">Light</button>
    </div></div>`;

  return html;
}

function setDashboardView(view) {
  if (!DASHBOARD_VIEWS.includes(view)) return;
  currentDashboardView = view;
  document.querySelectorAll('.dashboard-view-btn').forEach((btn) => {
    btn.setAttribute('aria-selected', String(btn.dataset.view === view));
  });
  renderCurrentDashboardView();
}
document.querySelectorAll('.dashboard-view-btn').forEach((btn) => {
  btn.addEventListener('click', () => setDashboardView(btn.dataset.view));
});

function openDashboard() {
  els.dashboardBackdrop.classList.remove('is-closing');
  els.dashboardBackdrop.classList.add('is-open');
  setDashboardView(currentDashboardView);
  refreshDashboard().then(wireThemeButtonsInDashboard);
}
function closeDashboard() {
  els.dashboardBackdrop.classList.add('is-closing');
  els.dashboardBackdrop.classList.remove('is-open');
}
els.chevron.addEventListener('click', openDashboard);
els.dashboardClose.addEventListener('click', closeDashboard);

function wireThemeButtonsInDashboard() {
  const current = localStorage.getItem('theme-preference') || 'auto';
  document.querySelectorAll('#theme-control-inner button').forEach((btn) => {
    btn.setAttribute('aria-pressed', String(btn.dataset.themeChoice === current));
    btn.addEventListener('click', () => setThemePreference(btn.dataset.themeChoice));
  });
}

// ---------------------------------------------------------------- theme --
function applyFromOS(mql) {
  document.documentElement.setAttribute('data-theme', mql.matches ? 'dark' : 'light');
}
function setThemePreference(pref) {
  localStorage.setItem('theme-preference', pref);
  const mql = window.matchMedia('(prefers-color-scheme: dark)');
  const theme = pref === 'light' ? 'light' : pref === 'dark' ? 'dark' : (mql.matches ? 'dark' : 'light');
  document.documentElement.setAttribute('data-theme', theme);
  wireThemeButtonsInDashboard();
}
(function initThemeWatcher() {
  const mql = window.matchMedia('(prefers-color-scheme: dark)');
  mql.addEventListener('change', () => {
    if ((localStorage.getItem('theme-preference') || 'auto') === 'auto') applyFromOS(mql);
  });
})();

// --------------------------------------------------------------- startup --
let startupDone = false;

async function runStartup() {
  const greetingPromise = fetchGreeting();

  if (reducedMotion) {
    // 06_STARTUP_EXPERIENCE §6.9 — the complete reduced-motion sequence,
    // not just the tree: wordmark and bloom still fade (--d-3, the one
    // motion this mode keeps), but the mic, composer, chevron, footer
    // hint, and greeting must reach opacity 1 too, or the founder is
    // left looking at a tree with no way to speak or type.
    tree.renderStaticFrame();
    els.wordmark.style.transitionDuration = 'var(--d-3)';
    els.wordmark.classList.add('is-visible');
    els.fieldBase.classList.add('is-visible');
    els.bloom.style.transitionDuration = 'var(--d-3), var(--d-3)';
    els.bloom.style.opacity = '0.60';
    await greetingPromise;
    // t=640 — UI affordances and the greeting appear immediately, no
    // entrance transition, unlike the animated cold start's fades.
    [els.micWrap, els.composerWrap, els.chevron, els.footerHint, els.greeting, els.presence].forEach((el) => {
      el.style.transitionDuration = '0ms';
    });
    applyGreeting();
    els.micWrap.classList.add('is-visible');
    els.modeSwitch.classList.add('is-visible');
    els.composerWrap.classList.add('is-visible');
    els.chevron.classList.add('is-visible');
    els.footerHint.classList.add('is-visible');
    finishStartup();
    return;
  }

  tree.start();
  setTimeout(() => els.wordmark.classList.add('is-visible'), 0);
  setTimeout(() => els.fieldBase.classList.add('is-visible'), 400);
  setTimeout(() => tree.beginGrowth(performance.now()), 600);
  setTimeout(() => {
    // §6.4.1 t=1200 — this one entrance fade is --d-6, not the bloom
    // element's own --d-8 default (which the t=2400 step below relies on).
    els.bloom.style.transitionDuration = 'var(--d-6), var(--d-6)';
    els.bloom.style.opacity = '0.25';
  }, 1200);
  setTimeout(() => {
    els.bloom.style.transitionDuration = 'var(--d-8), var(--d-8)';
    els.bloom.style.opacity = '0.60';
  }, 2400);
  setTimeout(() => {
    els.micWrap.classList.add('is-visible');
    els.modeSwitch.classList.add('is-visible');
    els.composerWrap.classList.add('is-visible');
    els.chevron.classList.add('is-visible');
  }, 3400);
  setTimeout(async () => {
    await greetingPromise;
    applyGreeting();
    els.footerHint.classList.add('is-visible');
  }, 3600);

  setTimeout(finishStartup, 4200);

  const fastForward = (ev) => {
    if (startupDone) return;
    document.removeEventListener('keydown', fastForwardKey);
    document.removeEventListener('click', fastForward);
    [els.wordmark, els.fieldBase, els.micWrap, els.composerWrap, els.chevron, els.footerHint].forEach((el) => {
      el.style.transitionDuration = '240ms';
      el.classList.add('is-visible');
    });
    els.bloom.style.transitionDuration = '240ms';
    els.bloom.style.opacity = '0.60';
    finishStartup();
    // §6.7.3 point 7 — a printable key that triggered the fast-forward is
    // captured as the composer's first character, same mechanism (focus
    // now, let the browser's own default action land the keystroke) the
    // post-Ready global handler already uses.
    if (ev && ev.type === 'keydown' && ev.key.length === 1 && !ev.ctrlKey && !ev.metaKey && !ev.altKey) {
      markInteracted();
      expandComposer(true);
    }
  };
  const fastForwardKey = (ev) => { if (ev.key.length === 1 || ev.key === 'Enter') fastForward(ev); };
  document.addEventListener('keydown', fastForwardKey, { once: true });
  document.addEventListener('click', fastForward, { once: true });
}

function finishStartup() {
  if (startupDone) return;
  startupDone = true;
  // The mic's real state (armed / unavailable / error) arrives from
  // founder_edition.voice_pipeline via onVoiceState, whenever its
  // background model-loading thread finishes — independent of the
  // startup timeline, per Product Veda's own rule that initialisation
  // never hurries or blocks the animation (06_STARTUP_EXPERIENCE §6.0).
}

// ----------------------------------------------------- startup diagnostics --
// Founder-requested safety net: if startup ever goes dead again, this says
// exactly which step stopped instead of a silent blank window. Not a
// Product Veda element — a debug/support tool, so it's terse and corner-
// anchored rather than designed into the founder-facing experience.
const DIAG_LABELS = {
  webview_loaded: 'WebView bridge',
  conversation_engine_ready: 'Conversation Engine',
  voice_initialized: 'Voice pipeline',
  stt_loaded: 'STT (Whisper)',
  tts_loaded: 'TTS (Piper)',
  dashboard_ready: 'Dashboard',
};
function renderStartupDiagnostics(checks) {
  const rows = Object.keys(DIAG_LABELS).map((key) => {
    const ok = !!checks[key];
    const mark = ok ? '✓' : '✗';
    const cls = ok ? 'diag-ok' : 'diag-fail';
    return `<div class="diag-row"><span class="${cls}">${mark}</span> ${DIAG_LABELS[key]}</div>`;
  });
  els.startupDiagnostics.innerHTML = rows.join('');
  els.startupDiagnostics.classList.add('is-visible');
}
async function showStartupDiagnostics() {
  const diag = await Bridge.call('get_startup_diagnostics').catch(() => null);
  if (diag === null) {
    // The bridge itself never answered — every check downstream of it is
    // unknown, but "bridge failed" is exactly the one fact worth surfacing.
    renderStartupDiagnostics({ webview_loaded: false });
    return;
  }
  renderStartupDiagnostics({ webview_loaded: true, ...diag });
}

// ------------------------------------------ execution status / prominence --
// Port manifest steps 1/2/6/7/8 (docs/audits/UI_INTEGRATION_AUDIT.md,
// SS7) -- Phase 1 tree prominence + Phase 3 Work Region / Founder
// Completion, wired against the real, already-shipped backend contract
// (master_agent.missions.execution_status.ExecutionStatus, exposed as
// window.pywebview.api.get_execution_status()/confirm_completion() in
// founder_edition/desktop_shell.py). Polled -- this bridge has no push
// channel for execution status the way voice state does.
const EXECUTION_POLL_INTERVAL_MS = 1500;

let executionStatus = window.KalpavrikshaWorkState.IDLE_EXECUTION;
let lastMessageSignature = null;
let lastChangeAt = Date.now();
let resultAcknowledged = true;
let lastAcknowledgeKey = null;
let prevProminenceLevel = 'ambient';
let completionCompleted = false;
let completionCountdown = 60;
let completionCountdownTimer = null;
let lastCompletionRenderedFor;
// Decision Gate Item 5 -- the one approved celebration trigger: the
// Founder's own "Mark complete" action, idempotent per completion_id, at
// most once per event. Never on app open, never on autonomous `completed`.
const celebratedCompletionIds = new Set();

function normalizeExecutionStatus(raw) {
  if (!raw || typeof raw !== 'object' || Object.keys(raw).length === 0) {
    return window.KalpavrikshaWorkState.IDLE_EXECUTION;
  }
  return {
    status: raw.status ?? null,
    message: raw.message ?? null,
    current_step: raw.current_step ?? null,
    total_steps: raw.total_steps ?? null,
    elapsed_ms: raw.elapsed_ms ?? null,
    timeout_ms: raw.timeout_ms ?? null,
    attempt: raw.attempt ?? null,
    max_attempts: raw.max_attempts ?? null,
    result: raw.result ?? null,
    requires_founder_completion: !!raw.requires_founder_completion,
    completion_id: raw.completion_id ?? null,
    terminal_state: !!raw.terminal_state,
  };
}

// A new *distinct* terminal event (a fresh objective/completion, not a
// second poll of the same one) starts un-acknowledged. Keyed on
// completion_id when present (founder-completion path), else on
// status+message (a plain completed/failed with no completion_id).
function terminalKeyFor(exec) {
  if (!exec.terminal_state && exec.status !== 'failed') return null;
  return exec.completion_id || `${exec.status}:${exec.message || ''}`;
}

function applyProminence(level) {
  const vars = window.KalpavrikshaProminence.prominenceVars(level);
  const receding = window.KalpavrikshaProminence.isReceding(prevProminenceLevel, level);
  const root = document.documentElement;
  root.setAttribute('data-prominence', level);
  root.setAttribute('data-receding', receding ? 'true' : 'false');
  Object.keys(vars).forEach((key) => root.style.setProperty(key, vars[key]));
  tree.setBreatheAmplitude(parseFloat(vars['--tree-breathe-amp']));
  // See applyBloom()'s own documented ruling: bloom is forced to 0 only
  // at `reduced`; at `minimum` the current state's own bloomOpacity governs.
  currentProminenceLevel = level;
  applyBloom(lastBloomState);
  prevProminenceLevel = level;
}

function clearWorkRegionSlot() {
  if (completionCountdownTimer) {
    clearInterval(completionCountdownTimer);
    completionCountdownTimer = null;
  }
  els.workRegionSlot.innerHTML = '';
}

// Renders the Work Region -- WorkRegion.tsx ported to vanilla DOM. Renders
// NOTHING at all when presentation.visible is false (the idle guarantee):
// no wrapper, no reserved height.
function renderWorkRegion(presentation, timing) {
  if (!presentation.visible) {
    clearWorkRegionSlot();
    return;
  }
  const region = document.createElement('div');
  region.className = 'kv-work-region';
  region.dataset.tone = presentation.tone;
  region.setAttribute('role', 'status');
  region.setAttribute('aria-live', 'polite');
  region.setAttribute('aria-atomic', 'true');

  const headline = document.createElement('p');
  headline.className = 'kv-work-region__headline';
  headline.textContent = presentation.headline;
  region.appendChild(headline);

  if (presentation.supporting !== null) {
    const supporting = document.createElement('p');
    supporting.className = 'kv-work-region__supporting';
    supporting.textContent = presentation.supporting;
    region.appendChild(supporting);
  }

  if (timing.steps !== null) {
    const bar = document.createElement('div');
    bar.className = 'kv-work-region__step-bar';
    bar.setAttribute('role', 'progressbar');
    bar.setAttribute('aria-valuenow', String(timing.steps.current));
    bar.setAttribute('aria-valuemin', '1');
    bar.setAttribute('aria-valuemax', String(timing.steps.total));
    bar.setAttribute('aria-label', `Step ${timing.steps.current} of ${timing.steps.total}`);
    for (let i = 0; i < timing.steps.total; i++) {
      const segment = document.createElement('div');
      segment.className = i < timing.steps.current
        ? 'kv-work-region__step-segment kv-work-region__step-segment--filled'
        : 'kv-work-region__step-segment';
      bar.appendChild(segment);
    }
    region.appendChild(bar);
  }

  els.workRegionSlot.innerHTML = '';
  els.workRegionSlot.appendChild(region);
}

// Renders the Founder Completion flow -- CompletionRequest.tsx ported to
// vanilla DOM. Exactly five elements (HYPER_UI_UX_REVIEW SS Founder
// Completion Experience): summary, evidence (collapsed; this backend
// contract carries no evidence rows, so this section never renders --
// an honest absence, not a stub), consequence, actions, undo window.
//
// "Send back" is rendered per the five-element contract but stays
// disabled: no backend counterpart to confirm_completion() exists for it
// (mission_control.py has confirm_completion() only -- checked during
// this port; reject()/defer() operate on a different id namespace,
// approval_id, for a different subsystem). Recorded here, not silently
// wired to the wrong call.
function renderCompletionRequest(exec) {
  if (exec.completion_id !== lastCompletionRenderedFor) {
    completionCompleted = false;
    completionCountdown = 60;
    if (completionCountdownTimer) {
      clearInterval(completionCountdownTimer);
      completionCountdownTimer = null;
    }
    lastCompletionRenderedFor = exec.completion_id;
  }

  const root = document.createElement('div');
  root.className = 'kv-completion';
  root.dataset.completed = completionCompleted ? 'true' : 'false';

  const summary = document.createElement('p');
  summary.className = 'kv-completion__summary';
  summary.textContent = exec.result || exec.message || 'Ready for your review';
  root.appendChild(summary);

  // Element 3: consequence.
  const consequence = document.createElement('p');
  consequence.className = 'kv-completion__consequence';
  consequence.textContent = exec.terminal_state
    ? 'Marking complete will close this mission.'
    : 'Marking complete will signal that this step is done.';

  const hasActions = exec.completion_id !== null;

  if (completionCompleted) {
    const undo = document.createElement('div');
    undo.className = 'kv-completion__undo';
    const label = document.createElement('span');
    label.className = 'kv-completion__undo-label';
    label.textContent = 'Marked complete';
    const sep = document.createElement('span');
    sep.className = 'kv-completion__undo-separator';
    sep.setAttribute('aria-hidden', 'true');
    sep.textContent = '·';
    undo.appendChild(label);
    undo.appendChild(sep);
    if (completionCountdown > 0) {
      const undoBtn = document.createElement('button');
      undoBtn.type = 'button';
      undoBtn.className = 'kv-completion__undo-action';
      undoBtn.textContent = 'undo';
      undoBtn.addEventListener('click', () => {
        completionCompleted = false;
        completionCountdown = 60;
        if (completionCountdownTimer) { clearInterval(completionCountdownTimer); completionCountdownTimer = null; }
        renderCompletionRequest(executionStatus);
      });
      const countdown = document.createElement('span');
      countdown.className = 'kv-completion__undo-countdown';
      countdown.setAttribute('aria-live', 'off');
      countdown.textContent = `${completionCountdown}s`;
      undo.appendChild(undoBtn);
      undo.appendChild(countdown);
    } else {
      const done = document.createElement('span');
      done.className = 'kv-completion__undo-countdown';
      done.textContent = 'done';
      undo.appendChild(done);
    }
    root.appendChild(consequence);
    root.appendChild(undo);
  } else {
    const actions = document.createElement('div');
    actions.className = 'kv-completion__actions';

    const primary = document.createElement('button');
    primary.type = 'button';
    primary.className = 'kv-completion__action-primary';
    primary.textContent = 'Mark complete';
    primary.disabled = !hasActions;
    if (!hasActions) primary.title = 'No completion ID — actions are unavailable';
    primary.addEventListener('click', async () => {
      if (!hasActions) return;
      completionCompleted = true;
      completionCountdown = 60;
      renderCompletionRequest(executionStatus);
      completionCountdownTimer = setInterval(() => {
        completionCountdown = Math.max(0, completionCountdown - 1);
        renderCompletionRequest(executionStatus);
        if (completionCountdown === 0 && completionCountdownTimer) {
          clearInterval(completionCountdownTimer);
          completionCountdownTimer = null;
        }
      }, 1000);
      // The approved celebration trigger, and only this one: the
      // Founder's decision landing, not the system finishing work.
      // Idempotent per completion_id -- clicking twice (e.g. after using
      // undo and completing again) never re-fires it.
      if (exec.completion_id && !celebratedCompletionIds.has(exec.completion_id)) {
        celebratedCompletionIds.add(exec.completion_id);
        const burstMs = (window.KALPAVRIKSHA_TREE_CELEBRATION_PARAMS || {}).pulsePeriod || 2200;
        tree.celebrate();
        applyBloom('celebration');
        setTimeout(() => applyBloom(currentTreeState), burstMs);
      }
      await Bridge.call('confirm_completion', exec.completion_id).catch(() => {});
    });

    const secondary = document.createElement('button');
    secondary.type = 'button';
    secondary.className = 'kv-completion__action-secondary';
    secondary.textContent = 'Send back';
    // See this function's own docstring: no backend action exists for
    // this yet -- disabled honestly rather than wired to nothing.
    secondary.disabled = true;
    secondary.title = 'Send back is not yet wired to a backend action';

    actions.appendChild(primary);
    actions.appendChild(secondary);
    root.appendChild(consequence);
    root.appendChild(actions);
  }

  els.workRegionSlot.innerHTML = '';
  els.workRegionSlot.appendChild(root);
}

function applyExecutionStatus(exec) {
  const signature = `${exec.status}|${exec.message}|${exec.current_step}|${exec.attempt}|${exec.result}`;
  if (signature !== lastMessageSignature) {
    lastMessageSignature = signature;
    lastChangeAt = Date.now();
  }
  const msSinceLastChange = Date.now() - lastChangeAt;

  const key = terminalKeyFor(exec);
  if (key !== null && key !== lastAcknowledgeKey) {
    // A genuinely new terminal event this poll has not seen before.
    resultAcknowledged = false;
    lastAcknowledgeKey = key;
  }

  const timing = window.KalpavrikshaTiming.presentTiming({ exec, msSinceLastChange });
  const presentation = window.KalpavrikshaWorkState.presentWork(exec, timing.line);

  const prominenceInput = {
    status: exec.status,
    requires_founder_completion: exec.requires_founder_completion,
    terminal_state: exec.terminal_state,
    resultAcknowledged: resultAcknowledged,
  };
  const decision = window.KalpavrikshaProminence.deriveProminence(prominenceInput);
  applyProminence(decision.level);

  if (window.KalpavrikshaWorkState.isAwaitingCompletion(exec)) {
    renderCompletionRequest(exec);
  } else {
    renderWorkRegion(presentation, timing);
  }

  // Drive the tree's own character state from this same poll -- resultAcknowledged
  // above is already final for this cycle, so executionTreeState() (arbiter,
  // near the top of this file) sees exactly what deriveProminence() just saw.
  recomputeTreeState();
}

async function pollExecutionStatus() {
  let raw = null;
  try {
    raw = await Bridge.call('get_execution_status');
  } catch (e) {
    raw = null;
  }
  executionStatus = normalizeExecutionStatus(raw);
  applyExecutionStatus(executionStatus);
}

// ------------------------------------------------------------------ boot --
let appMode = 'both';  // session-level: 'local' | 'ai_mode' | 'both'

async function setAppMode(mode) {
  const result = await Bridge.call('set_mode', mode).catch(() => null);
  if (result && result.mode) {
    appMode = result.mode;
    updateModeButtons();
  }
}

function updateModeButtons() {
  document.querySelectorAll('.mode-btn').forEach(b => {
    b.classList.toggle('is-active', b.dataset.mode === appMode);
  });
}

async function boot() {
  const seed = await Bridge.call('get_founder_seed').catch(() => 1);
  tree.build(seed >>> 0);

  runStartup();
  showStartupDiagnostics();
  // Set default mode to BOTH at startup
  await Bridge.call('set_mode', 'both').catch(() => {});
  updateModeButtons();
  // Re-check diagnostics after voice models have had time to load
  setTimeout(async () => {
    const diag = await Bridge.call('get_startup_diagnostics').catch(() => null);
    if (diag) renderStartupDiagnostics(diag);
  }, 15000);
  setTimeout(async () => {
    const diag = await Bridge.call('get_startup_diagnostics').catch(() => null);
    if (diag) renderStartupDiagnostics(diag);
  }, 45000);

  // Port manifest step 7/8 -- start polling execution status once the
  // bridge is reachable. Applies ambient prominence immediately so the
  // tree/veil carry correct data-prominence/CSS vars from first paint,
  // not only after the first poll resolves.
  applyProminence('ambient');
  pollExecutionStatus();
  setInterval(pollExecutionStatus, EXECUTION_POLL_INTERVAL_MS);
}

boot();
