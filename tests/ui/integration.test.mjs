/**
 * The shipped UI actually uses Hyperagent's renderer, and the questions the
 * founder answers live in the conversation.
 *
 * Two things are checked here that its own 16 tests cannot:
 *
 *   1. the file in `desktop_app/web/js/` IS Hyperagent's file, not a
 *      rewritten equivalent that happens to pass the same suite;
 *   2. `app.js` routes Somesh output through it, and puts interaction
 *      cards in the conversation rather than the Work Region.
 *
 * Read structurally from source. There is no DOM here (no jsdom in this
 * repo), so these assert the wiring; the behaviour itself is proven by
 * running the packaged Windows application, which source inspection is
 * explicitly not allowed to stand in for.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, '..', '..');
const read = (p) => readFileSync(join(REPO, p), 'utf8');

const SHIPPED = 'desktop_app/web/js/messageRender.js';
const HANDOFF = 'VEDRA_PROJECT/01_Assets/UI-UX/messageRender.js';
const APP = read('desktop_app/web/js/app.js');
const INDEX = read('desktop_app/web/index.html');

/* ── one implementation, not two ─────────────────────────────────────── */

test('the shipped renderer is Hyperagent\'s file, unchanged', () => {
  // Newlines normalised: the shipped copy is CRLF on this machine and the
  // handoff is LF. Identity of CONTENT is the property worth holding; a
  // line-ending difference is a checkout artefact, not a divergent twin.
  const norm = (t) => t.split(String.fromCharCode(13)).join('').replace(String.fromCharCode(65279), '');
  const shipped = norm(read(SHIPPED));
  const handoff = norm(read(HANDOFF));
  const marker = '/* ─────────────────────────── shipped-UI exposure';
  const index = shipped.indexOf(marker);

  assert.ok(index > 0, 'the shipped copy has no exposure marker');
  // Everything before the one added block must be byte-identical. A
  // divergent twin would pass the render tests and drift silently.
  assert.equal(shipped.slice(0, index).trimEnd(), handoff.trimEnd());
});

test('the only adaptation is publishing onto window', () => {
  const shipped = read(SHIPPED);
  const added = shipped.slice(shipped.indexOf('/* ─────────────────────────── shipped-UI exposure'));

  assert.ok(added.includes('window.KalpavrikshaMessageRender'));
  // No second sanitiser, no relaxed scheme list, no extra tags.
  for (const smell of ['ALLOWED_SCHEMES =', 'ALLOWED_TAGS =', 'function escapeHtml', 'DOMPurify']) {
    assert.ok(!added.includes(smell), `the adaptation redefines ${smell}`);
  }
});

test('the shipped page loads it as a module', () => {
  assert.match(INDEX, /<script type="module" src="js\/messageRender\.js"><\/script>/);
});

/* ── Somesh output goes through it ───────────────────────────────────── */

test('Somesh messages render through the renderer', () => {
  const fn = APP.slice(APP.indexOf('function appendSomeshMessage'));
  const body = fn.slice(0, fn.indexOf('\nfunction '));

  assert.ok(body.includes('KalpavrikshaMessageRender'));
  assert.ok(body.includes('renderer.renderMessage(text)'));
});

test('founder messages stay plain text', () => {
  const fn = APP.slice(APP.indexOf('function appendFounderMessage'));
  const body = fn.slice(0, fn.indexOf('\nfunction '));

  assert.ok(body.includes(".founder-message__bubble').textContent = text"));
  assert.ok(!body.includes('renderMessage'));
});

test('no unsanitised model output is ever assigned as HTML', () => {
  // Every `innerHTML =` in app.js must take a literal we built or a value
  // from the renderer -- never a raw backend string.
  const assignments = [...APP.matchAll(/\.innerHTML\s*=\s*([^;]+);/g)].map((m) => m[1].trim());
  for (const value of assignments) {
    const safe =
      value.startsWith('`') ||          // a template we wrote
      value.startsWith("'") ||          // a literal we wrote, or clearing
      value.startsWith('"') ||
      value.includes('renderMessage') ||
      value.includes('rows.join') ||    // built from escaped rows
      value === 'html';                 // dashboard, built locally
    assert.ok(safe, `unsafe innerHTML assignment: ${value}`);
  }
});

/* ── interactions are chronological ──────────────────────────────────── */

test('interaction cards append to the conversation', () => {
  const fn = APP.slice(APP.indexOf('function appendInteractionCard'));
  const body = fn.slice(0, fn.indexOf('\n// The founder\'s own review'));

  assert.ok(body.includes('els.conversation.appendChild(wrap)'));
  assert.ok(!body.includes('workRegionSlot'));
});

test('the work region is status-only', () => {
  // Only the two status functions may touch the slot.
  const lines = APP.split('\n');
  const users = [];
  let current = '(top level)';
  lines.forEach((line) => {
    const fn = line.match(/^function\s+(\w+)/);
    if (fn) current = fn[1];
    if (line.includes('workRegionSlot')) users.push(current);
  });
  const allowed = new Set(['clearWorkRegionSlot', 'renderWorkRegion', '(top level)']);
  for (const user of users) {
    assert.ok(allowed.has(user), `${user} writes into the work region`);
  }
});

test('a founder checkpoint says Continue and Stop', () => {
  const fn = APP.slice(APP.indexOf('function renderFounderReview'));
  const body = fn.slice(0, fn.indexOf('\n// A policy decision'));

  assert.ok(body.includes("label: 'Continue'"));
  assert.ok(body.includes("label: 'Stop'"));
  assert.ok(!body.includes("label: 'Approve'"), 'a review must not say Approve');
});

test('a permission approval says Approve and Decline', () => {
  const fn = APP.slice(APP.indexOf('function renderApprovalRequest'));
  const body = fn.slice(0, fn.indexOf('\nfunction applyExecutionStatus'));

  assert.ok(body.includes("label: 'Approve'"));
  assert.ok(body.includes("label: 'Decline'"));
});

test('the two kinds are routed apart by the backend discriminator', () => {
  assert.ok(APP.includes("exec.approval_kind === 'founder_checkpoint'"));
});

test('both decisions call the existing decision path', () => {
  const calls = [...APP.matchAll(/Bridge\.call\('decide_approval',\s*exec\.approval_id,\s*(true|false)/g)];
  assert.equal(calls.length, 4, 'expected Continue/Stop and Approve/Decline');
});

/* ── answered once, and only once ────────────────────────────────────── */

test('a card is not rebuilt while the same question is open', () => {
  assert.ok(APP.includes('if (exec.approval_id === lastApprovalRenderedFor) return;'));
  assert.ok(APP.includes('data-interaction="completion"'));
});

test('answering disables every button and states the decision', () => {
  const fn = APP.slice(APP.indexOf('function appendInteractionCard'));
  const body = fn.slice(0, fn.indexOf('\n// The founder\'s own review'));

  assert.ok(body.includes('buttons.forEach((b) => { b.disabled = true; })'));
  assert.ok(body.includes('row.hidden = true'));
  assert.ok(body.includes('decided.textContent = action.decided'));
});

test('completion is chronological too', () => {
  const fn = APP.slice(APP.indexOf('function renderCompletionRequest'));
  const body = fn.slice(0, fn.indexOf('\nfunction '));

  assert.ok(body.includes('els.conversation.appendChild(card)'));
  assert.ok(!body.includes('els.workRegionSlot.appendChild'));
});

/* ── the file-card rule, enforced by absence ─────────────────────────── */

test('nothing turns a path in prose into an attachment', () => {
  for (const smell of ['\\\\.docx', 'C:\\\\', 'attachmentFromText', 'detectPath']) {
    assert.ok(!new RegExp(smell).test(APP), `app.js scans prose for paths: ${smell}`);
  }
});
