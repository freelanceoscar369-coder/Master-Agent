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
const Bridge = {
  ready: false,
  async call(name, ...args) {
    if (!window.pywebview || !window.pywebview.api) {
      await new Promise((resolve) => {
        window.addEventListener('pywebviewready', resolve, { once: true });
      });
    }
    return window.pywebview.api[name](...args);
  },
};

// ------------------------------------------------------------- elements --
const canvas = $('#tree');
const els = {
  wordmark: $('.wordmark'),
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
  conversationScroll: $('.conversation-scroll'),
  conversation: $('.conversation'),
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
// 02_ANIMATION_SYSTEM §2.2 — `bloomTransDuration` per state. The base
// CSS rule (.bloom) declares --d-8 as the default; states that specify a
// different token override it inline here rather than in the stylesheet,
// since the duration is a per-state animation parameter, not a static
// layout fact.
const BLOOM_TRANS_DURATION = {
  idle: 'var(--d-8)', listening: 'var(--d-8)', thinking: 'var(--d-8)',
  speaking: 'var(--d-4)', waiting: 'var(--d-8)', celebration: 'var(--d-6)',
};
function applyBloom(state) {
  const p = { idle: 0.60, listening: 1.0, thinking: 0.85, speaking: 1.0, waiting: 0.70, celebration: 1.0 }[state] ?? 0.60;
  const dur = BLOOM_TRANS_DURATION[state] || 'var(--d-8)';
  els.bloom.style.transitionDuration = `${dur}, ${dur}`;
  els.bloom.style.opacity = String(p);
  const hueVar = { idle: '--s-live', listening: '--s-live', thinking: '--s-live', speaking: '--s-live', waiting: '--s-attend', celebration: '--s-bloom' }[state] ?? '--s-live';
  const alpha = { idle: 0.055, listening: 0.055, thinking: 0.065, speaking: 0.050, waiting: 0.045, celebration: 0.075 }[state] ?? 0.055;
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

// 'speaking' is a tree-only concept (02_ANIMATION_SYSTEM §2.2.4) — the
// mic component's own state vocabulary (03_VOICE_EXPERIENCE §3.1) has
// no "speaking" entry, because the founder's mic is not the one making
// sound. It arrives on the same push channel because the same pipeline
// drives both; it updates only the tree, never the mic button/label.
function setVoiceState(name) {
  if (name === 'speaking') {
    tree.setState('speaking');
    return;
  }
  setMicState(name);
}

function setMicState(name) {
  micState = name;
  els.mic.dataset.state = name;
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

  // Tree states (02_ANIMATION_SYSTEM §2.2) are a different, six-member
  // vocabulary from mic states (03_VOICE_EXPERIENCE §3.1) — 'armed' is a
  // mic state only. Armed maps to tree Idle: the tree enters Listening
  // only once the founder is actually being heard.
  if (name === 'listening' || name === 'capturing-speech') tree.setState('listening');
  else if (name === 'processing') tree.setState('thinking');
  else if (name === 'armed' || name === 'idle' || name === 'muted') tree.setState('idle');

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
els.composerInput.addEventListener('focus', () => expandComposer(false));
els.composerInput.addEventListener('input', () => {
  markInteracted();
  els.composer.classList.toggle('has-text', !!els.composerInput.textContent.trim());
});
els.composerInput.addEventListener('blur', () => setTimeout(collapseComposerIfEmpty, 100));
els.composerInput.addEventListener('keydown', (ev) => {
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
  if (ev.key.length === 1 && !ev.ctrlKey && !ev.metaKey && !ev.altKey) {
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
function showThinkingSoon() {
  thinkingTimer = setTimeout(() => {
    els.thinking.classList.add('is-visible');
    tree.setState('thinking');
  }, 400); // --d-gate
}
function hideThinking() {
  clearTimeout(thinkingTimer);
  els.thinking.classList.remove('is-visible');
}

async function submitMessage(text, source) {
  if (!text.trim()) return;
  markInteracted();
  enterConversationView();
  appendFounderMessage(text, new Date());
  showThinkingSoon();
  try {
    const result = await Bridge.call('send_message', text, source);
    hideThinking();
    if (result && result.reply) {
      appendSomeshMessage(result.reply);
    }
    // Idle now; if voice.speak() (already fired, Python side) actually
    // has a TTS voice loaded, an onVoiceState('speaking') push follows
    // within a frame or two and moves the tree again. If it does not
    // (no voice loaded), the tree correctly stays here rather than
    // lingering in Thinking.
    tree.setState('idle');
    refreshDashboard();
  } catch (e) {
    hideThinking();
    tree.setState('waiting');
  }
}

// ------------------------------------------------------------ dashboard --
function signalFor(bool) { return bool ? 'settled' : 'attend'; }

function row(label, value, signal) {
  return `<div class="dash-row"><span class="dash-row__label">${label}</span>
    <span class="dash-row__value"${signal ? ` data-signal="${signal}"` : ''}>${value}</span></div>`;
}

async function refreshDashboard() {
  try {
    const d = await Bridge.call('get_dashboard');
    els.dashboardBody.innerHTML = renderDashboard(d);
  } catch (e) { /* honest absence — leave the last known view */ }
}

function renderDashboard(d) {
  const identity = d.identity || {};
  const session = d.session || {};
  const presence = d.presence || {};
  const coverage = presence.coverage;
  const desktop = d.desktop;
  const sources = d.sources || [];

  let html = `<div class="dashboard-title">${identity.assistant_name || 'Somesh'}</div>
    <div class="dashboard-sub">for ${identity.founder_name || ''} · ${identity.edition || ''}</div>`;

  html += `<div class="dash-section"><div class="dash-section-title">Session</div>`;
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

function openDashboard() {
  els.dashboardBackdrop.classList.remove('is-closing');
  els.dashboardBackdrop.classList.add('is-open');
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
    tree.renderStaticFrame();
    els.fieldBase.classList.add('is-visible');
    els.bloom.style.opacity = '0.60';
    await greetingPromise;
    finishStartup();
    return;
  }

  tree.start();
  setTimeout(() => els.wordmark.classList.add('is-visible'), 0);
  setTimeout(() => els.fieldBase.classList.add('is-visible'), 400);
  setTimeout(() => tree.beginGrowth(performance.now()), 600);
  setTimeout(() => { els.bloom.style.opacity = '0.25'; }, 1200);
  setTimeout(() => { els.bloom.style.opacity = '0.60'; }, 2400);
  setTimeout(() => {
    els.micWrap.classList.add('is-visible');
    els.composerWrap.classList.add('is-visible');
    els.chevron.classList.add('is-visible');
  }, 3400);
  setTimeout(async () => {
    await greetingPromise;
    applyGreeting();
    els.footerHint.classList.add('is-visible');
  }, 3600);

  setTimeout(finishStartup, 4200);

  const fastForward = () => {
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
  };
  const fastForwardKey = (ev) => { if (ev.key.length === 1 || ev.key === 'Enter') fastForward(); };
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

// ------------------------------------------------------------------ boot --
(async function boot() {
  const seed = await Bridge.call('get_founder_seed').catch(() => 1);
  tree.build(seed >>> 0);
  runStartup();
})();
