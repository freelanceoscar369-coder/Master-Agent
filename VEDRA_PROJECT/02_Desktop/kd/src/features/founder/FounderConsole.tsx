/**
 * FounderConsole — the autonomy and judgment surface.
 *
 * Four tabs:
 *   Judgment    — approval queue at volume (three tiers)
 *   Rules       — standing rules with caps, status, actions
 *   Proposals   — the hero moment: should this become a rule?
 *   Scope & Audit — permitted/forbidden, autonomy ratio, dependency audit,
 *                   suspend control
 */

import React, { useCallback, useState } from 'react';
import { useKernel } from '@/kernel/KernelProvider';
import { useAsync, useMutation } from '@/kernel/hooks';
import type {
  JudgmentRequest,
  Principal,
  Verdict,
  ReceiptId,
  RuleId,
  PrincipalId,
} from '@/kernel/types';
import type { KernelError } from '@/kernel/client';
import {
  Tabs,
  Panel,
  H2,
  H3,
  Body,
  Dim,
  Mono,
  Kicker,
  Tag,
  Button,
  Bar,
  Sparkline,
  Skeleton,
  ErrorState,
  EmptyState,
  UndoToast,
} from '@/components';
import type { TabDef } from '@/components';
import {
  formatMoney,
  formatMoneyCompact,
  formatRelative,
  formatPercent,
  formatCount,
  formatDuration,
} from '@/lib/format';
import { DecisionCard } from './DecisionCard';
import './FounderConsole.css';

/* ── tab definitions ────────────────────────────────────────────────────── */

const TABS: readonly TabDef[] = [
  { key: 'judgment', label: 'Judgment' },
  { key: 'rules', label: 'Rules' },
  { key: 'proposals', label: 'Proposals' },
  { key: 'scope', label: 'Scope & Audit' },
];

type TabKey = 'judgment' | 'rules' | 'proposals' | 'scope';

/* ── undo toast state ───────────────────────────────────────────────────── */

interface ToastInfo {
  receiptIds: readonly ReceiptId[];
  seconds: number;
  message: string;
}

/* ═══════════════════════════════════════════════════════════════════════════
   JUDGMENT TAB
   Three tiers: Needs-you · Sweep · Auto-handled
   ═════════════════════════════════════════════════════════════════════════ */

interface JudgmentTabProps {
  onToast: (t: ToastInfo) => void;
}

function JudgmentTab({ onToast }: JudgmentTabProps): React.JSX.Element {
  const kernel = useKernel();

  const requestsState = useAsync(
    useCallback(() => kernel.listJudgmentRequests(), [kernel]),
    [kernel],
  );

  const principalsState = useAsync(
    useCallback(() => kernel.listPrincipals(), [kernel]),
    [kernel],
  );

  const ledgerState = useAsync(
    useCallback(
      () => kernel.queryLedger({ actor: 'kernel', limit: 50 }),
      [kernel],
    ),
    [kernel],
  );

  const submitVerdict = useMutation(
    useCallback(
      (client, args: { id: string; verdict: Verdict }) =>
        client.submitVerdict(args.id, args.verdict),
      [],
    ),
  );

  const submitBatch = useMutation(
    useCallback(
      (
        client,
        args: { ids: readonly string[]; verdict: Verdict },
      ) => client.submitBatchVerdict(args.ids, args.verdict),
      [],
    ),
  );

  const undoMutation = useMutation(
    useCallback(
      (client, ids: readonly ReceiptId[]) => client.undo(ids),
      [],
    ),
  );

  // Sweep selection
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [sweepError, setSweepError] = useState<string | undefined>(undefined);

  const requests = requestsState.data ?? [];
  const needsYou = requests
    .filter((r) => r.tier === 'needs-you')
    .sort((a, b) => a.rank.position - b.rank.position);
  const sweep = requests
    .filter((r) => r.tier === 'sweep')
    .sort((a, b) => a.rank.position - b.rank.position);
  const autoHandled = ledgerState.data?.items ?? [];

  // Aggregate exposure for sweep commit bar
  const selectedItems = sweep.filter((r) => selected.has(r.id));
  const totalExposure = selectedItems.reduce((acc, r) => {
    const cost = r.consequence.cost;
    if ('minor' in cost) return acc + cost.minor;
    return acc;
  }, 0);

  // Pick representative currency from first money cost (INR default)
  const firstMoneyCost = selectedItems
    .map((r) => r.consequence.cost)
    .find((c): c is Extract<typeof c, { currency: string }> => 'minor' in c);
  const currency = firstMoneyCost?.currency ?? 'INR';

  const exposureMoney = {
    currency: currency as 'INR' | 'USD' | 'EUR' | 'GBP',
    minor: totalExposure,
  };

  function toggleSweep(id: string): void {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAllSweep(): void {
    setSelected(new Set(sweep.map((r) => r.id)));
  }

  function clearSweep(): void {
    setSelected(new Set());
  }

  async function commitSweep(): Promise<void> {
    if (selected.size === 0) return;
    setSweepError(undefined);
    const result = await submitBatch.run({
      ids: [...selected],
      verdict: { kind: 'approve' },
    });
    if (!result.ok) {
      if (result.error.code === 'invalid') {
        setSweepError(result.error.message);
      } else {
        setSweepError(result.error.message);
      }
      return;
    }
    setSelected(new Set());
    onToast({
      receiptIds: result.value.receiptIds,
      seconds: result.value.undoWindowSeconds,
      message: `${selected.size} items approved.`,
    });
  }

  async function handleNeedsYouVerdict(
    id: string,
    verdict: Verdict,
  ): Promise<{ receiptId: ReceiptId; undoWindowSeconds: number } | null> {
    const result = await submitVerdict.run({ id, verdict });
    if (!result.ok) return null;
    onToast({
      receiptIds: [result.value.receiptId],
      seconds: result.value.undoWindowSeconds,
      message: 'Verdict recorded.',
    });
    return result.value;
  }

  if (requestsState.loading) {
    return (
      <div className="fc-judgment__loading">
        <Skeleton height={200} />
        <Skeleton height={120} />
      </div>
    );
  }

  if (requestsState.error !== undefined) {
    return (
      <ErrorState
        error={requestsState.error}
        onRetry={requestsState.reload}
      />
    );
  }

  return (
    <div className="fc-judgment">
      {/* ── Tier counts summary ── */}
      <div className="fc-judgment__tier-counts">
        <div className="fc-judgment__tier-count">
          <Mono className="fc-judgment__tier-num">{formatCount(needsYou.length)}</Mono>
          <Kicker tone="needs-you">Needs you</Kicker>
          <Dim className="fc-judgment__tier-sub">Irreversible or novel</Dim>
        </div>
        <div className="fc-judgment__tier-count">
          <Mono className="fc-judgment__tier-num">{formatCount(sweep.length)}</Mono>
          <Kicker tone="muted">Sweep</Kicker>
          <Dim className="fc-judgment__tier-sub">Routine, reversible</Dim>
        </div>
        <div className="fc-judgment__tier-count">
          <Mono className="fc-judgment__tier-num">{formatCount(autoHandled.length)}</Mono>
          <Kicker tone="done">Auto-handled</Kicker>
          <Dim className="fc-judgment__tier-sub">Receipts, read-only</Dim>
        </div>
      </div>

      {/* ── Needs-you items — individual consequence cards ── */}
      {needsYou.length > 0 && (
        <section className="fc-judgment__needs-you">
          <Kicker tone="needs-you" className="fc-judgment__section-label">
            Needs you — {needsYou.length} {needsYou.length === 1 ? 'item' : 'items'}
          </Kicker>
          {/*
           * NEVER selectable or batchable — each card must be decided
           * individually. No checkboxes, no select-all, no commit bar here.
           * Enforced by the DecisionCard having no selection affordances.
           */}
          <div className="fc-judgment__cards">
            {needsYou.map((req) => (
              <DecisionCard
                key={req.id}
                request={req}
                principals={principalsState.data ?? []}
                onVerdict={handleNeedsYouVerdict}
                pending={submitVerdict.pending}
              />
            ))}
          </div>
        </section>
      )}

      {needsYou.length === 0 && (
        <EmptyState
          headline="No items need your judgment."
          body="Everything in the irreversible or novel category has been handled or is not yet escalated."
          tone="done"
        />
      )}

      {/* ── Sweep items — dense rows with checkboxes ── */}
      {sweep.length > 0 && (
        <section className="fc-judgment__sweep">
          <div className="fc-judgment__sweep-header">
            <Kicker tone="muted" className="fc-judgment__section-label">
              Sweep — {sweep.length} {sweep.length === 1 ? 'item' : 'items'}
            </Kicker>
            <div className="fc-judgment__sweep-controls">
              <Button variant="ghost" size="sm" onClick={selectAllSweep}>
                Select all
              </Button>
              {selected.size > 0 && (
                <Button variant="ghost" size="sm" onClick={clearSweep}>
                  Clear
                </Button>
              )}
            </div>
          </div>

          <div className="fc-judgment__sweep-rows">
            {sweep.map((req) => (
              <SweepRow
                key={req.id}
                request={req}
                checked={selected.has(req.id)}
                onToggle={() => toggleSweep(req.id)}
                principals={principalsState.data ?? []}
                onVerdict={handleNeedsYouVerdict}
              />
            ))}
          </div>

          {/* Sticky commit bar */}
          {selected.size > 0 && (
            <div className="fc-judgment__commit-bar">
              <div className="fc-judgment__commit-exposure">
                <Mono className="fc-judgment__commit-count">
                  {selected.size} selected
                </Mono>
                {totalExposure > 0 && (
                  <Mono className="fc-judgment__commit-amount">
                    {formatMoney(exposureMoney)} total exposure
                  </Mono>
                )}
              </div>
              {sweepError !== undefined && (
                <Body className="fc-judgment__commit-error" role="alert">
                  {sweepError}
                </Body>
              )}
              <Button
                variant="primary"
                size="md"
                disabled={submitBatch.pending}
                onClick={() => void commitSweep()}
              >
                {submitBatch.pending ? 'Approving…' : `Approve ${selected.size}`}
              </Button>
            </div>
          )}
        </section>
      )}

      {/* ── Auto-handled receipts — read-only ── */}
      {autoHandled.length > 0 && (
        <section className="fc-judgment__auto">
          <Kicker tone="done" className="fc-judgment__section-label">
            Auto-handled — {autoHandled.length} receipts
          </Kicker>
          <div className="fc-judgment__auto-list">
            {autoHandled.slice(0, 20).map((receipt) => (
              <div key={receipt.id} className="fc-judgment__auto-row">
                <Body className="fc-judgment__auto-action">{receipt.actionType}</Body>
                <Mono className="fc-judgment__auto-time">
                  {formatRelative(receipt.at)}
                </Mono>
                <Tag tone="done">done</Tag>
              </div>
            ))}
          </div>
        </section>
      )}

      {undoMutation.error !== undefined && (
        <Body className="fc-judgment__undo-error" role="alert">
          {undoMutation.error.message}
        </Body>
      )}
    </div>
  );
}

/* ── SweepRow ─────────────────────────────────────────────────────────── */

interface SweepRowProps {
  request: JudgmentRequest;
  checked: boolean;
  onToggle: () => void;
  principals: readonly Principal[];
  onVerdict: (
    id: string,
    verdict: Verdict,
  ) => Promise<{ receiptId: ReceiptId; undoWindowSeconds: number } | null>;
}

function SweepRow({
  request,
  checked,
  onToggle,
  principals,
  onVerdict,
}: SweepRowProps): React.JSX.Element {
  const [showRank, setShowRank] = useState(false);
  const [showDelegate, setShowDelegate] = useState(false);
  const [delegateTo, setDelegateTo] = useState('');
  const [localPending, setLocalPending] = useState(false);

  async function act(verdict: Verdict): Promise<void> {
    setLocalPending(true);
    await onVerdict(request.id, verdict);
    setLocalPending(false);
  }

  const cost = request.consequence.cost;
  const costText =
    'minor' in cost
      ? formatMoneyCompact(cost)
      : cost.description;

  return (
    <div className={`fc-sweep-row ${checked ? 'fc-sweep-row--checked' : ''}`}>
      <label className="fc-sweep-row__check-label">
        <input
          type="checkbox"
          className="fc-sweep-row__checkbox"
          checked={checked}
          onChange={onToggle}
          aria-label={`Select: ${request.title}`}
        />
      </label>

      <div className="fc-sweep-row__body">
        <div className="fc-sweep-row__top">
          <Kicker tone="muted" className="fc-sweep-row__category">
            {request.category}
          </Kicker>
          <Body className="fc-sweep-row__title">{request.title}</Body>
          <Mono className="fc-sweep-row__cost">{costText}</Mono>
          <Mono className="fc-sweep-row__time">
            {formatRelative(request.openedAt)}
          </Mono>
        </div>

        {/* Secondary actions */}
        <div className="fc-sweep-row__actions">
          <button
            type="button"
            className="fc-sweep-row__rank-toggle"
            onClick={() => setShowRank((v) => !v)}
            aria-expanded={showRank}
          >
            <Mono>Why ranked #{request.rank.position}</Mono>
          </button>

          <Button
            variant="ghost"
            size="sm"
            disabled={localPending}
            onClick={() => {
              const until = new Date(Date.now() + 86_400_000).toISOString();
              void act({ kind: 'snooze', until });
            }}
          >
            Snooze
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowDelegate((v) => !v)}
          >
            Delegate
          </Button>
        </div>

        {showRank && (
          <Dim className="fc-sweep-row__rank-text">{request.rank.justification}</Dim>
        )}

        {showDelegate && (
          <div className="fc-sweep-row__delegate">
            <select
              className="fc-sweep-row__delegate-select"
              value={delegateTo}
              onChange={(e) => setDelegateTo(e.target.value)}
              aria-label="Delegate to"
            >
              <option value="">Choose person…</option>
              {principals.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} — {p.role}
                </option>
              ))}
            </select>
            <Button
              variant="default"
              size="sm"
              disabled={delegateTo === '' || localPending}
              onClick={() =>
                void act({ kind: 'delegate', to: delegateTo as PrincipalId })
              }
            >
              Confirm
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   RULES TAB
   ═════════════════════════════════════════════════════════════════════════ */

function RulesTab(): React.JSX.Element {
  const kernel = useKernel();

  const rulesState = useAsync(
    useCallback(() => kernel.listRules(), [kernel]),
    [kernel],
  );

  const setStatusMutation = useMutation(
    useCallback(
      (
        client,
        args: { id: RuleId; status: 'active' | 'paused' | 'revoked' },
      ) => client.setRuleStatus(args.id, args.status),
      [],
    ),
  );

  const renewMutation = useMutation(
    useCallback(
      (client, args: { id: RuleId; days: number }) =>
        client.renewRule(args.id, args.days),
      [],
    ),
  );

  const [mutationErrors, setMutationErrors] = useState<
    Readonly<Record<string, string>>
  >({});

  async function handleSetStatus(
    id: RuleId,
    status: 'active' | 'paused',
  ): Promise<void> {
    const result = await setStatusMutation.run({ id, status });
    if (!result.ok) {
      setMutationErrors((prev) => ({ ...prev, [id]: result.error.message }));
    } else {
      setMutationErrors((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      void rulesState.reload();
    }
  }

  async function handleRenew(id: RuleId): Promise<void> {
    const result = await renewMutation.run({ id, days: 90 });
    if (!result.ok) {
      setMutationErrors((prev) => ({ ...prev, [id]: result.error.message }));
    } else {
      setMutationErrors((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      void rulesState.reload();
    }
  }

  if (rulesState.loading) {
    return (
      <div className="fc-rules__loading">
        <Skeleton height={120} />
        <Skeleton height={120} />
        <Skeleton height={120} />
      </div>
    );
  }

  if (rulesState.error !== undefined) {
    return (
      <ErrorState error={rulesState.error} onRetry={rulesState.reload} />
    );
  }

  const rules = rulesState.data ?? [];

  if (rules.length === 0) {
    return (
      <EmptyState
        headline="No standing rules."
        body="Rules appear here after the AI proposes them and you grant a trial. When there are no rules, every decision escalates to you."
        tone="live"
      />
    );
  }

  const nowMs = Date.now();
  const sevenDaysMs = 7 * 24 * 60 * 60 * 1000;

  return (
    <div className="fc-rules">
      {rules.map((rule) => {
        const expiresAt = new Date(rule.expiresAt).getTime();
        const expiringSoon =
          rule.status === 'active' && expiresAt - nowMs < sevenDaysMs;
        const capRatio =
          rule.cumulativeCap.limit.minor > 0
            ? rule.cumulativeCap.consumed.minor /
              rule.cumulativeCap.limit.minor
            : 0;

        const errorMsg = mutationErrors[rule.id];

        return (
          <Panel
            key={rule.id}
            className={`fc-rule-card ${expiringSoon ? 'fc-rule-card--expiring' : ''}`}
          >
            <div className="fc-rule-card__header">
              <div className="fc-rule-card__meta">
                <Tag
                  tone={
                    rule.status === 'active'
                      ? 'live'
                      : rule.status === 'trial'
                      ? 'needs-you'
                      : rule.status === 'paused'
                      ? 'muted'
                      : 'risk'
                  }
                >
                  {rule.status}
                </Tag>
                <Tag tone="muted">{rule.domain}</Tag>
              </div>
              <Mono className="fc-rule-card__id">{rule.id}</Mono>
            </div>

            <Body className="fc-rule-card__statement">{rule.statement}</Body>

            {/* Trigger */}
            <div className="fc-rule-card__row">
              <Mono className="fc-rule-card__row-label">Trigger</Mono>
              <Body className="fc-rule-card__row-value">{rule.trigger}</Body>
            </div>

            {/* Cap with bar */}
            <div className="fc-rule-card__cap">
              <div className="fc-rule-card__cap-header">
                <Mono className="fc-rule-card__row-label">Cumulative cap</Mono>
                <Mono className="fc-rule-card__cap-nums">
                  {formatMoney(rule.cumulativeCap.consumed)} /{' '}
                  {formatMoney(rule.cumulativeCap.limit)}
                  {' '}({rule.cumulativeCap.windowDays}d window)
                </Mono>
              </div>
              <Bar
                value={capRatio}
                tone={capRatio > 0.85 ? 'risk' : capRatio > 0.6 ? 'needs-you' : 'live'}
                className="fc-rule-card__cap-bar"
              />
            </div>

            {/* Exclusions */}
            {rule.exclusions.length > 0 && (
              <div className="fc-rule-card__exclusions">
                <Mono className="fc-rule-card__row-label">Exclusions</Mono>
                <ul className="fc-rule-card__exclusion-list">
                  {rule.exclusions.map((ex, i) => (
                    <li key={i}>
                      <Body>{ex}</Body>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Expiry */}
            <div className="fc-rule-card__expiry">
              <Mono className="fc-rule-card__row-label">Expires</Mono>
              <Mono
                className={
                  expiringSoon
                    ? 'fc-rule-card__expiry-soon'
                    : 'fc-rule-card__expiry-normal'
                }
              >
                {formatRelative(rule.expiresAt)}
                {expiringSoon && ' — expiring soon'}
              </Mono>
            </div>

            {/* Stats */}
            <div className="fc-rule-card__stats">
              <Mono className="fc-rule-card__row-label">Fired</Mono>
              <Mono>{formatCount(rule.firingCount)} times</Mono>
              {rule.lastFiredAt !== undefined && (
                <Mono className="fc-rule-card__last-fired">
                  Last {formatRelative(rule.lastFiredAt)}
                </Mono>
              )}
            </div>

            {/* Mutation error */}
            {errorMsg !== undefined && (
              <Body className="fc-rule-card__error" role="alert">
                {errorMsg}
              </Body>
            )}

            {/* Actions */}
            <div className="fc-rule-card__actions">
              {rule.status === 'active' || rule.status === 'trial' ? (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={setStatusMutation.pending}
                  onClick={() => void handleSetStatus(rule.id, 'paused')}
                >
                  Pause
                </Button>
              ) : rule.status === 'paused' ? (
                <Button
                  variant="default"
                  size="sm"
                  disabled={setStatusMutation.pending}
                  onClick={() => void handleSetStatus(rule.id, 'active')}
                >
                  Resume
                </Button>
              ) : null}

              {expiringSoon && (
                <Button
                  variant="default"
                  size="sm"
                  disabled={renewMutation.pending}
                  onClick={() => void handleRenew(rule.id)}
                >
                  Renew 90 days
                </Button>
              )}
            </div>
          </Panel>
        );
      })}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   PROPOSALS TAB
   ═════════════════════════════════════════════════════════════════════════ */

function ProposalsTab(): React.JSX.Element {
  const kernel = useKernel();

  const proposalsState = useAsync(
    useCallback(() => kernel.listRuleProposals(), [kernel]),
    [kernel],
  );

  const grantMutation = useMutation(
    useCallback(
      (
        client,
        args: { proposalId: string; adjustedCap?: string },
      ) => {
        const adj =
          args.adjustedCap !== undefined && args.adjustedCap.trim() !== ''
            ? {
                cumulativeCap: {
                  limit: {
                    currency: 'INR' as const,
                    minor: Math.round(parseFloat(args.adjustedCap) * 100),
                  },
                  windowDays: 30,
                  consumed: { currency: 'INR' as const, minor: 0 },
                },
              }
            : undefined;
        return adj !== undefined
          ? client.grantRule(args.proposalId, adj)
          : client.grantRule(args.proposalId);
      },
      [],
    ),
  );

  const declineMutation = useMutation(
    useCallback(
      (client, id: string) => client.declineProposal(id),
      [],
    ),
  );

  const [adjustedCaps, setAdjustedCaps] = useState<
    Readonly<Record<string, string>>
  >({});
  const [mutationErrors, setMutationErrors] = useState<
    Readonly<Record<string, string>>
  >({});

  async function handleGrant(proposalId: string): Promise<void> {
    const adjustedCap = adjustedCaps[proposalId];
    const result = await grantMutation.run({ proposalId, adjustedCap });
    if (!result.ok) {
      setMutationErrors((prev) => ({
        ...prev,
        [proposalId]: result.error.message,
      }));
    } else {
      setMutationErrors((prev) => {
        const next = { ...prev };
        delete next[proposalId];
        return next;
      });
      void proposalsState.reload();
    }
  }

  async function handleDecline(proposalId: string): Promise<void> {
    const result = await declineMutation.run(proposalId);
    if (!result.ok) {
      setMutationErrors((prev) => ({
        ...prev,
        [proposalId]: result.error.message,
      }));
    } else {
      void proposalsState.reload();
    }
  }

  if (proposalsState.loading) {
    return (
      <div className="fc-proposals__loading">
        <Skeleton height={280} />
        <Skeleton height={280} />
      </div>
    );
  }

  if (proposalsState.error !== undefined) {
    return (
      <ErrorState
        error={proposalsState.error}
        onRetry={proposalsState.reload}
      />
    );
  }

  const proposals = proposalsState.data ?? [];

  if (proposals.length === 0) {
    return (
      <EmptyState
        headline="No rule proposals."
        body="Proposals appear when the AI has handled similar requests enough times to suggest a standing rule. There are none right now."
        tone="done"
      />
    );
  }

  return (
    <div className="fc-proposals">
      {proposals.map((proposal) => {
        const approved = proposal.evidence.observations.filter(
          (o) => o.outcome === 'approved',
        );
        const declined = proposal.evidence.observations.filter(
          (o) => o.outcome === 'declined',
        );
        const total = proposal.evidence.observations.length;
        const approvedRatio = total > 0 ? approved.length / total : 0;
        const declinedRatio = total > 0 ? declined.length / total : 0;

        const errorMsg = mutationErrors[proposal.id];
        const adjCap = adjustedCaps[proposal.id] ?? '';

        const draft = proposal.draft;
        const expiresLabel = formatRelative(draft.expiresAt);

        return (
          <Panel key={proposal.id} className="fc-proposal-card">
            {/* The question — H2, the hero moment */}
            <H2 className="fc-proposal-card__question">{proposal.question}</H2>

            {/* Evidence strip */}
            <div className="fc-proposal-card__evidence">
              <div className="fc-proposal-card__ev-row">
                <Mono className="fc-proposal-card__ev-label">Approved</Mono>
                <Bar
                  value={approvedRatio}
                  tone="done"
                  className="fc-proposal-card__ev-bar"
                />
                <Mono className="fc-proposal-card__ev-count">
                  {approved.length}
                </Mono>
              </div>
              <div className="fc-proposal-card__ev-row">
                <Mono className="fc-proposal-card__ev-label">Declined</Mono>
                <Bar
                  value={declinedRatio}
                  tone="risk"
                  className="fc-proposal-card__ev-bar"
                />
                <Mono className="fc-proposal-card__ev-count">
                  {declined.length}
                </Mono>
              </div>
              <div className="fc-proposal-card__ev-meta">
                <Mono className="fc-proposal-card__ev-meta-item">
                  Median decision:{' '}
                  {formatDuration(proposal.evidence.medianDecisionSeconds)}
                </Mono>
                <Mono className="fc-proposal-card__ev-meta-item">
                  Over {proposal.evidence.windowDays} days
                </Mono>
              </div>
            </div>

            {/* Boundary-setting rejection */}
            {proposal.evidence.boundarySettingRejection !== undefined && (
              <div className="fc-proposal-card__boundary">
                <Kicker tone="risk">Boundary-setting decline</Kicker>
                <Body className="fc-proposal-card__boundary-text">
                  {proposal.evidence.boundarySettingRejection}
                </Body>
              </div>
            )}

            {/* Five-part rule anatomy */}
            <div className="fc-proposal-card__anatomy">
              <H3 className="fc-proposal-card__anatomy-heading">
                Proposed rule
              </H3>

              <div className="fc-proposal-card__anatomy-row">
                <Mono className="fc-proposal-card__anatomy-label">Trigger</Mono>
                <Body className="fc-proposal-card__anatomy-value">
                  {draft.trigger}
                </Body>
              </div>

              <div className="fc-proposal-card__anatomy-row">
                <Mono className="fc-proposal-card__anatomy-label">Cap</Mono>
                <div className="fc-proposal-card__cap-edit">
                  <Body className="fc-proposal-card__anatomy-value">
                    {formatMoney(draft.cumulativeCap.limit)} over{' '}
                    {draft.cumulativeCap.windowDays} days
                  </Body>
                  {/* Inline cap adjustment — no modal */}
                  <div className="fc-proposal-card__cap-adjust">
                    <label
                      htmlFor={`cap-${proposal.id}`}
                      className="fc-proposal-card__cap-label"
                    >
                      <Mono>Adjust ceiling (major units)</Mono>
                    </label>
                    <input
                      id={`cap-${proposal.id}`}
                      type="number"
                      className="fc-proposal-card__cap-input"
                      value={adjCap}
                      placeholder={String(
                        draft.cumulativeCap.limit.minor / 100,
                      )}
                      onChange={(e) =>
                        setAdjustedCaps((prev) => ({
                          ...prev,
                          [proposal.id]: e.target.value,
                        }))
                      }
                      aria-label="Adjusted ceiling"
                      min="0"
                    />
                  </div>
                </div>
              </div>

              {draft.exclusions.length > 0 && (
                <div className="fc-proposal-card__anatomy-row">
                  <Mono className="fc-proposal-card__anatomy-label">
                    Exclusions
                  </Mono>
                  <ul className="fc-proposal-card__exclusion-list">
                    {draft.exclusions.map((ex, i) => (
                      <li key={i}>
                        <Body>{ex}</Body>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="fc-proposal-card__anatomy-row">
                <Mono className="fc-proposal-card__anatomy-label">
                  Trial expiry
                </Mono>
                <Body className="fc-proposal-card__anatomy-value">
                  {expiresLabel}
                </Body>
              </div>

              <div className="fc-proposal-card__anatomy-row">
                <Mono className="fc-proposal-card__anatomy-label">Receipt</Mono>
                <Body className="fc-proposal-card__anatomy-value">
                  Every action under this rule produces a receipt.
                </Body>
              </div>
            </div>

            <Dim className="fc-proposal-card__interruptions">
              Would save approximately {proposal.interruptionsSaved}{' '}
              {proposal.interruptionsSaved === 1
                ? 'interruption'
                : 'interruptions'}{' '}
              per trial period.
            </Dim>

            {/* Mutation error */}
            {errorMsg !== undefined && (
              <Body className="fc-proposal-card__error" role="alert">
                {errorMsg}
              </Body>
            )}

            {/* Actions */}
            <div className="fc-proposal-card__actions">
              <Button
                variant="primary"
                size="md"
                disabled={grantMutation.pending}
                onClick={() => void handleGrant(proposal.id)}
              >
                Accept trial
              </Button>
              <Button
                variant="ghost"
                size="md"
                disabled={declineMutation.pending}
                onClick={() => void handleDecline(proposal.id)}
              >
                Keep asking me
              </Button>
            </div>
          </Panel>
        );
      })}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   SCOPE & AUDIT TAB
   ═════════════════════════════════════════════════════════════════════════ */

function ScopeTab(): React.JSX.Element {
  const kernel = useKernel();

  const scopeState = useAsync(
    useCallback(() => kernel.getScope(), [kernel]),
    [kernel],
  );

  const boundaryState = useAsync(
    useCallback(() => kernel.getBoundary(), [kernel]),
    [kernel],
  );

  const auditState = useAsync(
    useCallback(() => kernel.getDependencyAudit(), [kernel]),
    [kernel],
  );

  const suspendMutation = useMutation(
    useCallback((client, _: undefined) => client.suspendAutonomy(), []),
  );

  const resumeMutation = useMutation(
    useCallback((client, _: undefined) => client.resumeAutonomy(), []),
  );

  const [suspendError, setSuspendError] = useState<KernelError | undefined>(
    undefined,
  );

  async function handleSuspend(): Promise<void> {
    setSuspendError(undefined);
    const result = await suspendMutation.run(undefined);
    if (!result.ok) {
      setSuspendError(result.error);
    } else {
      void boundaryState.reload();
    }
  }

  async function handleResume(): Promise<void> {
    setSuspendError(undefined);
    const result = await resumeMutation.run(undefined);
    if (!result.ok) {
      setSuspendError(result.error);
    } else {
      void boundaryState.reload();
    }
  }

  const suspended = boundaryState.data?.suspended ?? false;

  return (
    <div className="fc-scope">
      {/* ── Suspend control — one button, no confirmation ── */}
      <section className="fc-scope__suspend">
        {boundaryState.loading ? (
          <Skeleton lines={2} />
        ) : (
          <>
            {suspended && (
              <div className="fc-scope__suspended-notice" role="status">
                <Tag tone="risk">Autonomy suspended</Tag>
                <Body className="fc-scope__suspended-text">
                  All rules are dormant. The kernel continues working but stops
                  deciding. Every action is escalated to you.
                </Body>
              </div>
            )}
            <Button
              variant={suspended ? 'primary' : 'default'}
              size="md"
              disabled={suspendMutation.pending || resumeMutation.pending}
              onClick={() =>
                suspended ? void handleResume() : void handleSuspend()
              }
            >
              {suspended ? 'Resume autonomy' : 'Suspend autonomy'}
            </Button>
            {suspendError !== undefined && (
              <ErrorState error={suspendError} />
            )}
          </>
        )}
      </section>

      {/* ── Permitted / Forbidden ── */}
      <section className="fc-scope__scope-text">
        <H3 className="fc-scope__section-heading">Scope</H3>
        {scopeState.loading && <Skeleton lines={2} />}
        {scopeState.error !== undefined && (
          <ErrorState error={scopeState.error} onRetry={scopeState.reload} />
        )}
        {scopeState.data !== undefined && (
          <div className="fc-scope__two-answers">
            <div className="fc-scope__answer">
              <Kicker tone="done">Permitted</Kicker>
              <Body className="fc-scope__answer-text">
                {scopeState.data.permitted}
              </Body>
            </div>
            <div className="fc-scope__answer">
              <Kicker tone="risk">Forbidden</Kicker>
              <Body className="fc-scope__answer-text">
                {scopeState.data.forbidden}
              </Body>
            </div>
          </div>
        )}
      </section>

      {/* ── Autonomy ratio ── */}
      <section className="fc-scope__boundary">
        <H3 className="fc-scope__section-heading">Autonomy</H3>
        {boundaryState.loading && <Skeleton height={80} />}
        {boundaryState.error !== undefined && (
          <ErrorState
            error={boundaryState.error}
            onRetry={boundaryState.reload}
          />
        )}
        {boundaryState.data !== undefined && (
          <div className="fc-scope__boundary-body">
            <div className="fc-scope__ratio-row">
              <span className="fc-scope__ratio-numeral">
                {formatPercent(boundaryState.data.autonomyRatio)}
              </span>
              <div className="fc-scope__ratio-meta">
                <Body>handled without you</Body>
                <Mono className="fc-scope__ratio-rules">
                  {boundaryState.data.activeRuleCount} active{' '}
                  {boundaryState.data.activeRuleCount === 1 ? 'rule' : 'rules'}
                </Mono>
              </div>
            </div>
            {boundaryState.data.history.length > 1 && (
              <Sparkline
                points={boundaryState.data.history.map((h) => h.ratio)}
                tone="live"
                width={200}
                height={32}
                className="fc-scope__sparkline"
              />
            )}
          </div>
        )}
      </section>

      {/* ── Dependency audit ── */}
      <section className="fc-scope__audit">
        <H3 className="fc-scope__section-heading">Dependency audit</H3>
        {auditState.loading && <Skeleton lines={4} />}
        {auditState.error !== undefined && (
          <ErrorState error={auditState.error} onRetry={auditState.reload} />
        )}
        {auditState.data !== undefined && (
          <div className="fc-scope__audit-sections">
            <AuditSection
              label="Unasked authority"
              items={auditState.data.unaskedAuthority}
              emptyText="None identified."
            />
            <AuditSection
              label="Unexamined rules"
              items={auditState.data.unexaminedRules}
              emptyText="All rules have been reviewed."
            />
            <AuditSection
              label="What would be lost"
              items={auditState.data.whatWouldBeLost}
              emptyText="Nothing critical identified."
            />
            <AuditSection
              label="Self-assessed overreach"
              items={auditState.data.selfAssessedOverreach}
              emptyText="No overreach identified."
              tone="risk"
            />
          </div>
        )}
      </section>
    </div>
  );
}

interface AuditSectionProps {
  label: string;
  items: readonly string[];
  emptyText: string;
  tone?: 'risk' | 'muted';
}

function AuditSection({
  label,
  items,
  emptyText,
  tone = 'muted',
}: AuditSectionProps): React.JSX.Element {
  return (
    <div className="fc-audit-section">
      <Kicker tone={tone === 'risk' ? 'risk' : 'muted'} className="fc-audit-section__label">
        {label}
      </Kicker>
      {items.length === 0 ? (
        <Dim className="fc-audit-section__empty">{emptyText}</Dim>
      ) : (
        <ul className="fc-audit-section__list">
          {items.map((item, i) => (
            <li key={i}>
              <Body>{item}</Body>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   FOUNDER CONSOLE (root)
   ═════════════════════════════════════════════════════════════════════════ */

export function FounderConsole(): React.JSX.Element {
  const [activeTab, setActiveTab] = useState<TabKey>('judgment');
  const [toast, setToast] = useState<ToastInfo | null>(null);
  const kernel = useKernel();

  const undoMutation = useMutation(
    useCallback(
      (client, ids: readonly ReceiptId[]) => client.undo(ids),
      [],
    ),
  );

  function handleUndo(): void {
    if (toast === null) return;
    void undoMutation.run(toast.receiptIds);
    setToast(null);
  }

  return (
    <main className="fc-root">
      <Tabs
        tabs={TABS}
        active={activeTab}
        onChange={(k) => setActiveTab(k as TabKey)}
        className="fc-tabs"
      />

      <div className="fc-content">
        {activeTab === 'judgment' && (
          <JudgmentTab onToast={setToast} />
        )}
        {activeTab === 'rules' && <RulesTab />}
        {activeTab === 'proposals' && <ProposalsTab />}
        {activeTab === 'scope' && <ScopeTab />}
      </div>

      {toast !== null && (
        <div className="fc-toast-anchor" aria-live="polite">
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
