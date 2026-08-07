/**
 * MemoryExplorer — five memory stores, freshness-first.
 *
 * Tabs by MemoryKind, SearchField + domain filter.
 * Every record shows lastVerifiedAt and calls out staleness > 30 days.
 * Detail pane: content, provenance, supersedes / contradicts links.
 */
import React, { useMemo, useState } from 'react';
import {
  Body,
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
  Tabs,
} from '@/components';
import type { Column, KeyValueRow, SelectOption, TabDef } from '@/components';
import { useAsync } from '@/kernel/hooks';
import { useKernel } from '@/kernel/KernelProvider';
import { useLocation, useRouter } from '@/app/router';
import type { DomainKey, MemoryKind, MemoryRecord } from '@/kernel/types';
import { formatRelative } from '@/lib/format';
import './MemoryExplorer.css';

/* ── constants ──────────────────────────────────────────────────────────── */

const THIRTY_DAYS_MS = 30 * 24 * 60 * 60 * 1000;

interface KindMeta {
  description: string;
  retention: string;
}

const KIND_META: Record<MemoryKind, KindMeta> = {
  episodic: {
    description: 'Specific events and their outcomes — what happened, when, and what it meant.',
    retention: 'Rolling window; older episodes expire unless promoted.',
  },
  decisional: {
    description: 'Recorded judgments and the reasoning behind them.',
    retention: 'Permanent — decisions form the audit chain.',
  },
  semantic: {
    description: 'General facts, domain knowledge, and stable world-model beliefs.',
    retention: 'Permanent until explicitly superseded or contradicted.',
  },
  procedural: {
    description: 'How-to knowledge: steps, processes, protocols, and workflows.',
    retention: 'Rolling; reviewed when the underlying process changes.',
  },
  relational: {
    description: 'Entities and the relationships between them — people, vendors, systems.',
    retention: 'Permanent; updated in place with full provenance trail.',
  },
};

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

const KIND_TABS: TabDef[] = [
  { key: 'episodic', label: 'Episodic' },
  { key: 'decisional', label: 'Decisional' },
  { key: 'semantic', label: 'Semantic' },
  { key: 'procedural', label: 'Procedural' },
  { key: 'relational', label: 'Relational' },
];

/* ── freshness helpers ──────────────────────────────────────────────────── */

function isStale(iso: string): boolean {
  return Date.now() - new Date(iso).getTime() > THIRTY_DAYS_MS;
}

function FreshnessCell({ iso }: { iso: string }): React.JSX.Element {
  const stale = isStale(iso);
  return (
    <span className={`me-freshness${stale ? ' me-freshness--stale' : ''}`}>
      <Mono>{formatRelative(iso)}</Mono>
      {stale && (
        <span className="me-freshness__warning" aria-label="Stale — not verified in over 30 days">
          not checked in 30+ days
        </span>
      )}
    </span>
  );
}

/* ── detail pane ────────────────────────────────────────────────────────── */

function MemoryDetail({
  record,
  allRecords,
}: {
  record: MemoryRecord;
  allRecords: MemoryRecord[];
}): React.JSX.Element {
  const { navigate } = useRouter();

  const supersedesRecord = useMemo(
    () => (record.supersedes !== undefined ? allRecords.find((r) => r.id === record.supersedes) : undefined),
    [record.supersedes, allRecords],
  );

  const contradictedRecords = useMemo(
    () =>
      record.contradicts !== undefined
        ? record.contradicts.flatMap((cid) => {
            const found = allRecords.find((r) => r.id === cid);
            return found !== undefined ? [found] : [];
          })
        : [],
    [record.contradicts, allRecords],
  );

  const kvRows: KeyValueRow[] = [
    { k: 'ID', v: record.id, mono: true },
    { k: 'Kind', v: <Tag tone="muted">{record.kind}</Tag> },
    { k: 'Domain', v: record.domain, mono: true },
    { k: 'Recorded', v: formatRelative(record.recordedAt) },
    {
      k: 'Last verified',
      v: (
        <span className={isStale(record.lastVerifiedAt) ? 'me-detail__stale-value' : undefined}>
          {formatRelative(record.lastVerifiedAt)}
          {isStale(record.lastVerifiedAt) && ' — I have not checked this recently'}
        </span>
      ),
    },
    {
      k: 'Retention',
      v:
        record.retention.policy === 'rolling' && record.retention.days !== undefined
          ? `Rolling ${record.retention.days} days`
          : record.retention.policy,
    },
  ];

  return (
    <div className="me-detail">
      <Kicker>{record.kind} · {record.domain}</Kicker>
      <H3>{record.subject}</H3>

      <KeyValue rows={kvRows} />

      <Rule />

      <Kicker>Content</Kicker>
      <Body className="me-detail__content">{record.content}</Body>

      {record.provenance.length > 0 && (
        <>
          <Rule />
          <Kicker>Provenance</Kicker>
          <div className="me-detail__provenance">
            {record.provenance.map((ev) => (
              <div key={ev.id} className="me-evidence">
                <div className="me-evidence__header">
                  <Mono className="me-evidence__id">{ev.id}</Mono>
                  <Mono className="me-evidence__at">{formatRelative(ev.observedAt)}</Mono>
                </div>
                <div className="me-evidence__label">{ev.label}</div>
                <Dim className="me-evidence__source">{ev.source}</Dim>
                {ev.uri !== undefined && (
                  <a
                    href={ev.uri}
                    className="me-evidence__uri"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {ev.uri}
                  </a>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {(supersedesRecord !== undefined || record.supersedes !== undefined) && (
        <>
          <Rule />
          <Kicker>Supersedes</Kicker>
          {supersedesRecord !== undefined ? (
            <button
              type="button"
              className="me-detail__link-record"
              onClick={() => navigate(`/memory/${supersedesRecord.id}`)}
            >
              <Mono>{supersedesRecord.id}</Mono>
              <span className="me-detail__link-subject">{supersedesRecord.subject}</span>
            </button>
          ) : (
            <Mono className="me-detail__orphan-id">{record.supersedes}</Mono>
          )}
        </>
      )}

      {contradictedRecords.length > 0 && (
        <>
          <Rule />
          <Panel tone="risk" className="me-detail__contradictions">
            <Kicker>This record disagrees with</Kicker>
            <Dim>
              These records hold conflicting claims. Contradictions are surfaced here, never silently
              resolved.
            </Dim>
            <div className="me-detail__contradiction-list">
              {contradictedRecords.map((cr) => (
                <button
                  key={cr.id}
                  type="button"
                  className="me-detail__link-record"
                  onClick={() => navigate(`/memory/${cr.id}`)}
                >
                  <Mono>{cr.id}</Mono>
                  <span className="me-detail__link-subject">{cr.subject}</span>
                </button>
              ))}
            </div>
          </Panel>
        </>
      )}

      {record.contradicts !== undefined &&
        record.contradicts.length > 0 &&
        contradictedRecords.length < record.contradicts.length && (
          <>
            {record.contradicts
              .filter((cid) => !contradictedRecords.some((r) => r.id === cid))
              .map((cid) => (
                <Mono key={cid} className="me-detail__orphan-id">
                  Contradicts: {cid}
                </Mono>
              ))}
          </>
        )}
    </div>
  );
}

/* ── columns ────────────────────────────────────────────────────────────── */

const COLUMNS: Column<MemoryRecord>[] = [
  {
    key: 'subject',
    header: 'Subject',
    render: (r) => <span className="me-subject">{r.subject}</span>,
  },
  {
    key: 'domain',
    header: 'Domain',
    width: '8rem',
    render: (r) => <Tag tone="muted">{r.domain}</Tag>,
  },
  {
    key: 'freshness',
    header: 'Last verified',
    width: '12rem',
    render: (r) => <FreshnessCell iso={r.lastVerifiedAt} />,
  },
  {
    key: 'retention',
    header: 'Retention',
    width: '9rem',
    render: (r) => (
      <Mono>
        {r.retention.policy === 'rolling' && r.retention.days !== undefined
          ? `${r.retention.days}d rolling`
          : r.retention.policy}
      </Mono>
    ),
  },
];

/* ── main component ─────────────────────────────────────────────────────── */

export function MemoryExplorer(): React.JSX.Element {
  const kernel = useKernel();
  const location = useLocation();
  const { navigate } = useRouter();

  const [activeKind, setActiveKind] = useState<MemoryKind>('episodic');
  const [search, setSearch] = useState('');
  const [domain, setDomain] = useState('');

  const { data, loading, error, reload } = useAsync(
    () =>
      kernel.queryMemory({
        kind: activeKind,
        domain: domain !== '' ? domain : undefined,
        search: search !== '' ? search : undefined,
      }),
    [kernel, activeKind, domain, search],
  );

  const records = useMemo((): MemoryRecord[] => (data?.items as MemoryRecord[]) ?? [], [data]);

  const selectedId = location.detail;
  const selectedRecord = useMemo(
    () => records.find((r) => r.id === selectedId),
    [records, selectedId],
  );

  const meta = KIND_META[activeKind];

  const listPane = (
    <div className="me-list-pane">
      <H2>Memory</H2>

      <Tabs
        tabs={KIND_TABS}
        active={activeKind}
        onChange={(k) => setActiveKind(k as MemoryKind)}
      />

      {meta !== undefined && (
        <div className="me-kind-meta">
          <Mono className="me-kind-meta__desc">{meta.description}</Mono>
          <Mono className="me-kind-meta__retention">Retention: {meta.retention}</Mono>
        </div>
      )}

      <div className="me-filters">
        <SearchField
          label="Search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter by subject or content…"
        />
        <SelectField
          label="Domain"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          options={DOMAIN_OPTIONS}
        />
      </div>

      {loading && (
        <div className="me-skeletons">
          <Skeleton lines={2} />
          <Skeleton lines={2} />
          <Skeleton lines={2} />
        </div>
      )}

      {error !== undefined && <ErrorState error={error} onRetry={reload} />}

      {!loading && error === undefined && records.length === 0 && (
        <EmptyState
          headline={`No ${activeKind} records.`}
          body={
            activeKind === 'episodic'
              ? 'No episodes have been recorded yet.'
              : activeKind === 'decisional'
              ? 'No decisions have been recorded yet.'
              : activeKind === 'semantic'
              ? 'No facts or beliefs have been stored yet.'
              : activeKind === 'procedural'
              ? 'No procedures have been stored yet.'
              : 'No relational data has been recorded yet.'
          }
        />
      )}

      {!loading && records.length > 0 && (
        <DataTable<MemoryRecord>
          columns={COLUMNS}
          rows={records}
          onRowClick={(r) => navigate(`/memory/${r.id}`)}
        />
      )}
    </div>
  );

  const detailPane = (
    <div className="me-detail-pane">
      {selectedRecord !== undefined ? (
        <MemoryDetail record={selectedRecord} allRecords={records} />
      ) : (
        <EmptyState
          headline="Select a record."
          body="Choose a memory record from the list to see its full content, provenance, and any contradictions."
        />
      )}
    </div>
  );

  return (
    <div className="me-root">
      <SplitView left={listPane} right={detailPane} />
    </div>
  );
}
