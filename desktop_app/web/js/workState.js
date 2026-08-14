/* Work state translation -- technical state to founder language. Ported
 * from the HyperAgent reference implementation (surface/src/presentation/
 * workState.ts, approved verdict C, HYPER_UI_UX_REVIEW SS Task-State
 * Experience). Logic, thresholds, and copy are unchanged from that
 * source; only the language is (TypeScript -> plain JS).
 *
 * THE GOVERNING RULE: show what is being DONE, not what state the
 * machine is IN. `message` describes reality; `status` describes the
 * machine. The founder cares about the first, so whenever `message` is
 * present the status name is invisible -- the status name is NEVER
 * shown to the founder anywhere in this module.
 *
 * BACKEND BOUNDARY: this module reads the authoritative ExecutionStatus
 * contract -- confirmed, during this port, to be
 * src/master_agent/missions/execution_status.py::ExecutionStatus.as_dict(),
 * already wired end to end (window.pywebview.api.get_execution_status(),
 * exposed in founder_edition/desktop_shell.py). The spellings below are
 * copied verbatim from that module, not guessed.
 */
'use strict';

(function () {
  var IDLE_EXECUTION = {
    status: 'idle', message: null, current_step: null, total_steps: null,
    elapsed_ms: null, timeout_ms: null, attempt: null, max_attempts: null,
    result: null, requires_founder_completion: false, completion_id: null,
    terminal_state: false,
  };

  /* ── state -> language ────────────────────────────────────────────── */

  var STATE_LANGUAGE = {
    understanding: 'Reading your request',
    planning: 'Working out the steps',
    awaiting_approval: 'Needs your approval',
    executing: 'Working',
    observing: 'Watching for the result',
    verifying: 'Checking the result',
    recovering: 'Retrying',
    awaiting_founder_completion: 'Ready for your review',
    completed: 'Done',
    failed: "Couldn't finish",
    blocked: 'Stopped -- needs you',
  };

  var WORKING_STATES = [
    'understanding', 'planning', 'executing', 'observing', 'verifying', 'recovering',
  ];

  var KNOWN_STATUSES = [
    'idle', 'understanding', 'planning', 'awaiting_approval', 'executing',
    'observing', 'verifying', 'recovering', 'awaiting_founder_completion',
    'completed', 'failed', 'blocked',
  ];

  function isKnownStatus(status) {
    return status !== null && KNOWN_STATUSES.indexOf(status) !== -1;
  }

  var UNKNOWN_STATUS_FALLBACK = 'Working';

  /* ── the translation ──────────────────────────────────────────────── */

  /**
   * @param {object} exec ExecutionStatus (see IDLE_EXECUTION shape)
   * @param {string|null} [supporting] pre-computed supporting line (timing.js)
   * @returns {{visible: boolean, headline: string, supporting: string|null,
   *            tone: string, needsFounder: boolean, source: string}}
   */
  function presentWork(exec, supporting) {
    if (supporting === undefined) supporting = null;
    var status = exec.status, message = exec.message, result = exec.result;
    var requiresFounderCompletion = exec.requires_founder_completion;

    var needsFounder =
      requiresFounderCompletion ||
      status === 'awaiting_founder_completion' ||
      status === 'awaiting_approval' ||
      status === 'blocked';

    /* 1 -- A human is required. Outranks everything, including a message. */
    if (needsFounder) {
      var headline = status === 'awaiting_approval' ? STATE_LANGUAGE.awaiting_approval
        : status === 'blocked' ? STATE_LANGUAGE.blocked
        : STATE_LANGUAGE.awaiting_founder_completion;
      return {
        visible: true, headline: headline, supporting: message !== null ? message : supporting,
        tone: 'attend', needsFounder: true, source: 'state',
      };
    }

    /* 2 -- Failure. What broke leads; the machine's word for it does not. */
    if (status === 'failed') {
      return {
        visible: true, headline: message !== null ? message : STATE_LANGUAGE.failed,
        supporting: message !== null ? STATE_LANGUAGE.failed : supporting,
        tone: 'risk', needsFounder: false, source: message !== null ? 'message' : 'state',
      };
    }

    /* 3 -- Completed. The result is the protagonist; "Done" is the fallback. */
    if (status === 'completed' || exec.terminal_state) {
      return {
        visible: true,
        headline: result !== null ? result : (message !== null ? message : STATE_LANGUAGE.completed),
        supporting: supporting, tone: 'settled', needsFounder: false,
        source: result !== null ? 'result' : (message !== null ? 'message' : 'state'),
      };
    }

    /* 4 -- Work in flight. THE CORE RULE: message wins over status, always. */
    if (status !== null && WORKING_STATES.indexOf(status) !== -1) {
      if (message !== null && message.trim().length > 0) {
        return {
          visible: true, headline: message, supporting: supporting,
          tone: 'live', needsFounder: false, source: 'message',
        };
      }
      return {
        visible: true, headline: STATE_LANGUAGE[status], supporting: supporting,
        tone: 'live', needsFounder: false, source: 'state',
      };
    }

    /* 5 -- Idle. Silence is the correct rendering. The region does not exist. */
    if (status === null || status === 'idle') {
      return {
        visible: false, headline: '', supporting: null,
        tone: 'muted', needsFounder: false, source: 'none',
      };
    }

    /* 6 -- UNRECOGNISED STATUS. Fail safe, never silent -- see workState.ts's
     * own header for why: a one-character contract mismatch must never
     * silently hide genuinely in-flight work. */
    var hasMessage = message !== null && message.trim().length > 0;
    var hasResult = result !== null && String(result).trim().length > 0;
    return {
      visible: true,
      headline: hasMessage ? message : (hasResult ? result : UNKNOWN_STATUS_FALLBACK),
      supporting: supporting, tone: 'live', needsFounder: false,
      source: hasMessage ? 'message' : (hasResult ? 'result' : 'state'),
    };
  }

  function isAwaitingCompletion(exec) {
    return exec.requires_founder_completion || exec.status === 'awaiting_founder_completion';
  }

  /* An open approval is a founder decision too. Kept separate from
   * `isAwaitingCompletion` because the two ask different questions --
   * "is this finished?" versus "may I proceed?" -- and answer to
   * different Mission Control calls. Both render a decision surface;
   * neither is a failure. */
  function isAwaitingApproval(exec) {
    return exec.status === 'awaiting_approval' && !!exec.approval_id;
  }

  window.KalpavrikshaWorkState = {
    IDLE_EXECUTION: IDLE_EXECUTION,
    KNOWN_STATUSES: KNOWN_STATUSES,
    UNKNOWN_STATUS_FALLBACK: UNKNOWN_STATUS_FALLBACK,
    isKnownStatus: isKnownStatus,
    presentWork: presentWork,
    isAwaitingCompletion: isAwaitingCompletion,
    isAwaitingApproval: isAwaitingApproval,
  };
})();
