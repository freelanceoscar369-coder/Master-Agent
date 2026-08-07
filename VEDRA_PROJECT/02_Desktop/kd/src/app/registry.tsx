/**
 * Route registry — the single route table instance for the application.
 *
 * Every route has a Bible §12 gate justification. Group order is:
 *   founder → operate → inspect
 *
 * Component imports are lazy so each section is a separate chunk. If a
 * feature file does not exist yet that is expected — another agent owns
 * src/features/**. TypeScript will surface the missing module only at build time.
 */

import { lazy } from 'react';
import type { RouteRegistry } from './routes';

const Dashboard = lazy(() =>
  import('@/features/dashboard/Dashboard').then((m) => ({ default: m.Dashboard })),
);

const FounderConsole = lazy(() =>
  import('@/features/founder/FounderConsole').then((m) => ({ default: m.FounderConsole })),
);

const MissionCenter = lazy(() =>
  import('@/features/missions/MissionCenter').then((m) => ({ default: m.MissionCenter })),
);

const LiveEventStream = lazy(() =>
  import('@/features/events/LiveEventStream').then((m) => ({ default: m.LiveEventStream })),
);

const LedgerExplorer = lazy(() =>
  import('@/features/ledger/LedgerExplorer').then((m) => ({ default: m.LedgerExplorer })),
);

const MemoryExplorer = lazy(() =>
  import('@/features/memory/MemoryExplorer').then((m) => ({ default: m.MemoryExplorer })),
);

const CapabilityLibrary = lazy(() =>
  import('@/features/capabilities/CapabilityLibrary').then((m) => ({ default: m.CapabilityLibrary })),
);

export const REGISTRY: RouteRegistry = [
  {
    path: '/',
    index: '01',
    label: 'Dashboard',
    hint: 'Overview of open judgment, running missions, and the latest attestation.',
    gate: 'explains',
    group: 'founder',
    Component: Dashboard,
  },
  {
    path: '/console',
    index: '02',
    label: 'Founder Console',
    hint: 'Open judgment requests ranked by urgency. Your direct line to the AI.',
    gate: 'judgment',
    group: 'founder',
    Component: FounderConsole,
    countKey: 'openRequests',
  },
  {
    path: '/missions',
    index: '03',
    label: 'Mission Center',
    hint: 'All missions in flight — queued, running, held, and completed.',
    gate: 'explains',
    group: 'operate',
    Component: MissionCenter,
  },
  {
    path: '/events',
    index: '04',
    label: 'Live Events',
    hint: 'Real-time stream of every kernel event as it happens.',
    gate: 'explains',
    group: 'operate',
    Component: LiveEventStream,
  },
  {
    path: '/ledger',
    index: '05',
    label: 'Ledger Explorer',
    hint: 'Append-only receipt ledger — every action the AI has ever taken.',
    gate: 'explains',
    group: 'inspect',
    Component: LedgerExplorer,
  },
  {
    path: '/memory',
    index: '06',
    label: 'Memory Explorer',
    hint: 'Browse episodic, decisional, and semantic memory records.',
    gate: 'explains',
    group: 'inspect',
    Component: MemoryExplorer,
  },
  {
    path: '/capabilities',
    index: '07',
    label: 'Capability Library',
    hint: 'All registered capabilities, their reversibility, and execution status.',
    gate: 'operator',
    group: 'inspect',
    Component: CapabilityLibrary,
  },
] as const;
