/**
 * LedgerExplorer — the append-only receipt ledger.
 *
 * Filter bar → DataTable → SplitView detail pane.
 * Cursor pagination via Page<T>.cursor.
 * "Read as prose" via renderLedgerAsProse.
 * Append-only notice is permanent and visible.
 */
import React, { useCallback, useMemo, useState } from 'react';
import {
  Body,
  Button,
  ConsequenceGrid,
  DataTable,
  Dim,
  EmptyState,
  ErrorState,
  H2,
  H3,
  KeyValue,
  Kicker,
  Mono,
  Panel,
  Rule,
  SearchField,
  SelectField,
  Skeleton,
  SplitView,
  Tag,
} from '@/components';
import type { Column, KeyValueRow, SelectOption } from '@/components';
import { useAsync } from '@/kernel/hooks';
import { useKernel } from '@/kernel/KernelProvider';
import { useLocation, useRouter } from '@/app/router';
import type { Actor, DomainKey, LedgerQuery, Receipt } from '@/kernel/types';
import {
  formatMoney,
  formatRelative,
  formatReversibility,
} from '@/lib/format';
import { actorDisplay } from '@/features/shared/actorLabel';
import './LedgerExplorer.css';

/* ── constants ──────────────────────────────────────────────────────────── */

const PAGE_SIZE = 50;

const DOMAIN_OPTIONS: SelectOption[] = [
  { value: '', label: 'All domains' },
  { value: 'vendors', label: 'Vendors' },
  { value: 'spend', label: 'Spend' },
  { value: 'hiring', label: 'Hiring' },
  { value: 'operations', label: 'Operations' },
  { value: 'legal', label: 'Legal' },
  { value: 'product', label: 'Product' },
  { value: 'system', label: 'System' },
];

const ACTOR_OPTIONS: SelectOption[] = [
  { value: '', label: 'All actors' },
  { value: 'kernel', label: 'Kernel' },
  { value: 'rule', label: 'Rule' },
  { value: 'founder', label: 'Founder' },
  { value: 'delegate', label: 'Delegate' },
];

/* ── filter state ───────────────────────────────────────────────────────── */

interface Filters {
  domain: string;
  actor: string;
  flaggedOnly: boolean;
  search: string;
  from: string;
  to: string;
}

const EMPTY_FILTERS: Filters = {
  domain: '',
  actor: '',
  flaggedOnly: false,
  search: '',
  from: '',
  to: '',
};

function filtersToQuery(f: Filters, cursor?: string): LedgerQuery {
  return {
    ...(f.domain !== '' ? { domain: f.domain as DomainKey } : {}),
    ...(f.actor !== '' ? { actor: f.actor as Actor['kind'] } : {}),
    ...(f.flaggedOnly ? { flaggedOnly: true } : {}),
    ...(f.search !== '' ? { search: f.search } : {}),
    ...(f.from !== '' ? { from: f.from } : {}),
    ...(f.to !== '' ? { to: f.to } : {}),
    ...(cursor !== undefined ? { cursor } : {}),
    limit: PAGE_SIZE,
  };
}

function queryToFilters(q: Readonly<Record<string, string>>): Filters {
  return {
    domain: q['domain'] ?? '',
    actor: q['actor'] ?? '',
    flaggedOnly: q['flagged'] === '1',
    search: q['search'] ?? '',
    from: q['from'] ?? '',
    to: q['to'] ?? '',
  };
}

function filtersToQS(f: Filters): string {
  const parts: string[] = [];
  if (f.domain !== '') parts.push(`domain=${encodeURIComponent(f.domain)}`);
  if (f.actor !== '') parts.push(`actor=${encodeURIComponent(f.actor)}`);
  if (f.flaggedOnly) parts.push('flagged=1');
  if (f.search !== '') parts.push(`search=${encodeURIComponent(f.search)}`);
  if (f.from !== '') parts.push(`from=${encodeURIComponent(f.from)}`);
  if (f.to !== '') parts.push(`to=${encodeURIComponent(f.to)}`);
  return parts.length > 0 ? `?${parts.join('&')}` : '';
}

/* ── actor cell ─────────────────────────────────────────────────────────── */

function ActorCell({ actor }: { actor: Actor }): React.JSX.Element {
  const { label, tone } = actorDisplay(actor);
  return <Tag tone={tone}>{label}</Tag>;
}

/* ── reversibility cell ─────────────────────────────────────────────────── */

function RevCell({ r }: { r: Receipt['reversibility'] }): React.JSX.Element {
  const tone =
    r.kind === 'irreversible' ? 'risk' : r.kind === 'reversible-until' ? 'needs-you' : 'done';
  return (
    <span title={formatReversibility(r)}>
      <Tag tone={tone}>{r.kind}</Tag>
    </span>
  );
}

/* ── detail pane ────────────────────────────────────────────────────────── */

function ReceiptDetail({ receipt }: { receipt: Receipt }): React.JSX.Element {
  const actorKv: KeyValueRow[] = [
    { k: 'ID', v: receipt.id, mono: true },
    { k: 'Domain', v: receipt.domain, mono: true },
    { k: 'Phase', v: <Tag tone="muted">{receipt.phase}</Tag> },
    { k: 'Intent ID', v: receipt.intentId, mono: true },
    { k: 'At', v: formatRelative(receipt.at) },
    { k: 'Actor', v: <ActorCell actor={receipt.actor} /> },
    { k: 'Action type', v: receipt.actionType, mono: true },
    { k: 'Reversibility', v: <RevCell r={receipt.reversibility} /> },
    ...(receipt.amount !== undefined
      ? [{ k: 'Amount', v: <Mono>{formatMoney(receipt.amount)}</Mono> }]
      : []),
    ...(receipt.result !== undefined
      ? [
          {
            k: 'Result',
            v: (
              <Tag
                tone={
                  receipt.result === 'ok'
                    ? 'done'
                    : receipt.result === 'failed'
                    ? 'risk'
                    : 'needs-you'
                }
              >
                {receipt.result}
              </Tag>
            ),
          },
        ]
      : []),
  ];

  return (
    <div className="le-detail">
      <Kicker>{receipt.domain}</Kicker>
      <H3>{receipt.actionType}</H3>

      <KeyValue rows={actorKv} />

      <Rule />

      <div className="le-detail__intent-outcome">
        <div className="le-detail__intent">
          <Kicker>Intent</Kicker>
          <Body>{receipt.expectedEffect}</Body>
        </div>
        {receipt.actualEffect !== undefined && (
          <div className="le-detail__outcome">
            <Kicker>Outcome</Kicker>
            <Body>{receipt.actualEffect}</Body>
          </div>
        )}
      </div>

      {receipt.consequence !== undefined && (
        <>
          <Rule />
          <Kicker>Consequence quartet</Kicker>
          <ConsequenceGrid consequence={receipt.consequence} />
        </>
      )}

      {receipt.flagged !== undefined && (
        <>
          <Rule />
          <Panel tone="needs-you" className="le-detail__flagged">
            <Kicker>Flagged by self-audit</Kicker>
            <Body>{receipt.flagged.why}</Body>
            {receipt.flagged.proposedNarrowing !== undefined && (
              <>
                <Kicker>Proposed narrowing</Kicker>
                <Body>{receipt.flagged.proposedNarrowing}</Body>
              </>
            )}
          </Panel>
        </>
      )}
    </div>
  );
}

/* ── prose panel ────────────────────────────────────────────────────────── */

function ProsePanel({ query }: { query: LedgerQuery }): React.JSX.Element {
  const kernel = useKernel();
  const { data, loading, error, reload } = useAsync(
    () => kernel.renderLedgerAsProse(query),
    // Stringify query to detect changes
    [kernel, JSON.stringify(query)],
  );

  if (loading) return <Skeleton lines={6} />;
  if (error !== undefined) return <ErrorState error={error} onRetry={reload} />;
  if (data === undefined || data === '') {
    return <Dim>No narrative available for the current filter.</Dim>;
  }

  return (
    <div className="le-prose">
      <Body>{data}</Body>
    </div>
  );
}

/* ── columns ────────────────────────────────────────────────────────────── */

function buildColumns(): Column<Receipt>[] {
  return [
    {
      key: 'at',
      header: 'Time',
      width: '10rem',
      mono: true,
      render: (r) => (
        <span title={r.at} className="le-time-cell">
          {formatRelative(r.at)}
        </span>
      ),
    },
    {
      key: 'actor',
      header: 'Actor',
      width: '8rem',
      render: (r) => <ActorCell actor={r.actor} />,
    },
    {
      key: 'actionType',
      header: 'Action',
      render: (r) => (
        <span className="le-action-cell">
          {r.flagged !== undefined && (
            <span className="le-flagged-rule" aria-label="flagged">
              flagged
            </span>
          )}
          {r.actionType}
        </span>
      ),
    },
    {
      key: 'amount',
      header: 'Amount',
      width: '8rem',
      align: 'right',
      mono: true,
      render: (r) =>
        r.amount !== undefined ? (
          <span className="le-amount">{formatMoney(r.amount)}</span>
        ) : (
          <span className="le-amount-empty">—</span>
        ),
    },
    {
      key: 'reversibility',
      header: 'Reversible',
      width: '9rem',
      render: (r) => <RevCell r={r.reversibility} />,
    },
    {
      key: 'phase',
      header: 'Phase',
      width: '6rem',
      render: (r) => <Tag tone="muted">{r.phase}</Tag>,
    },
    {
      key: 'result',
      header: 'Result',
      width: '6rem',
      render: (r) =>
        r.result !== undefined ? (
          <Tag
            tone={
              r.result === 'ok' ? 'done' : r.result === 'failed' ? 'risk' : 'needs-you'
            }
          >
            {r.result}
          </Tag>
        ) : (
          <span className="le-amount-empty">—</span>
        ),
    },
  ];
}

/* ── main component ─────────────────────────────────────────────────────── */

export function LedgerExplorer(): React.JSX.Element {
  const kernel = useKernel();
  const location = useLocation();
  const { navigate } = useRouter();

  const [filters, setFilters] = useState<Filters>(() => queryToFilters(location.query));
  const [cursor, setCursor] = useState<string | undefined>(undefined);
  const [allReceipts, setAllReceipts] = useState<Receipt[]>([]);
  const [showProse, setShowProse] = useState(false);

  const query = useMemo(() => filtersToQuery(filters, cursor), [filters, cursor]);

  const { data, loading, error, reload } = useAsync(
    () => kernel.queryLedger(query),
    [kernel, JSON.stringify(query)],
  );

  // Sync accumulated when fresh page loaded
  React.useEffect(() => {
    if (data !== undefined) {
      const incoming = data.items as Receipt[];
      setAllReceipts((prev) => {
        // cursor === undefined means filter changed — replace
        if (cursor === undefined) return incoming;
        // cursor present — paginating, dedupe by id
        const existing = new Set(prev.map((r) => r.id));
        const fresh = incoming.filter((r) => !existing.has(r.id));
        return [...prev, ...fresh];
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  const receipts = allReceipts;

  const selectedId = location.detail;
  const selectedReceipt = useMemo(
    () => receipts.find((r) => r.id === selectedId),
    [receipts, selectedId],
  );

  const updateFilters = useCallback(
    (patch: Partial<Filters>) => {
      const next = { ...filters, ...patch };
      setFilters(next);
      setCursor(undefined);
      setAllReceipts([]);
      navigate(`/ledger${filtersToQS(next)}`, { replace: true });
    },
    [filters, navigate],
  );

  const proseQuery = useMemo(() => filtersToQuery(filters), [filters]);
  const columns = useMemo(() => buildColumns(), []);

  const listPane = (
    <div className="le-list-pane">
      <div className="le-header">
        <H2>Receipt ledger</H2>
        <Panel tone="done" className="le-append-only-notice">
          <Mono className="le-append-only-notice__text">
            Append-only — there is no edit or delete affordance anywhere on this screen, by design.
          </Mono>
        </Panel>
      </div>

      <div className="le-filters">
        <SearchField
          label="Search"
          value={filters.search}
          onChange={(e) => updateFilters({ search: e.target.value })}
          placeholder="Filter by action, actor, effect…"
        />
        <SelectField
          label="Domain"
          value={filters.domain}
          onChange={(e) => updateFilters({ domain: e.target.value })}
          options={DOMAIN_OPTIONS}
        />
        <SelectField
          label="Actor"
          value={filters.actor}
          onChange={(e) => updateFilters({ actor: e.target.value })}
          options={ACTOR_OPTIONS}
        />
        <label className="le-filters__flagged">
          <input
            type="checkbox"
            checked={filters.flaggedOnly}
            onChange={(e) => updateFilters({ flaggedOnly: e.target.checked })}
          />
          <span>Flagged only</span>
        </label>
        <div className="le-filters__dates">
          <label className="le-filters__date-label">
            <span>From</span>
            <input
              type="date"
              className="le-filters__date-input"
              value={filters.from}
              onChange={(e) => updateFilters({ from: e.target.value })}
            />
          </label>
          <label className="le-filters__date-label">
            <span>To</span>
            <input
              type="date"
              className="le-filters__date-input"
              value={filters.to}
              onChange={(e) => updateFilters({ to: e.target.value })}
            />
          </label>
        </div>
      </div>

      {loading && receipts.length === 0 && (
        <div className="le-skeletons">
          <Skeleton height={32} />
          <Skeleton height={32} />
          <Skeleton height={32} />
          <Skeleton height={32} />
          <Skeleton height={32} />
        </div>
      )}

      {error !== undefined && receipts.length === 0 && (
        <ErrorState error={error} onRetry={reload} />
      )}

      {!loading && error === undefined && receipts.length === 0 && (
        <EmptyState
          headline="No receipts match the current filter."
          body="The ledger is complete — every action taken by the kernel is recorded here. Adjust the filters to find what you are looking for."
        />
      )}

      {receipts.length > 0 && (
        <DataTable<Receipt>
          columns={columns}
          rows={receipts}
          onRowClick={(r) => navigate(`/ledger/${r.id}`)}
          empty={
            <EmptyState
              headline="No receipts."
              body="No actions recorded yet."
            />
          }
        />
      )}

      {data?.cursor !== undefined && (
        <div className="le-load-more">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              const next = data?.cursor;
              if (next !== undefined) setCursor(next);
            }}
            disabled={loading}
          >
            {loading ? 'Loading…' : 'Load more'}
          </Button>
        </div>
      )}

      <Rule />

      <div className="le-prose-section">
        <div className="le-prose-section__header">
          <div>
            <H3>Read as prose</H3>
            <Dim>
              Engineering Law III — the system renders its state as legible narrative. This is
              that narrative, generated for the current filter.
            </Dim>
          </div>
          <Button
            variant="accent"
            size="sm"
            onClick={() => setShowProse((v) => !v)}
          >
            {showProse ? 'Hide narrative' : 'Read as prose'}
          </Button>
        </div>
        {showProse && <ProsePanel query={proseQuery} />}
      </div>
    </div>
  );

  const detailPane = (
    <div className="le-detail-pane">
      {selectedReceipt !== undefined ? (
        <ReceiptDetail receipt={selectedReceipt} />
      ) : (
        <EmptyState
          headline="Select a receipt."
          body="Click any row to inspect it in full — including its consequence quartet and audit flags."
        />
      )}
    </div>
  );

  return (
    <div className="le-root">
      <SplitView left={listPane} right={detailPane} />
    </div>
  );
}
