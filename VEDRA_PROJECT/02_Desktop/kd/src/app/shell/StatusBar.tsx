/**
 * StatusBar — 32px mono bar at the bottom of the shell.
 *
 * Always shows, left to right:
 *   stream status (word + colour, never colour alone)
 *   autonomy ratio + active rule count (from getBoundary())
 *   local clock (ticks each second)
 *   kernel adapter name (mock / http — always visible, never hidden)
 *
 * ADAPTER VISIBILITY: The adapter name must be visible at all times so
 * nobody demos mock data thinking it is real production data.
 *
 * When boundary.suspended: the entire bar turns --signal-risk and reads
 * "AUTONOMY PAUSED" alongside the normal fields.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { useKernel } from '@/kernel/KernelProvider';
import { useAsync, useStreamStatus } from '@/kernel/hooks';
import type { StreamStatus } from '@/kernel/client';
import styles from './StatusBar.module.css';

/* ── stream status ────────────────────────────────────────────────────────── */

interface StreamLabelProps {
  status: StreamStatus;
}

function StreamLabel({ status }: StreamLabelProps): React.ReactElement {
  const word = status.connected ? 'connected' : 'disconnected';
  const cls = status.connected ? styles.signalLive : styles.signalRisk;
  return (
    <span className={cls}>
      {/* State = colour AND word — never colour alone */}
      {word}
    </span>
  );
}

/* ── local clock ──────────────────────────────────────────────────────────── */

function LocalClock(): React.ReactElement {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const hh = String(now.getHours()).padStart(2, '0');
  const mm = String(now.getMinutes()).padStart(2, '0');
  const ss = String(now.getSeconds()).padStart(2, '0');

  return <span className={styles.segment}>{hh}:{mm}:{ss}</span>;
}

/* ── StatusBar ────────────────────────────────────────────────────────────── */

export function StatusBar(): React.ReactElement {
  const kernel = useKernel();
  const streamStatus = useStreamStatus();

  const { data: boundary } = useAsync(
    useCallback(() => kernel.getBoundary(), [kernel]),
    [kernel],
  );

  const autonomyPct =
    boundary !== undefined
      ? `${Math.round(boundary.autonomyRatio * 100)}%`
      : '—';

  const activeRules =
    boundary !== undefined
      ? String(boundary.activeRuleCount)
      : '—';

  const suspended = boundary?.suspended === true;

  return (
    <footer
      className={`${styles.root} ${suspended ? styles.suspended : ''}`}
      aria-label="Status bar"
    >
      {suspended && (
        <span className={styles.suspendedLabel}>AUTONOMY PAUSED</span>
      )}

      <span className={styles.segment}>
        stream{' '}
        <StreamLabel status={streamStatus} />
      </span>

      <span className={styles.divider} aria-hidden="true">·</span>

      <span className={styles.segment}>
        autonomy{' '}
        <span className={suspended ? styles.signalRisk : styles.signalLive}>
          {autonomyPct}
        </span>
        {' '}·{' '}
        <span className={styles.plain}>{activeRules} rules</span>
      </span>

      <span className={styles.divider} aria-hidden="true">·</span>

      <LocalClock />

      <span className={styles.divider} aria-hidden="true">·</span>

      {/* Adapter name — always visible so nobody demos mock data believing it is real */}
      <span className={`${styles.segment} ${kernel.kind === 'mock' ? styles.adapterMock : styles.adapterHttp}`}>
        {kernel.kind}
      </span>
    </footer>
  );
}
