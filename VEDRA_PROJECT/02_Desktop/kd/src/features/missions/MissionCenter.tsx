/**
 * MissionCenter — operational view of all kernel work.
 *
 * Tabs: Active · Held · Completed · Failed, with counts.
 * Left list + right SplitView detail panel.
 * Live events applied in-place (no full refetch).
 */
import React, { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';
import {
  Bar,
  Body,
  Button,
  Dim,
  EmptyState,
  ErrorState,
  H2,
  H3,
  KeyValue,
  Kicker,
  Mono,
  Panel,
  Skeleton,
  SplitView,
  Tag,
  Tabs,
  Timeline,
} from '@/components';
import type { KeyValueRow } from '@/components';
import type { TimelineItem } from '@/components';
import type { TabDef } from '@/components';
import { useAsync, useKernelEvents, useMutation } from '@/kernel/hooks';
import { useKernel } from '@/kernel/KernelProvider';
import { useLocation, useRouter } from '@/app/router';
import type { KernelError } from '@/kernel/client';
import type { Mission, Receipt } from '@/kernel/types';
import { formatCount, formatDuration, formatPercent, formatRelative } from '@/lib/format';
import './MissionCenter.css';

/* ── types ─────────────────────────────────────────────────────────────── */

type TabKey = 'active' | 'held' | 'completed' | 'failed';

interface MissionMap {
  active: Mission[];
  held: Mission[];
  completed: Mission[];
  failed: Mission[];
}

type MissionAction =
  | { type: 'seed'; missions: readonly Mission[] }
  | { type: 'progress'; id: string; progress: number; etaSeconds?: number }
  | { type: 'complete'; id: string }
  | { type: 'hold'; id: string };

function toMap(missions: readonly Mission[]): MissionMap {
  const m: MissionMap = { active: [], held: [], completed: [], failed: [] };
  for (const mission of missions) {
    if (mission.state === 'running' || mission.state === 'queued') {
      m.active.push(mission);
    } else if (mission.state === 'held') {
      m.held.push(mission);
    } else if (mission.state === 'completed') {
      m.completed.push(mission);
    } else if (mission.state === 'failed') {
      m.failed.push(mission);
    }
  }
  return m;
}

function missionsReducer(state: MissionMap, action: MissionAction): MissionMap {
  switch (action.type) {
    case 'seed':
      return toMap(action.missions);
    case 'progress': {
      return {
        ...state,
        active: state.active.map((m) =>
          m.id === action.id
            ? { ...m, progress: action.progress, etaSeconds: action.etaSeconds }
            : m,
        ),
      };
    }
    case 'complete': {
      const mission = state.active.find((m) => m.id === action.id);
      if (!mission) return state;
      const updated: Mission = { ...mission, state: 'completed' };
      return {
        ...state,
        active: state.active.filter((m) => m.id !== action.id),
        completed: [updated, ...state.completed],
      };
    }
    case 'hold': {
      const mission = state.active.find((m) => m.id === action.id);
      if (!mission) return state;
      const updated: Mission = { ...mission, state: 'held' };
      return {
        ...state,
        active: state.active.filter((m) => m.id !== action.id),
        held: [updated, ...state.held],
      };
    }
  }
}

/* ── sub-components ────────────────────────────────────────────────────── */

function ImpactTag({ impact }: { impact: Mission['impact'] }): React.JSX.Element {
  const tone = impact === 'high' ? 'risk' : impact === 'medium' ? 'needs-you' : 'muted';
  return <Tag tone={tone}>{impact}</Tag>;
}

function MissionRow({
  mission,
  selected,
  onClick,
}: {
  mission: Mission;
  selected: boolean;
  onClick: () => void;
}): React.JSX.Element {
  const isRunning = mission.state === 'running';
  const isHeld = mission.state === 'held';
  const isFailed = mission.state === 'failed';

  return (
    <button
      type="button"
      className={`mc-mission-row${selected ? ' mc-mission-row--selected' : ''}`}
      onClick={onClick}
      aria-current={selected ? 'true' : undefined}
    >
      <div className="mc-mission-row__header">
        <Mono className="mc-mission-row__id">{mission.id}</Mono>
        <ImpactTag impact={mission.impact} />
      </div>
      <div className="mc-mission-row__name">{mission.name}</div>

      {isRunning && mission.progress !== undefined && (
        <div className="mc-mission-row__progress">
          <Bar value={mission.progress} tone="live" />
          <div className="mc-mission-row__progress-label">
            <Mono>{formatPercent(mission.progress)}</Mono>
            {mission.etaSeconds !== undefined && (
              <Mono className="mc-mission-row__eta">
                {formatDuration(mission.etaSeconds)} remaining
              </Mono>
            )}
          </div>
        </div>
      )}

      {isHeld && (
        <div className="mc-mission-row__held">
          <Tag tone="needs-you">held</Tag>
          <span className="mc-mission-row__held-since">
            {' '}blocked {formatRelative(mission.startedAt)}
          </span>
          {mission.heldOnRequestId !== undefined && (
            <a
              href={`#/console/${mission.heldOnRequestId}`}
              className="mc-mission-row__held-link"
              onClick={(e) => e.stopPropagation()}
            >
              view request
            </a>
          )}
        </div>
      )}

      {isFailed && mission.failure !== undefined && (
        <div className="mc-mission-row__failure">
          <Tag tone="risk">failed</Tag>
          <Body className="mc-mission-row__risk">{mission.failure.whatIsAtRisk}</Body>
          <Mono className="mc-mission-row__next-attempt">
            Next attempt: {mission.failure.nextAttempt}
          </Mono>
        </div>
      )}
    </button>
  );
}


function MissionDetail({ mission }: { mission: Mission }): React.JSX.Element {
  const kernel = useKernel();

  // Load all receipts for the timeline
  const receiptResults = useAsync(
    useCallback(async () => {
      if (mission.receiptIds.length === 0) {
        return { ok: true as const, value: [] as Receipt[] };
      }
      const fetched: Receipt[] = [];
      for (const id of mission.receiptIds) {
        const r = await kernel.getReceipt(id);
        if (r.ok) fetched.push(r.value);
      }
      return { ok: true as const, value: fetched };
    }, [kernel, mission.receiptIds]),
    [kernel, mission.id],
  );

  const timelineItems: TimelineItem[] = useMemo(() => {
    if (!receiptResults.data) return [];
    return receiptResults.data.map((r): TimelineItem => ({
      id: r.id,
      at: formatRelative(r.at),
      line: `${r.actionType} — ${r.expectedEffect}${r.actualEffect !== undefined ? ` → ${r.actualEffect}` : ''}`,
      tone: r.result === 'failed' ? 'risk' : r.result === 'ok' ? 'done' : undefined,
    }));
  }, [receiptResults.data]);

  const stateSignal = mission.state === 'running' ? 'live'
    : mission.state === 'held' ? 'needs-you'
    : mission.state === 'completed' ? 'done'
    : mission.state === 'failed' ? 'risk'
    : 'muted';

  const kvRows: KeyValueRow[] = [
    { k: 'ID', v: mission.id, mono: true },
    { k: 'Domain', v: mission.domain, mono: true },
    { k: 'Impact', v: <ImpactTag impact={mission.impact} /> },
    { k: 'State', v: <Tag tone={stateSignal}>{mission.state}</Tag> },
    { k: 'Started', v: formatRelative(mission.startedAt) },
    ...(mission.endedAt !== undefined
      ? [{ k: 'Ended', v: formatRelative(mission.endedAt) }]
      : []),
  ];

  return (
    <div className="mc-detail">
      <Kicker>{mission.domain}</Kicker>
      <H3>{mission.name}</H3>
      <Body className="mc-detail__summary">{mission.summary}</Body>
      <KeyValue rows={kvRows} />

      {mission.failure !== undefined && (
        <Panel tone="risk" className="mc-detail__failure-panel">
          <Kicker>What is at risk</Kicker>
          <Body>{mission.failure.whatIsAtRisk}</Body>
          <Dim>Next attempt: {mission.failure.nextAttempt}</Dim>
        </Panel>
      )}

      <div className="mc-detail__timeline-header">
        <H3>Receipt chain</H3>
        <Mono className="mc-detail__receipt-count">
          {formatCount(mission.receiptIds.length)} receipts
        </Mono>
      </div>

      {receiptResults.loading && <Skeleton lines={4} />}
      {receiptResults.error !== undefined && (
        <ErrorState error={receiptResults.error} onRetry={receiptResults.reload} />
      )}
      {!receiptResults.loading && receiptResults.data !== undefined && (
        <>
          {timelineItems.length === 0 ? (
            <EmptyState
              headline="No receipts yet."
              body="This mission has not recorded any actions."
            />
          ) : (
            <Timeline items={timelineItems} />
          )}
        </>
      )}
    </div>
  );
}

/* ── request mission ────────────────────────────────────────────────────── */

function RequestMissionForm(): React.JSX.Element {
  const [brief, setBrief] = useState('');
  const mutation = useMutation((client, b: string) => client.requestMission(b));

  const handleSubmit = useCallback(async () => {
    if (brief.trim() === '') return;
    const result = await mutation.run(brief.trim());
    if (result.ok) setBrief('');
  }, [brief, mutation]);

  const notImpl = mutation.error?.code === 'not-implemented';

  return (
    <div className="mc-request-form">
      <Kicker>Request a mission</Kicker>
      <textarea
        className="mc-request-form__textarea"
        value={brief}
        onChange={(e) => setBrief(e.target.value)}
        placeholder="Describe what you need the kernel to do."
        rows={3}
        disabled={mutation.pending || notImpl}
        aria-label="Mission brief"
      />
      <div className="mc-request-form__footer">
        <Button
          variant="primary"
          size="sm"
          disabled={mutation.pending || notImpl || brief.trim() === ''}
          onClick={() => void handleSubmit()}
        >
          {mutation.pending ? 'Submitting…' : 'Request mission'}
        </Button>
        {notImpl && mutation.error !== undefined && (
          <Dim className="mc-request-form__reason">
            Not available: {mutation.error.message}
          </Dim>
        )}
        {mutation.error !== undefined && !notImpl && (
          <Dim className="mc-request-form__reason">{mutation.error.message}</Dim>
        )}
      </div>
    </div>
  );
}

/* ── main component ─────────────────────────────────────────────────────── */

export function MissionCenter(): React.JSX.Element {
  const kernel = useKernel();
  const location = useLocation();
  const { navigate } = useRouter();

  const [missions, dispatch] = useReducer(missionsReducer, {
    active: [],
    held: [],
    completed: [],
    failed: [],
  });

  const [seeded, setSeeded] = useState(false);
  const [loadError, setLoadError] = useState<KernelError | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [reloadFlag, setReloadFlag] = useState(0);

  const reload = useCallback(() => setReloadFlag((n) => n + 1), []);

  // Initial load — all states
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setLoadError(undefined);

    void (async () => {
      const result = await kernel.listMissions();
      if (!alive) return;
      if (result.ok) {
        dispatch({ type: 'seed', missions: result.value.items });
        setSeeded(true);
      } else {
        setLoadError(result.error);
      }
      setLoading(false);
    })();

    return () => { alive = false; };
  }, [kernel, reloadFlag]);

  // Live event subscription — apply in-place, no refetch
  const events = useKernelEvents(200);
  const lastProcessedIdRef = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (!seeded) return;
    // Events are newest-first. Walk until we hit the last-processed id.
    for (const event of events) {
      if (event.id === lastProcessedIdRef.current) break;
      if (event.refs?.missionId === undefined) continue;
      const mId = event.refs.missionId;
      if (event.type === 'mission.progress') {
        // Parse progress from line e.g. "42%"
        const match = /(\d+)%/.exec(event.line);
        const pct = match?.[1] !== undefined ? parseInt(match[1]!, 10) / 100 : undefined;
        if (pct !== undefined) {
          dispatch({ type: 'progress', id: mId, progress: pct });
        }
      } else if (event.type === 'mission.completed') {
        dispatch({ type: 'complete', id: mId });
      } else if (event.type === 'mission.held') {
        dispatch({ type: 'hold', id: mId });
      }
    }
    const newest = events[0];
    if (newest !== undefined) lastProcessedIdRef.current = newest.id;
    // We only want to react when events array reference changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events, seeded]);

  const [activeTab, setActiveTab] = useState<TabKey>('active');

  const selectedId = location.detail;

  const allMissions = useMemo<Mission[]>(() => {
    const m = missions[activeTab];
    return m ?? [];
  }, [missions, activeTab]);

  const selectedMission = useMemo(() => {
    if (selectedId === undefined) return undefined;
    for (const list of Object.values(missions)) {
      const found = list.find((m) => m.id === selectedId);
      if (found !== undefined) return found;
    }
    return undefined;
  }, [selectedId, missions]);

  const tabs: TabDef[] = [
    { key: 'active', label: 'Active', count: missions.active.length },
    { key: 'held', label: 'Held', count: missions.held.length },
    { key: 'completed', label: 'Completed', count: missions.completed.length },
    { key: 'failed', label: 'Failed', count: missions.failed.length },
  ];

  const listPane = (
    <div className="mc-list-pane">
      <div className="mc-list-pane__header">
        <H2>Missions</H2>
        <Mono className="mc-list-pane__count">
          {formatCount(
            missions.active.length +
              missions.held.length +
              missions.completed.length +
              missions.failed.length,
          )}{' '}
          total
        </Mono>
      </div>

      <Tabs tabs={tabs} active={activeTab} onChange={(k) => setActiveTab(k as TabKey)} />

      {loading && !seeded && (
        <div className="mc-list-pane__skeletons">
          <Skeleton lines={3} />
          <Skeleton lines={3} />
          <Skeleton lines={3} />
        </div>
      )}

      {loadError !== undefined && (
        <ErrorState error={loadError} onRetry={reload} />
      )}

      {!loading && loadError === undefined && allMissions.length === 0 && (
        <EmptyState
          headline={`No ${activeTab} missions.`}
          body={
            activeTab === 'active'
              ? 'The kernel is not running any work right now.'
              : activeTab === 'held'
              ? 'Nothing is waiting for a decision.'
              : activeTab === 'failed'
              ? 'No missions have failed.'
              : 'No missions have finished yet.'
          }
        />
      )}

      <div className="mc-list-pane__items">
        {allMissions.map((mission) => (
          <MissionRow
            key={mission.id}
            mission={mission}
            selected={mission.id === selectedId}
            onClick={() => navigate(`/missions/${mission.id}`)}
          />
        ))}
      </div>

      <RequestMissionForm />
    </div>
  );

  const detailPane = (
    <div className="mc-detail-pane">
      {selectedMission !== undefined ? (
        <MissionDetail mission={selectedMission} />
      ) : (
        <EmptyState
          headline="Select a mission."
          body="Choose a mission from the list to see its details, summary, and receipt chain."
        />
      )}
    </div>
  );

  return (
    <div className="mc-root">
      <SplitView left={listPane} right={detailPane} />
    </div>
  );
}
