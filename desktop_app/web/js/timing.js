/* Timing and progress -- the honesty rules, as code. Ported from the
 * HyperAgent reference implementation (surface/src/presentation/
 * timing.ts, approved verdict C, HYPER_UI_UX_REVIEW SS Timing / Progress
 * Experience). Logic and thresholds are unchanged from that source.
 *
 *   - Elapsed appears only past 10s. Below that it is noise.
 *   - Steps render as "Step 3 of 7" -- DISCRETE, never a percentage.
 *   - A progress bar exists only when total_steps >= 3, segmented, one
 *     segment per step. No continuous bar. No indeterminate bar.
 *   - Timeout NEVER renders as a countdown; only "Taking longer than
 *     usual" in the final quarter of the window.
 *   - Attempts appear only when attempt > 1.
 *   - Liveness is proven by the step message CHANGING. Only when nothing
 *     has changed for 20s do we add "still working".
 *   - No ETA is ever computed.
 *
 * Pure functions. No clock is read here -- `now`/`elapsed` are supplied
 * by app.js's own polling loop, so every output is reproducible.
 */
'use strict';

(function () {
  var ELAPSED_VISIBLE_MS = 10000;
  var MIN_STEPS_FOR_BAR = 3;
  var TIMEOUT_WARN_FRACTION = 0.75;
  var LIVENESS_SILENCE_MS = 20000;

  function formatElapsed(ms) {
    if (ms < 0) return '0s';
    var totalSeconds = Math.floor(ms / 1000);
    if (totalSeconds < 60) return totalSeconds + 's';
    var minutes = Math.floor(totalSeconds / 60);
    var seconds = totalSeconds % 60;
    if (minutes < 60) return seconds === 0 ? minutes + 'm' : minutes + 'm ' + seconds + 's';
    var hours = Math.floor(minutes / 60);
    var rem = minutes % 60;
    return rem === 0 ? hours + 'h' : hours + 'h ' + rem + 'm';
  }

  var NO_TIMING = { line: null, steps: null, runningLong: false, assertingLiveness: false };

  /**
   * @param {{exec: object, msSinceLastChange: number|null}} input
   * @returns {{line: string|null, steps: {current:number,total:number}|null,
   *            runningLong: boolean, assertingLiveness: boolean}}
   */
  function presentTiming(input) {
    var exec = input.exec, msSinceLastChange = input.msSinceLastChange;

    if (exec.terminal_state || exec.status === 'completed' || exec.status === 'failed') {
      return NO_TIMING;
    }
    if (exec.status === null || exec.status === 'idle') return NO_TIMING;

    var fragments = [];

    var attempt = exec.attempt != null ? exec.attempt : 1;
    var maxAttempts = exec.max_attempts != null ? exec.max_attempts : 1;
    if (attempt > 1) {
      fragments.push(maxAttempts > 1
        ? 'Retrying — attempt ' + attempt + ' of ' + maxAttempts
        : 'Retrying — attempt ' + attempt);
    }

    var steps = null;
    var current = exec.current_step, total = exec.total_steps;
    if (current !== null && total !== null && total >= 1 && current >= 1 && current <= total) {
      fragments.push('Step ' + current + ' of ' + total);
      if (total >= MIN_STEPS_FOR_BAR) steps = { current: current, total: total };
    }

    var elapsed = exec.elapsed_ms;
    if (elapsed !== null && elapsed >= ELAPSED_VISIBLE_MS) {
      fragments.push(formatElapsed(elapsed));
    }

    var runningLong = false;
    if (elapsed !== null && exec.timeout_ms !== null && exec.timeout_ms > 0) {
      runningLong = elapsed >= exec.timeout_ms * TIMEOUT_WARN_FRACTION;
      if (runningLong) fragments.push('Taking longer than usual');
    }

    var assertingLiveness = false;
    if (!runningLong && msSinceLastChange !== null && msSinceLastChange >= LIVENESS_SILENCE_MS) {
      assertingLiveness = true;
      fragments.push('Still working');
    }

    return {
      line: fragments.length > 0 ? fragments.join(' · ') : null,
      steps: steps, runningLong: runningLong, assertingLiveness: assertingLiveness,
    };
  }

  window.KalpavrikshaTiming = {
    ELAPSED_VISIBLE_MS: ELAPSED_VISIBLE_MS,
    MIN_STEPS_FOR_BAR: MIN_STEPS_FOR_BAR,
    TIMEOUT_WARN_FRACTION: TIMEOUT_WARN_FRACTION,
    LIVENESS_SILENCE_MS: LIVENESS_SILENCE_MS,
    NO_TIMING: NO_TIMING,
    PRODUCES_ETA: false,
    formatElapsed: formatElapsed,
    presentTiming: presentTiming,
  };
})();
