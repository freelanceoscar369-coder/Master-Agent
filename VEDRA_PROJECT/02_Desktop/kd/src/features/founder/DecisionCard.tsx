/**
 * DecisionCard — the full consequence card for a single JudgmentRequest.
 *
 * Used in two places:
 *   · Dashboard (Screen 01) — one card at a time in the main decision slot
 *   · FounderConsole → Judgment tab → Needs-you tier
 *
 * This is the ONLY implementation. Any change to the judgment card layout must
 * be made here and nowhere else.
 *
 * Design Constitution invariants enforced here:
 *   · Needs-you items are NEVER selectable or batchable (no checkboxes, no
 *     select-all applies). Enforced by omitting all selection affordances.
 *   · Rank justification is on-demand only (expandable, never always-visible).
 *   · SilenceDefault fires-at is expressed in prose via formatRelative.
 *   · Confidence is rendered via ConfidenceMark — no numeric path.
 *   · Consequence is rendered via ConsequenceGrid — the full quartet.
 *   · Actions come from request.actions — never hard-coded labels.
 */

import React, { useState } from 'react';
import type { JudgmentRequest, Principal, Verdict, ReceiptId } from '@/kernel/types';
import {
  Panel,
  Kicker,
  H3,
  Body,
  Dim,
  Mono,
  Button,
  Tag,
  ConfidenceMark,
  ConsequenceGrid,
  SelectField,
} from '@/components';
import { formatRelative } from '@/lib/format';
import './DecisionCard.css';

/* ── props ──────────────────────────────────────────────────────────────── */

export interface DecisionCardProps {
  request: JudgmentRequest;
  principals: readonly Principal[];
  onVerdict: (
    id: string,
    verdict: Verdict,
  ) => Promise<{ receiptId: ReceiptId; undoWindowSeconds: number } | null>;
  /** Called after a successful verdict so the parent can advance to next item */
  onAdvance?: () => void;
  pending?: boolean;
  className?: string;
}

/* ── component ──────────────────────────────────────────────────────────── */

export function DecisionCard({
  request,
  principals,
  onVerdict,
  onAdvance,
  pending = false,
  className,
}: DecisionCardProps): React.JSX.Element {
  const [showRank, setShowRank] = useState(false);
  const [delegateTo, setDelegateTo] = useState('');
  const [localPending, setLocalPending] = useState(false);
  const [mutationError, setMutationError] = useState<string | undefined>(undefined);

  const isPending = pending || localPending;

  const delegateOptions = [
    { value: '', label: 'Choose person…' },
    ...principals.map((p) => ({ value: p.id, label: `${p.name} — ${p.role}` })),
  ];

  async function handleVerdict(verdict: Verdict): Promise<void> {
    setLocalPending(true);
    setMutationError(undefined);
    const result = await onVerdict(request.id, verdict);
    setLocalPending(false);
    if (result !== null) {
      onAdvance?.();
    }
  }

  function handleActionClick(
    intent: 'approve' | 'decline' | 'discuss' | 'delegate' | 'snooze',
    key: string,
  ): void {
    if (intent === 'approve') {
      void handleVerdict({ kind: 'approve' });
    } else if (intent === 'decline') {
      void handleVerdict({ kind: 'decline' });
    } else if (intent === 'delegate') {
      if (delegateTo !== '') {
        void handleVerdict({ kind: 'delegate', to: delegateTo });
      }
    } else if (intent === 'snooze') {
      // Snooze 24h by default; a real implementation would ask for duration
      const until = new Date(Date.now() + 86_400_000).toISOString();
      void handleVerdict({ kind: 'snooze', until });
    }
    // 'discuss' does not call submitVerdict; it's informational
    void key; // key is carried for future routing
  }

  const tierLabel =
    request.tier === 'needs-you' ? 'Needs you' : 'Sweep';
  const tierTone = request.tier === 'needs-you' ? 'needs-you' as const : 'muted' as const;

  const classes = ['dc-card', className].filter(Boolean).join(' ');

  return (
    <Panel className={classes}>
      {/* Kicker: category · trigger · tier */}
      <div className="dc-card__header">
        <Kicker tone={tierTone}>
          {request.category} · {request.trigger} · {tierLabel}
        </Kicker>
        {request.deadline !== undefined && (
          <Mono className="dc-card__deadline">
            Due {formatRelative(request.deadline)}
          </Mono>
        )}
      </div>

      {/* Title */}
      <H3 className="dc-card__title">{request.title}</H3>

      {/* Recommendation prose */}
      <Body className="dc-card__recommendation">{request.recommendation}</Body>

      {/* Confidence */}
      <ConfidenceMark confidence={request.confidence} className="dc-card__confidence" />

      {/* Consequence quartet */}
      <ConsequenceGrid consequence={request.consequence} className="dc-card__consequence" />

      {/* Silence default — stated in words, always present (Principle VII) */}
      <div className="dc-card__silence">
        <Mono className="dc-card__silence-label">If you do nothing</Mono>
        <Body className="dc-card__silence-text">
          {request.silenceDefault.action} by{' '}
          {formatRelative(request.silenceDefault.firesAt)}.
          {request.silenceDefault.staleIfFactsChange && (
            <span className="dc-card__silence-caveat">
              {' '}Will be re-verified before firing.
            </span>
          )}
        </Body>
      </div>

      {/* Rank justification — on demand */}
      <div className="dc-card__rank">
        <button
          type="button"
          className="dc-card__rank-toggle"
          onClick={() => setShowRank((v) => !v)}
          aria-expanded={showRank}
        >
          <Mono>Why ranked #{request.rank.position}</Mono>
        </button>
        {showRank && (
          <Body className="dc-card__rank-text">{request.rank.justification}</Body>
        )}
      </div>

      {/* Mutation error */}
      {mutationError !== undefined && (
        <Body className="dc-card__error" role="alert">
          {mutationError}
        </Body>
      )}

      {/* Delegate selector (shown alongside delegate actions) */}
      {request.actions.some((a) => a.intent === 'delegate') && (
        <SelectField
          label="Delegate to"
          value={delegateTo}
          onChange={(e) => setDelegateTo(e.target.value)}
          options={delegateOptions}
          className="dc-card__delegate-select"
        />
      )}

      {/* Actions */}
      <div className="dc-card__actions">
        {request.actions.map((action) => {
          const isDelegate = action.intent === 'delegate';
          const disableDelegate = isDelegate && delegateTo === '';

          const variantMap: Record<
            'approve' | 'decline' | 'discuss' | 'delegate' | 'snooze',
            'primary' | 'default' | 'ghost'
          > = {
            approve: 'primary',
            decline: 'default',
            discuss: 'ghost',
            delegate: 'default',
            snooze: 'ghost',
          };

          return (
            <Button
              key={action.key}
              variant={variantMap[action.intent]}
              size="md"
              disabled={isPending || disableDelegate}
              onClick={() => handleActionClick(action.intent, action.key)}
            >
              {action.label}
            </Button>
          );
        })}
      </div>

      {/* Domain tag */}
      <div className="dc-card__footer">
        <Tag tone="muted">{request.domain}</Tag>
        <Mono className="dc-card__opened">
          Opened {formatRelative(request.openedAt)}
        </Mono>
      </div>
    </Panel>
  );
}
