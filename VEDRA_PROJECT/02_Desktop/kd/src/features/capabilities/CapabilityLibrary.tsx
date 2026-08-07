/**
 * CapabilityLibrary — the reversibility registry made visible.
 *
 * Fail-closed: unclassified capabilities are separated into their own section.
 * Summary strip at top. Grouped by DomainKey.
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
  Stat,
  Tag,
} from '@/components';
import type { Column, KeyValueRow, SelectOption } from '@/components';
import { useAsync } from '@/kernel/hooks';
import { useKernel } from '@/kernel/KernelProvider';
import { useLocation, useRouter } from '@/app/router';
import type { Capability, CapabilityStatus, DomainKey } from '@/kernel/types';
import {
  formatCount,
  formatPercent,
  formatRelative,
  formatReversibility,
} from '@/lib/format';
import './CapabilityLibrary.css';

/* ── constants ──────────────────────────────────────────────────────────── */

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

const STATUS_OPTIONS: SelectOption[] = [
  { value: '', label: 'All statuses' },
  { value: 'available', label: 'Available' },
  { value: 'blocked', label: 'Blocked' },
  { value: 'unclassified', label: 'Unclassified' },
];

/* ── helpers ────────────────────────────────────────────────────────────── */

function statusTone(status: CapabilityStatus): 'done' | 'risk' | 'needs-you' {
  if (status === 'available') return 'done';
  if (status === 'blocked') return 'risk';
  return 'needs-you';
}

/* ── detail pane ────────────────────────────────────────────────────────── */

function CapabilityDetail({ cap }: { cap: Capability }): React.JSX.Element {
  const kvRows: KeyValueRow[] = [
    { k: 'ID', v: cap.id, mono: true },
    { k: 'Domain', v: cap.domain, mono: true },
    { k: 'Status', v: <Tag tone={statusTone(cap.status)}>{cap.status}</Tag> },
    { k: 'Invocations', v: <Mono>{formatCount(cap.invocations)}</Mono> },
    ...(cap.lastUsedAt !== undefined
      ? [{ k: 'Last used', v: formatRelative(cap.lastUsedAt) }]
      : [{ k: 'Last used', v: <Dim>Never used</Dim> }]),
    {
      k: 'Requires judgment',
      v: cap.requiresJudgment ? <Tag tone="needs-you">yes</Tag> : <Tag tone="muted">no</Tag>,
    },
    {
      k: 'Reversibility',
      v:
        cap.reversibility !== null ? (
          <span>{formatReversibility(cap.reversibility)}</span>
        ) : (
          <Tag tone="risk">unclassified</Tag>
        ),
    },
  ];

  return (
    <div className="cl-detail">
      <Kicker>{cap.domain}</Kicker>
      <H3>{cap.name}</H3>
      <Body className="cl-detail__description">{cap.description}</Body>

      <KeyValue rows={kvRows} />

      {cap.status === 'unclassified' && (
        <>
          <Rule />
          <Panel tone="risk" className="cl-detail__unclassified-notice">
            <Kicker>Non-executable by design</Kicker>
            <Body>
              This capability has not been classified for reversibility. The registry fails closed:
              unclassified capabilities cannot be invoked until a reversibility classification is
              recorded.
            </Body>
          </Panel>
        </>
      )}

      {cap.status === 'blocked' && (
        <>
          <Rule />
          <Panel tone="risk" className="cl-detail__blocked-notice">
            <Kicker>Blocked</Kicker>
            <Body>This capability is currently blocked from execution.</Body>
          </Panel>
        </>
      )}
    </div>
  );
}

/* ── capability row group ───────────────────────────────────────────────── */

function buildColumns(): Column<Capability>[] {
  return [
    {
      key: 'name',
      header: 'Name',
      render: (c) => (
        <span className="cl-name-cell">
          {c.name}
          {c.requiresJudgment && (
            <Tag tone="needs-you" className="cl-judgment-tag">
              judgment
            </Tag>
          )}
        </span>
      ),
    },
    {
      key: 'reversibility',
      header: 'Reversible',
      width: '10rem',
      render: (c) => {
        if (c.reversibility === null) {
          return <Tag tone="risk">unclassified</Tag>;
        }
        const tone =
          c.reversibility.kind === 'irreversible'
            ? 'risk'
            : c.reversibility.kind === 'reversible-until'
            ? 'needs-you'
            : 'done';
        return (
          <span title={formatReversibility(c.reversibility)}>
            <Tag tone={tone}>{c.reversibility.kind}</Tag>
          </span>
        );
      },
    },
    {
      key: 'invocations',
      header: 'Used',
      width: '6rem',
      align: 'right',
      mono: true,
      render: (c) => formatCount(c.invocations),
    },
    {
      key: 'lastUsed',
      header: 'Last used',
      width: '9rem',
      render: (c) =>
        c.lastUsedAt !== undefined ? (
          <Mono>{formatRelative(c.lastUsedAt)}</Mono>
        ) : (
          <span className="cl-never">never</span>
        ),
    },
    {
      key: 'status',
      header: 'Status',
      width: '8rem',
      render: (c) => <Tag tone={statusTone(c.status)}>{c.status}</Tag>,
    },
  ];
}

interface DomainGroupProps {
  domain: DomainKey;
  capabilities: Capability[];
  columns: Column<Capability>[];
  onSelect: (c: Capability) => void;
}

function DomainGroup({ domain, capabilities, columns, onSelect }: DomainGroupProps): React.JSX.Element {
  return (
    <div className="cl-domain-group">
      <div className="cl-domain-group__header">
        <H3>{domain}</H3>
        <Mono className="cl-domain-group__count">{formatCount(capabilities.length)}</Mono>
      </div>
      <DataTable<Capability>
        columns={columns}
        rows={capabilities}
        onRowClick={onSelect}
      />
    </div>
  );
}

/* ── main component ─────────────────────────────────────────────────────── */

export function CapabilityLibrary(): React.JSX.Element {
  const kernel = useKernel();
  const location = useLocation();
  const { navigate } = useRouter();

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [domainFilter, setDomainFilter] = useState('');

  const { data, loading, error, reload } = useAsync(
    () => kernel.listCapabilities(),
    [kernel],
  );

  const all = useMemo((): Capability[] => (data ?? []) as Capability[], [data]);

  const filtered = useMemo(() => {
    let caps = all;
    if (search !== '') {
      const q = search.toLowerCase();
      caps = caps.filter(
        (c) => c.name.toLowerCase().includes(q) || c.description.toLowerCase().includes(q),
      );
    }
    if (statusFilter !== '') {
      caps = caps.filter((c) => c.status === statusFilter);
    }
    if (domainFilter !== '') {
      caps = caps.filter((c) => c.domain === domainFilter);
    }
    return caps;
  }, [all, search, statusFilter, domainFilter]);

  // Separate unclassified from rest
  const classified = useMemo(
    () => filtered.filter((c) => c.status !== 'unclassified'),
    [filtered],
  );
  const unclassified = useMemo(
    () => filtered.filter((c) => c.status === 'unclassified'),
    [filtered],
  );

  // Group classified by domain
  const groupedByDomain = useMemo(() => {
    const groups = new Map<DomainKey, Capability[]>();
    for (const cap of classified) {
      const existing = groups.get(cap.domain);
      if (existing !== undefined) {
        existing.push(cap);
      } else {
        groups.set(cap.domain, [cap]);
      }
    }
    return groups;
  }, [classified]);

  // Summary stats
  const total = all.length;
  const available = all.filter((c) => c.status === 'available').length;
  const unclassifiedCount = all.filter((c) => c.status === 'unclassified').length;
  const blocked = all.filter((c) => c.status === 'blocked').length;
  const requiresJudgment = all.filter((c) => c.requiresJudgment).length;
  const judgmentShare = total > 0 ? requiresJudgment / total : 0;

  const selectedId = location.detail;
  const selectedCap = useMemo(
    () => all.find((c) => c.id === selectedId),
    [all, selectedId],
  );

  const columns = useMemo(() => buildColumns(), []);

  const listPane = (
    <div className="cl-list-pane">
      <H2>Capability library</H2>

      {/* Summary strip */}
      {all.length > 0 && (
        <div className="cl-stats">
          <Stat value={formatCount(total)} label="Total" />
          <Stat value={formatCount(available)} label="Available" tone="done" />
          <Stat value={formatCount(unclassifiedCount)} label="Unclassified" tone="risk" />
          <Stat value={formatCount(blocked)} label="Blocked" tone="needs-you" />
          <Stat value={formatPercent(judgmentShare)} label="Require judgment" tone="muted" />
        </div>
      )}

      {/* Filters */}
      <div className="cl-filters">
        <SearchField
          label="Search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter by name or description…"
        />
        <SelectField
          label="Status"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          options={STATUS_OPTIONS}
        />
        <SelectField
          label="Domain"
          value={domainFilter}
          onChange={(e) => setDomainFilter(e.target.value)}
          options={DOMAIN_OPTIONS}
        />
      </div>

      {loading && (
        <div className="cl-skeletons">
          <Skeleton height={48} />
          <Skeleton height={48} />
          <Skeleton height={48} />
        </div>
      )}

      {error !== undefined && <ErrorState error={error} onRetry={reload} />}

      {!loading && error === undefined && filtered.length === 0 && (
        <EmptyState
          headline="No capabilities match the current filter."
          body="The library is the full set of actions the kernel can take. Adjust the filters to find a specific capability."
        />
      )}

      {/* Classified groups */}
      {Array.from(groupedByDomain.entries()).map(([domain, caps]) => (
        <DomainGroup
          key={domain}
          domain={domain}
          capabilities={caps}
          columns={columns}
          onSelect={(c) => navigate(`/capabilities/${c.id}`)}
        />
      ))}

      {/* Unclassified section */}
      {unclassified.length > 0 && (
        <div className="cl-unclassified-section">
          <Panel tone="risk" className="cl-unclassified-notice">
            <Kicker>Unclassified — non-executable by design</Kicker>
            <Body>
              The following capabilities have not been classified for reversibility. The registry
              fails closed: an unclassified capability cannot be invoked until a reversibility
              classification is recorded. This is not an error — it is the intended behaviour.
            </Body>
            <Mono className="cl-unclassified-count">
              {formatCount(unclassified.length)} unclassified capability
              {unclassified.length !== 1 ? 'ies' : 'y'}
            </Mono>
          </Panel>
          <DataTable<Capability>
            columns={columns}
            rows={unclassified}
            onRowClick={(c) => navigate(`/capabilities/${c.id}`)}
          />
        </div>
      )}
    </div>
  );

  const detailPane = (
    <div className="cl-detail-pane">
      {selectedCap !== undefined ? (
        <CapabilityDetail cap={selectedCap} />
      ) : (
        <EmptyState
          headline="Select a capability."
          body="Click any row to see its reversibility classification, invocation history, and whether it requires judgment."
        />
      )}
    </div>
  );

  return (
    <div className="cl-root">
      <SplitView left={listPane} right={detailPane} />
    </div>
  );
}
