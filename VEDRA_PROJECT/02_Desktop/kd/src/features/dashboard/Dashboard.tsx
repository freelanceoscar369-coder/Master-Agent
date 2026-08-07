/**
 * Dashboard — Screen 01 v2.
 *
 * Purpose: explain what the AI did and where judgment is required.
 * Nothing else appears here.
 *
 * Layout (12-col):
 *   cols 1–8  — Voice + Vigilance gate + Decision slot
 *   cols 9–12 — Receipt column (lower contrast)
 *   Doorways  — bottom, three mono text links
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useKernel } from '@/kernel/KernelProvider';
import { useAsync, useMutation } from '@/kernel/hooks';
import type { Brief, JudgmentRequest, Verdict, ReceiptId } from '@/kernel/types';
import {
  Skeleton,
  ErrorState,
  EmptyState,
  Panel,
  H3,
  Body,
  Dim,
  Mono,
  Kicker,
  Tag,
  Speech,
  Button,
  UndoToast,
} from '@/components';
import { formatRelative, formatCount } from '@/lib/format';
import { canClaimCalm, describeGaps } from '@/lib/vigilance';
import { Link } from '@/app/router';
import { DecisionCard } from '@/features/founder/DecisionCard';
import './Dashboard.css';

/* ── typewriter ─────────────────────────────────────────────────────────── */

const CHAR_MS = 38;
const CURSOR_LINGER_MS = 420;

interface TypewriterState {
  displayed: string;
  done: boolean;
}

function useTypewriter(full: string): {
  state: TypewriterState;
  complete: () => void;
} {
  const prefersReduced =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const [state, setState] = useState<TypewriterState>(() => ({
    displayed: prefersReduced ? full : '',
    done: prefersReduced,
  }));

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fullRef = useRef(full);
  fullRef.current = full;

  const complete = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setState({ displayed: fullRef.current, done: true });
  }, []);

  useEffect(() => {
    if (prefersReduced) {
      setState({ displayed: full, done: true });
      return;
    }

    setState({ displayed: '', done: false });
    let idx = 0;

    intervalRef.current = setInterval(() => {
      idx += 1;
      const slice = fullRef.current.slice(0, idx);
      if (idx >= fullRef.current.length) {
        if (intervalRef.current !== null) clearInterval(intervalRef.current);
        setState({ displayed: slice, done: false });
        // Remove cursor after linger
        setTimeout(() => {
          setState({ displayed: slice, done: true });
        }, CURSOR_LINGER_MS);
      } else {
        setState({ displayed: slice, done: false });
      }
    }, CHAR_MS);

    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
    // full is the stable greeting text; re-run only when it changes
  }, [full, prefersReduced]);

  return { state, complete };
}

/* ── UndoToast manager ──────────────────────────────────────────────────── */

interface ToastInfo {
  receiptIds: readonly ReceiptId[];
  seconds: number;
  message: string;
}

/* ── receipt column ─────────────────────────────────────────────────────── */

interface ReceiptColumnProps {
  brief: Brief;
  onNarrowRule: (receiptId: string) => void;
  onConfirmRule: (receiptId: string) => void;
}

function ReceiptColumn({
  brief,
  onNarrowRule,
  onConfirmRule,
}: ReceiptColumnProps): React.JSX.Element {
  const [expanded, setExpanded] = useState(false);

  return (
    <aside className="db-receipt-col" aria-label="Activity summary">
      {/* Counts */}
      <div className="db-receipt-col__counts">
        <div className="db-receipt-col__count-row">
          <Mono className="db-receipt-col__count-num">
            {formatCount(brief.handledCount)}
          </Mono>
          <Dim className="db-receipt-col__count-label">handled without you</Dim>
        </div>
        <div className="db-receipt-col__count-row">
          <Mono className="db-receipt-col__count-num">
            {formatCount(brief.runningCount)}
          </Mono>
          <Dim className="db-receipt-col__count-label">running right now</Dim>
        </div>
      </div>

      {/* Expand toggle */}
      {brief.flaggedReceipts.length > 0 || brief.disclosures.length > 0 ? (
        <button
          type="button"
          className="db-receipt-col__expand"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
        >
          <Mono>
            {expanded ? 'Hide details' : 'Show details'}
          </Mono>
        </button>
      ) : null}

      {expanded && (
        <div className="db-receipt-col__details">
          {/* Flagged receipts — borderline AI calls */}
          {brief.flaggedReceipts.length > 0 && (
            <section className="db-receipt-col__flagged">
              <Kicker tone="needs-you" className="db-receipt-col__section-label">
                Borderline calls
              </Kicker>
              {brief.flaggedReceipts.map((r) => (
                <Panel key={r.id} className="db-receipt-col__flagged-item">
                  <Body className="db-receipt-col__flagged-action">
                    {r.actionType}
                  </Body>
                  {r.flagged !== undefined && (
                    <>
                      <Dim className="db-receipt-col__flagged-why">
                        {r.flagged.why}
                      </Dim>
                      <div className="db-receipt-col__flagged-actions">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onNarrowRule(r.id)}
                        >
                          Narrow the rule
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onConfirmRule(r.id)}
                        >
                          That was right
                        </Button>
                      </div>
                    </>
                  )}
                  <Mono className="db-receipt-col__flagged-time">
                    {formatRelative(r.at)}
                  </Mono>
                </Panel>
              ))}
            </section>
          )}

          {/* Mistake disclosures — impact → cause → fix → prevention */}
          {brief.disclosures.length > 0 && (
            <section className="db-receipt-col__disclosures">
              <Kicker tone="risk" className="db-receipt-col__section-label">
                Mistakes disclosed
              </Kicker>
              {brief.disclosures.map((d) => (
                <Panel key={d.id} className="db-receipt-col__disclosure">
                  <div className="db-receipt-col__disclosure-row">
                    <Mono className="db-receipt-col__disclosure-step">Impact</Mono>
                    <Body className="db-receipt-col__disclosure-text">{d.impact}</Body>
                  </div>
                  <div className="db-receipt-col__disclosure-row">
                    <Mono className="db-receipt-col__disclosure-step">Cause</Mono>
                    <Body className="db-receipt-col__disclosure-text">{d.cause}</Body>
                  </div>
                  <div className="db-receipt-col__disclosure-row">
                    <Mono className="db-receipt-col__disclosure-step">Fix</Mono>
                    <Body className="db-receipt-col__disclosure-text">{d.fix}</Body>
                  </div>
                  <div className="db-receipt-col__disclosure-row">
                    <Mono className="db-receipt-col__disclosure-step">Prevention</Mono>
                    <Body className="db-receipt-col__disclosure-text">{d.prevention}</Body>
                  </div>
                  <Mono className="db-receipt-col__disclosure-time">
                    {formatRelative(d.at)}
                  </Mono>
                </Panel>
              ))}
            </section>
          )}
        </div>
      )}
    </aside>
  );
}

/* ── decision slot ──────────────────────────────────────────────────────── */

interface DecisionSlotProps {
  requests: readonly JudgmentRequest[];
  onVerdictComplete: (toast: ToastInfo) => void;
}

function DecisionSlot({
  requests,
  onVerdictComplete,
}: DecisionSlotProps): React.JSX.Element {
  const kernel = useKernel();
  const [currentIdx, setCurrentIdx] = useState(0);
  // Transition state: 'idle' | 'out' | 'in'
  const [transition, setTransition] = useState<'idle' | 'out' | 'in'>('idle');

  const principalsState = useAsync(
    useCallback(() => kernel.listPrincipals(), [kernel]),
    [kernel],
  );

  const submitVerdict = useMutation(
    useCallback(
      (client, args: { id: string; verdict: Verdict }) =>
        client.submitVerdict(args.id, args.verdict),
      [],
    ),
  );

  const needsYou = requests
    .filter((r) => r.tier === 'needs-you')
    .sort((a, b) => a.rank.position - b.rank.position);

  const current: JudgmentRequest | undefined = needsYou[currentIdx];

  async function handleVerdict(
    id: string,
    verdict: Verdict,
  ): Promise<{ receiptId: ReceiptId; undoWindowSeconds: number } | null> {
    const result = await submitVerdict.run({ id, verdict });
    if (!result.ok) return null;
    return result.value;
  }

  function handleAdvance(): void {
    if (currentIdx >= needsYou.length - 1) {
      // No more items — just stay at current (empty state will render)
      setCurrentIdx(needsYou.length);
      return;
    }
    // 420ms transition out then in
    setTransition('out');
    setTimeout(() => {
      setCurrentIdx((i) => i + 1);
      setTransition('in');
      setTimeout(() => setTransition('idle'), 420);
    }, 420);
  }

  async function handleVerdictWithToast(
    id: string,
    verdict: Verdict,
  ): Promise<{ receiptId: ReceiptId; undoWindowSeconds: number } | null> {
    const result = await handleVerdict(id, verdict);
    if (result !== null) {
      onVerdictComplete({
        receiptIds: [result.receiptId],
        seconds: result.undoWindowSeconds,
        message: 'Verdict recorded.',
      });
    }
    return result;
  }

  if (current === undefined) {
    return (
      <EmptyState
        headline="Nothing needs you right now."
        body="The AI is handling everything within its current rules. Check back when something escalates."
        tone="done"
        className="db-decision-slot__empty"
      />
    );
  }

  const transitionClass =
    transition === 'out'
      ? 'db-decision-slot--out'
      : transition === 'in'
      ? 'db-decision-slot--in'
      : '';

  return (
    <div className={`db-decision-slot ${transitionClass}`}>
      <DecisionCard
        request={current}
        principals={principalsState.data ?? []}
        onVerdict={handleVerdictWithToast}
        onAdvance={handleAdvance}
        pending={submitVerdict.pending}
      />
      {needsYou.length > 1 && (
        <Mono className="db-decision-slot__position">
          {currentIdx + 1} of {needsYou.length}
        </Mono>
      )}
    </div>
  );
}

/* ── main Dashboard ─────────────────────────────────────────────────────── */

export function Dashboard(): React.JSX.Element {
  const kernel = useKernel();

  const greetingState = useAsync(
    useCallback(() => kernel.getGreeting(), [kernel]),
    [kernel],
  );

  const attestationState = useAsync(
    useCallback(() => kernel.getAttestation(), [kernel]),
    [kernel],
  );

  const briefState = useAsync(
    useCallback(() => kernel.getBrief(), [kernel]),
    [kernel],
  );

  // Typewriter — only start once greeting text is available
  const greetingText = greetingState.data?.text ?? '';
  const { state: typeState, complete: completeTypewriter } = useTypewriter(greetingText);

  // Interrupt typewriter on any keypress or click
  useEffect(() => {
    function interrupt(): void {
      completeTypewriter();
    }
    document.addEventListener('keydown', interrupt);
    document.addEventListener('click', interrupt);
    return () => {
      document.removeEventListener('keydown', interrupt);
      document.removeEventListener('click', interrupt);
    };
  }, [completeTypewriter]);

  // Undo toast
  const [toast, setToast] = useState<ToastInfo | null>(null);

  function handleVerdictComplete(t: ToastInfo): void {
    setToast(t);
  }

  function handleUndo(): void {
    if (toast === null) return;
    void kernel.undo(toast.receiptIds);
    setToast(null);
  }

  return (
    <main className="db-root">
      <div className="db-grid">
        {/* ── Left column (cols 1–8) ── */}
        <div className="db-main">

          {/* Voice — AI speaks first */}
          <section className="db-voice" aria-label="AI voice">
            {greetingState.loading && (
              <Skeleton lines={3} className="db-voice__skeleton" />
            )}
            {greetingState.error !== undefined && (
              <ErrorState
                error={greetingState.error}
                onRetry={greetingState.reload}
              />
            )}
            {greetingState.data !== undefined && (
              <Speech className="db-voice__speech">
                {typeState.displayed}
                {!typeState.done && (
                  <span className="db-voice__cursor" aria-hidden="true" />
                )}
              </Speech>
            )}
          </section>

          {/* Vigilance gate — Bible §1 / module D7
           *
           * CRITICAL: canClaimCalm() must be the gatekeeper.
           * If coverage is incomplete, describeGaps() MUST be rendered
           * instead of any claim that everything is handled.
           * Violating this rule violates the single most important invariant
           * on this screen. — Kalpavriksha Experience Bible §1, module D7
           */}
          <section className="db-vigilance" aria-label="System vigilance">
            {attestationState.loading && (
              <Skeleton lines={1} className="db-vigilance__skeleton" />
            )}
            {attestationState.error !== undefined && (
              <ErrorState
                error={attestationState.error}
                onRetry={attestationState.reload}
              />
            )}
            {attestationState.data !== undefined && (() => {
              const att = attestationState.data;
              if (canClaimCalm(att)) {
                return (
                  <div className="db-vigilance__calm">
                    <Tag tone="done">All systems verified</Tag>
                    <Mono className="db-vigilance__calm-time">
                      Last checked {formatRelative(att.at)}
                    </Mono>
                  </div>
                );
              }
              const gaps = describeGaps(att);
              return (
                <div className="db-vigilance__gap" role="alert">
                  <Tag tone="risk">Coverage incomplete</Tag>
                  {gaps !== null && (
                    <Body className="db-vigilance__gap-text">{gaps}</Body>
                  )}
                  <Mono className="db-vigilance__gap-time">
                    Last checked {formatRelative(att.at)}
                  </Mono>
                </div>
              );
            })()}
          </section>

          {/* Decision slot — top-ranked needs-you request */}
          <section className="db-decision" aria-label="Decision required">
            <H3 className="db-decision__heading">Needs your judgment</H3>
            {briefState.loading && (
              <Skeleton height={320} className="db-decision__skeleton" />
            )}
            {briefState.error !== undefined && (
              <ErrorState
                error={briefState.error}
                onRetry={briefState.reload}
              />
            )}
            {briefState.data !== undefined && (
              <DecisionSlot
                requests={briefState.data.openRequests}
                onVerdictComplete={handleVerdictComplete}
              />
            )}
          </section>
        </div>

        {/* ── Right column (cols 9–12) — receipt / borderline / disclosures ── */}
        {briefState.data !== undefined && (
          <ReceiptColumn
            brief={briefState.data}
            onNarrowRule={(_receiptId) => {
              /* navigate to founder console → rules */
            }}
            onConfirmRule={(_receiptId) => {
              /* acknowledge the borderline call */
            }}
          />
        )}
      </div>

      {/* Doorways — three quiet mono text links, not navigation chrome */}
      <nav className="db-doorways" aria-label="Go deeper">
        <Link to="/console" className="db-doorways__link">
          <Mono>Console</Mono>
        </Link>
        <Link to="/missions" className="db-doorways__link">
          <Mono>Missions</Mono>
        </Link>
        <Link to="/events" className="db-doorways__link">
          <Mono>Events</Mono>
        </Link>
      </nav>

      {/* UndoToast — single transient surface */}
      {toast !== null && (
        <div className="db-toast-anchor" aria-live="polite">
          <UndoToast
            message={toast.message}
            seconds={toast.seconds}
            onUndo={handleUndo}
            onExpire={() => setToast(null)}
          />
        </div>
      )}
    </main>
  );
}
