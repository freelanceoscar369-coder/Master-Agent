/**
 * LiveEventStream — dense mono log with follow mode, filters, and stream status.
 *
 * Follow mode: auto-scrolls to newest. Scrolling up pauses follow.
 * Ring buffer capped at BUFFER_CAP (shown in header).
 * New rows enter with a 240ms fade.
 * Connection state from useStreamStatus().
 */
import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  Body,
  Button,
  Dim,
  EmptyState,
  ErrorState,
  H2,
  Kicker,
  Mono,
  Panel,
  Rule,
  SearchField,
  SelectField,
  Tag,
} from '@/components';
import type { SelectOption } from '@/components';
import { useKernelEvents, useStreamStatus } from '@/kernel/hooks';
import { useRouter } from '@/app/router';
import type { DomainKey, KernelEvent, KernelEventType, Signal } from '@/kernel/types';
import { formatClock } from '@/lib/format';
import './LiveEventStream.css';

/* ── constants ──────────────────────────────────────────────────────────── */

const BUFFER_CAP = 500;

const EVENT_TYPE_OPTIONS: SelectOption[] = [
  { value: '', label: 'All types' },
  { value: 'mission.started', label: 'mission.started' },
  { value: 'mission.progress', label: 'mission.progress' },
  { value: 'mission.completed', label: 'mission.completed' },
  { value: 'mission.failed', label: 'mission.failed' },
  { value: 'mission.held', label: 'mission.held' },
  { value: 'receipt.intent', label: 'receipt.intent' },
  { value: 'receipt.outcome', label: 'receipt.outcome' },
  { value: 'judgment.opened', label: 'judgment.opened' },
  { value: 'judgment.resolved', label: 'judgment.resolved' },
  { value: 'judgment.default-fired', label: 'judgment.default-fired' },
  { value: 'rule.proposed', label: 'rule.proposed' },
  { value: 'rule.granted', label: 'rule.granted' },
  { value: 'rule.fired', label: 'rule.fired' },
  { value: 'rule.expired', label: 'rule.expired' },
  { value: 'audit.flagged', label: 'audit.flagged' },
  { value: 'presence.changed', label: 'presence.changed' },
  { value: 'attestation.updated', label: 'attestation.updated' },
  { value: 'boundary.changed', label: 'boundary.changed' },
  { value: 'mistake.disclosed', label: 'mistake.disclosed' },
];

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

const SIGNAL_OPTIONS: SelectOption[] = [
  { value: '', label: 'All signals' },
  { value: 'live', label: 'Live' },
  { value: 'needs-you', label: 'Needs you' },
  { value: 'done', label: 'Done' },
  { value: 'risk', label: 'Risk' },
];

/* ── event type → tag tone ──────────────────────────────────────────────── */

function eventTypeTone(type: KernelEventType): Signal | 'muted' {
  if (type.startsWith('mission.')) {
    if (type === 'mission.failed') return 'risk';
    if (type === 'mission.held') return 'needs-you';
    if (type === 'mission.completed') return 'done';
    return 'live';
  }
  if (type.startsWith('judgment.')) {
    if (type === 'judgment.opened') return 'needs-you';
    if (type === 'judgment.resolved') return 'done';
    return 'needs-you';
  }
  if (type.startsWith('rule.')) {
    if (type === 'rule.expired') return 'risk';
    if (type === 'rule.fired' || type === 'rule.granted') return 'done';
    return 'muted';
  }
  if (type === 'audit.flagged') return 'risk';
  if (type === 'mistake.disclosed') return 'risk';
  if (type === 'boundary.changed') return 'needs-you';
  return 'muted';
}

/* ── stream status display ──────────────────────────────────────────────── */

function StreamStatusBar(): React.JSX.Element {
  const status = useStreamStatus();

  const tone: Signal | 'muted' = status.connected
    ? 'live'
    : status.retries > 0
    ? 'needs-you'
    : 'risk';

  const label = status.connected
    ? 'Connected'
    : status.retries > 0
    ? 'Reconnecting'
    : 'Offline';

  return (
    <div className="les-stream-status">
      <Tag tone={tone}>{label}</Tag>
      <Mono className="les-stream-status__transport">{status.transport}</Mono>
      {status.retries > 0 && (
        <Mono className="les-stream-status__retries">retry {status.retries}</Mono>
      )}
    </div>
  );
}

/* ── event row ──────────────────────────────────────────────────────────── */

interface EventRowProps {
  event: KernelEvent;
  isNew: boolean;
}

function EventRow({ event, isNew }: EventRowProps): React.JSX.Element {
  const { navigate } = useRouter();
  const tone = eventTypeTone(event.type);

  const refs = event.refs;

  return (
    <div
      className={`les-event-row les-event-row--signal-${event.signal}${isNew ? ' les-event-row--new' : ''}`}
      role="row"
    >
      <Mono className="les-event-row__time">{formatClock(event.at)}</Mono>
      <Tag tone={tone} className="les-event-row__type">
        {event.type}
      </Tag>
      <span className="les-event-row__line">{event.line}</span>
      <Mono className="les-event-row__domain">{event.domain}</Mono>
      {refs !== undefined && (
        <div className="les-event-row__refs">
          {refs.missionId !== undefined && (
            <button
              type="button"
              className="les-event-row__ref-link"
              onClick={() => { const id = refs.missionId; if (id !== undefined) navigate(`/missions/${id}`); }}
              aria-label={`Mission ${refs.missionId}`}
            >
              <Mono>msn</Mono>
            </button>
          )}
          {refs.receiptId !== undefined && (
            <button
              type="button"
              className="les-event-row__ref-link"
              onClick={() => { const id = refs.receiptId; if (id !== undefined) navigate(`/ledger/${id}`); }}
              aria-label={`Receipt ${refs.receiptId}`}
            >
              <Mono>rcpt</Mono>
            </button>
          )}
          {refs.requestId !== undefined && (
            <button
              type="button"
              className="les-event-row__ref-link"
              onClick={() => { const id = refs.requestId; if (id !== undefined) navigate(`/console/${id}`); }}
              aria-label={`Request ${refs.requestId}`}
            >
              <Mono>req</Mono>
            </button>
          )}
          {refs.ruleId !== undefined && (
            <button
              type="button"
              className="les-event-row__ref-link"
              onClick={() => { const id = refs.ruleId; if (id !== undefined) navigate(`/autonomy/${id}`); }}
              aria-label={`Rule ${refs.ruleId}`}
            >
              <Mono>rule</Mono>
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/* ── main component ─────────────────────────────────────────────────────── */

export function LiveEventStream(): React.JSX.Element {
  const allEvents = useKernelEvents(BUFFER_CAP);

  const [paused, setPaused] = useState(false);
  const [following, setFollowing] = useState(true);
  const [newCount, setNewCount] = useState(0);
  const [typeFilter, setTypeFilter] = useState('');
  const [domainFilter, setDomainFilter] = useState('');
  const [signalFilter, setSignalFilter] = useState('');
  const [searchText, setSearchText] = useState('');

  const scrollRef = useRef<HTMLDivElement>(null);
  const prevLengthRef = useRef(0);
  const userScrollingRef = useRef(false);
  const scrollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Track new-event IDs for fade-in (only within a short window)
  const [recentIds, setRecentIds] = useState<Set<string>>(new Set());

  // Buffer: when paused, we freeze the display
  const [frozenEvents, setFrozenEvents] = useState<readonly KernelEvent[]>(allEvents);
  const displayEvents = paused ? frozenEvents : allEvents;

  useEffect(() => {
    if (paused) return;
    setFrozenEvents(allEvents);

    const newLength = allEvents.length;
    const delta = newLength - prevLengthRef.current;
    if (delta > 0) {
      // Mark new events for fade-in
      const newIds = new Set<string>();
      for (let i = 0; i < delta; i++) {
        const ev = allEvents[i];
        if (ev !== undefined) newIds.add(ev.id);
      }
      setRecentIds(newIds);
      setTimeout(() => setRecentIds(new Set()), 420);

      if (!following) {
        setNewCount((n) => n + delta);
      }
    }
    prevLengthRef.current = newLength;
  }, [allEvents, paused, following]);

  // Auto-scroll to top (newest events are at top due to ring buffer ordering)
  useEffect(() => {
    if (following && !userScrollingRef.current && scrollRef.current !== null) {
      scrollRef.current.scrollTop = 0;
    }
  }, [displayEvents, following]);

  const handleScroll = useCallback(() => {
    if (scrollRef.current === null) return;
    const { scrollTop } = scrollRef.current;

    // Treat scrollTop > 64px as "reading up"
    if (scrollTop > 64) {
      userScrollingRef.current = true;
      setFollowing(false);
      if (scrollTimerRef.current !== null) clearTimeout(scrollTimerRef.current);
    } else {
      userScrollingRef.current = false;
    }
  }, []);

  const resumeFollow = useCallback(() => {
    setFollowing(true);
    setNewCount(0);
    if (scrollRef.current !== null) {
      scrollRef.current.scrollTop = 0;
    }
  }, []);

  const togglePause = useCallback(() => {
    setPaused((p) => {
      if (p) {
        // resuming
        setFrozenEvents(allEvents);
        prevLengthRef.current = allEvents.length;
      } else {
        setFrozenEvents(allEvents);
      }
      return !p;
    });
  }, [allEvents]);

  const filtered = useMemo(() => {
    let evs = displayEvents;
    if (typeFilter !== '') {
      evs = evs.filter((e) => e.type === typeFilter);
    }
    if (domainFilter !== '') {
      evs = evs.filter((e) => e.domain === (domainFilter as DomainKey));
    }
    if (signalFilter !== '') {
      evs = evs.filter((e) => e.signal === signalFilter);
    }
    if (searchText !== '') {
      const q = searchText.toLowerCase();
      evs = evs.filter(
        (e) => e.line.toLowerCase().includes(q) || e.type.includes(q),
      );
    }
    return evs;
  }, [displayEvents, typeFilter, domainFilter, signalFilter, searchText]);

  return (
    <div className="les-root">
      <div className="les-header">
        <div className="les-header__top">
          <H2>Live event stream</H2>
          <StreamStatusBar />
        </div>
        <Mono className="les-buffer-label">
          last {BUFFER_CAP} events — ring buffer
        </Mono>

        <div className="les-controls">
          <div className="les-filters">
            <SearchField
              label="Search"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder="Filter by line text or type…"
            />
            <SelectField
              label="Type"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              options={EVENT_TYPE_OPTIONS}
            />
            <SelectField
              label="Domain"
              value={domainFilter}
              onChange={(e) => setDomainFilter(e.target.value)}
              options={DOMAIN_OPTIONS}
            />
            <SelectField
              label="Signal"
              value={signalFilter}
              onChange={(e) => setSignalFilter(e.target.value)}
              options={SIGNAL_OPTIONS}
            />
          </div>
          <div className="les-stream-controls">
            <Button
              variant={paused ? 'accent' : 'ghost'}
              size="sm"
              onClick={togglePause}
            >
              {paused ? 'Resume stream' : 'Pause stream'}
            </Button>
            {paused && (
              <Mono className="les-paused-label">stream paused</Mono>
            )}
          </div>
        </div>
      </div>

      <Rule />

      {/* Follow-resume banner — only visible when user has scrolled up */}
      {!following && newCount > 0 && (
        <button
          type="button"
          className="les-follow-banner"
          onClick={resumeFollow}
        >
          <Mono>
            {newCount} new below · resume
          </Mono>
        </button>
      )}

      <div
        className="les-log"
        ref={scrollRef}
        onScroll={handleScroll}
        role="log"
        aria-live="polite"
        aria-atomic="false"
        aria-label="Kernel event stream"
      >
        {filtered.length === 0 && (
          <EmptyState
            headline="No events."
            body="The stream is connected. Events appear here as the kernel acts."
          />
        )}
        {filtered.map((event) => (
          <EventRow
            key={event.id}
            event={event}
            isNew={recentIds.has(event.id)}
          />
        ))}
      </div>
    </div>
  );
}
