/* Tree prominence — the hierarchy rule, ported from the HyperAgent
 * reference implementation (surface/src/presentation/prominence.ts,
 * approved verdict C, HYPER_UI_UX_REVIEW). Logic and constants are
 * unchanged from that source; only the language is (TypeScript -> plain
 * JS, no build step, matching this app's existing js/*.js files).
 *
 * THE RULE: the tree's prominence is inversely proportional to the work
 * in flight. At 'ambient' the tree is exactly as Product Veda S2
 * specified -- primary and full-bleed. 'reduced' and 'minimum' are
 * active yielding states, not errors or degradations.
 *
 * BACKEND BOUNDARY: this module READS master_agent.missions.execution_
 * status.ExecutionStatus (via window.pywebview.api.get_execution_status,
 * polled by app.js). It adds no field, writes nothing, and encodes no
 * colour/animation/metaphor into backend state. `resultAcknowledged` is
 * client-side view state, computed in app.js, and never sent anywhere.
 *
 * The eleven non-null status spellings below (understanding / planning /
 * awaiting_approval / executing / observing / verifying / recovering /
 * awaiting_founder_completion / completed / failed / blocked) are copied
 * verbatim from that same module's own authoritative source -- confirmed
 * during this port against the real, committed contract:
 * src/master_agent/missions/execution_status.py. 'idle' has no backend
 * spelling; the backend represents it as status === null, treated as
 * idle throughout this module and workState.js.
 */
'use strict';

(function () {
  var RANK = { ambient: 0, reduced: 1, minimum: 2 };

  /* ── the derivation ────────────────────────────────────────────────── */

  /**
   * @param {{status: string|null, requires_founder_completion: boolean,
   *          terminal_state: boolean, resultAcknowledged: boolean}} input
   * @returns {{level: 'ambient'|'reduced'|'minimum', reason: string}}
   */
  function deriveProminence(input) {
    var status = input.status;
    var requiresFounderCompletion = input.requires_founder_completion;
    var terminalState = input.terminal_state;
    var resultAcknowledged = input.resultAcknowledged;

    // 1 -- A human is required. Nothing may outrank this, including the tree.
    if (requiresFounderCompletion) {
      return { level: 'minimum', reason: 'Founder completion is required.' };
    }
    if (status === 'awaiting_founder_completion') {
      return { level: 'minimum', reason: 'Awaiting founder completion.' };
    }
    if (status === 'awaiting_approval') {
      return { level: 'minimum', reason: 'Awaiting founder approval.' };
    }
    if (status === 'awaiting_clarification') {
      return { level: 'minimum', reason: 'Awaiting founder answer.' };
    }
    if (status === 'blocked') {
      return { level: 'minimum', reason: 'Blocked -- needs the founder.' };
    }
    // A failure the founder has not yet seen is a human requirement.
    if (status === 'failed' && !resultAcknowledged) {
      return { level: 'minimum', reason: 'Unacknowledged failure.' };
    }

    // 2 -- Work in flight. The work is the protagonist.
    if (
      status === 'understanding' || status === 'planning' ||
      status === 'executing' || status === 'observing' ||
      status === 'verifying' || status === 'recovering'
    ) {
      return { level: 'reduced', reason: 'Work in flight (' + status + ').' };
    }

    // 3 -- A terminal result the founder has not yet taken in.
    if (terminalState && !resultAcknowledged) {
      return { level: 'reduced', reason: 'Result not yet acknowledged.' };
    }
    if (status === 'completed' && !resultAcknowledged) {
      return { level: 'reduced', reason: 'Completed result not yet acknowledged.' };
    }

    // 4 -- Nothing in flight, nothing waiting. Identity fills the silence.
    return { level: 'ambient', reason: 'No work in flight.' };
  }

  /* ── the visual contract ──────────────────────────────────────────── */

  var VARS = {
    ambient: {
      '--tree-scale': '1', '--tree-alpha': '1',
      '--tree-bloom-opacity': '0.6', '--tree-breathe-amp': '1',
      '--veil-strength': '0.82',
    },
    reduced: {
      '--tree-scale': '0.55', '--tree-alpha': '0.55',
      '--tree-bloom-opacity': '0', '--tree-breathe-amp': '0.42',
      '--veil-strength': '0.92',
    },
    minimum: {
      '--tree-scale': '0.3', '--tree-alpha': '0.32',
      '--tree-bloom-opacity': '0', '--tree-breathe-amp': '0.2',
      '--veil-strength': '0.96',
    },
  };

  function prominenceVars(level) {
    return VARS[level];
  }

  /* ── transition duration ──────────────────────────────────────────── */

  /** The tree yields quickly (--d-6, 600ms) and returns slowly (--d-8,
   * 1400ms) -- see prominence.css for the transition rules this feeds. */
  function transitionToken(from, to) {
    if (from === to) return null;
    return RANK[to] > RANK[from] ? '--d-6' : '--d-8';
  }

  function isReceding(from, to) {
    return RANK[to] > RANK[from];
  }

  window.KalpavrikshaProminence = {
    deriveProminence: deriveProminence,
    prominenceVars: prominenceVars,
    transitionToken: transitionToken,
    isReceding: isReceding,
  };
})();
