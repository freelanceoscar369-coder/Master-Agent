/**
 * Kernel adapter entry point.
 *
 * Reads VITE_KERNEL_ADAPTER ('mock' by default) and returns the appropriate
 * KernelClient implementation. Nothing above this module knows what is behind
 * the interface.
 *
 * Environment variables:
 *   VITE_KERNEL_ADAPTER   'mock' | 'http'  (default: 'mock')
 *   VITE_KERNEL_BASE_URL  Base URL for HTTP adapter (required when adapter='http')
 *   VITE_KERNEL_STREAM    'sse' | 'websocket' | 'poll'  (default: 'sse')
 */

import type { KernelClient } from './client';
import { createMockKernel } from './mock/mockKernel';
import { createHttpKernel } from './http/httpKernel';

export type { KernelClient };

/* ── re-export types ─────────────────────────────────────────────────────── */

export type {
  Result,
  KernelError,
  StreamStatus,
  Unsubscribe,
} from './client';

export { ok, err, notImplemented } from './client';

export type {
  // Primitives
  Iso8601,
  MissionId,
  ReceiptId,
  RuleId,
  RequestId,
  MemoryId,
  CapabilityId,
  PrincipalId,
  Money,
  Impact,
  Signal,
  // Core domain
  Mission,
  MissionState,
  JudgmentRequest,
  JudgmentAction,
  JudgmentCategory,
  JudgmentTier,
  EscalationTrigger,
  Verdict,
  Receipt,
  ReceiptPhase,
  Actor,
  StandingRule,
  RuleStatus,
  RuleProposal,
  BoundaryState,
  DomainKey,
  // Attestation & vigilance
  Attestation,
  DomainCoverage,
  // Presence
  PresenceState,
  Utterance,
  // Memory
  MemoryKind,
  MemoryRecord,
  // Capabilities
  Capability,
  CapabilityStatus,
  // Events
  KernelEvent,
  KernelEventType,
  // Misc
  Brief,
  Consequence,
  Confidence,
  SilenceDefault,
  Reversibility,
  EvidenceRef,
  Principal,
  MistakeDisclosure,
  DependencyAudit,
  Page,
  LedgerQuery,
} from './types';

/* ── re-export factories ─────────────────────────────────────────────────── */

export { createMockKernel } from './mock/mockKernel';
export type { MockOpts } from './mock/mockKernel';

export { createHttpKernel } from './http/httpKernel';
export type { HttpKernelConfig } from './http/httpKernel';

/* ── environment-driven factory ─────────────────────────────────────────── */

/**
 * Creates the Kernel client appropriate for the current environment.
 *
 * Designed to be called once at app startup. The result should be provided to
 * the rest of the app via KernelProvider.
 */
export function createKernel(): KernelClient {
  const adapter = import.meta.env.VITE_KERNEL_ADAPTER ?? 'mock';

  if (adapter === 'http') {
    const baseUrl = import.meta.env.VITE_KERNEL_BASE_URL;
    if (!baseUrl) {
      throw new Error(
        'VITE_KERNEL_BASE_URL is required when VITE_KERNEL_ADAPTER=http. ' +
        'Set it in your .env file.',
      );
    }

    const rawStream = import.meta.env.VITE_KERNEL_STREAM ?? 'sse';
    const stream = (rawStream === 'websocket' || rawStream === 'poll')
      ? rawStream
      : 'sse' as const;

    return createHttpKernel({ baseUrl, stream });
  }

  // Default to mock
  return createMockKernel();
}
