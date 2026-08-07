/**
 * The Kernel boundary.
 *
 * This interface is the ONLY thing the UI is allowed to know about the backend.
 * No screen imports fetch(), a URL, or a transport detail. When C15.0's real
 * contract lands, it is implemented behind this interface and nothing above it
 * changes.
 *
 * Every method returns a Result rather than throwing, because the Bible
 * requires that failure states be designed (Eng. Law IV) — an unhandled
 * rejection produces an undesigned screen.
 */

import type {
  Attestation, BoundaryState, Brief, Capability, DependencyAudit, JudgmentRequest,
  KernelEvent, LedgerQuery, MemoryRecord, MemoryKind, Mission, MissionId, MistakeDisclosure,
  Page, Principal, Receipt, ReceiptId, RequestId, RuleId, RuleProposal, StandingRule,
  Utterance, Verdict,
} from './types';

/* ─────────────────────────────── Result ─────────────────────────────── */

export type Result<T> =
  | { readonly ok: true; readonly value: T }
  | { readonly ok: false; readonly error: KernelError };

export interface KernelError {
  readonly code:
    | 'not-implemented'   // typed placeholder — endpoint not confirmed with the Kernel yet
    | 'unavailable'       // Kernel unreachable
    | 'unauthorized'
    | 'not-found'
    | 'conflict'
    | 'invalid'
    | 'suspended'         // autonomy is paused; the action was refused by design
    | 'internal';
  /** Shown to the founder. Must read as a sentence, not a stack trace. */
  readonly message: string;
  readonly detail?: string;
  readonly retryable: boolean;
}

export const ok = <T,>(value: T): Result<T> => ({ ok: true, value });
export const err = (error: KernelError): Result<never> => ({ ok: false, error });

export const notImplemented = (what: string): Result<never> =>
  err({
    code: 'not-implemented',
    message: `${what} is not wired to the Kernel yet.`,
    detail: 'This is a typed placeholder. Implement it in kernel/http/httpKernel.ts once the C15.0 contract is confirmed.',
    retryable: false,
  });

/* ──────────────────────────── subscriptions ─────────────────────────── */

export type Unsubscribe = () => void;

export interface StreamStatus {
  readonly connected: boolean;
  readonly transport: 'sse' | 'websocket' | 'poll' | 'mock';
  readonly lastEventAt?: string;
  readonly retries: number;
}

/* ────────────────────────────── the client ──────────────────────────── */

export interface KernelClient {
  readonly kind: 'mock' | 'http';

  /* — session & presence — */
  getPrincipal(): Promise<Result<Principal>>;
  getPresence(): Promise<Result<import('./types').PresenceState>>;
  subscribePresence(fn: (s: import('./types').PresenceState) => void): Unsubscribe;

  /* — the brief (Dashboard) — */
  getBrief(): Promise<Result<Brief>>;
  getAttestation(): Promise<Result<Attestation>>;
  getGreeting(): Promise<Result<Utterance>>;

  /* — missions — */
  listMissions(filter?: { state?: Mission['state'] }): Promise<Result<Page<Mission>>>;
  getMission(id: MissionId): Promise<Result<Mission>>;
  /** Founder-initiated. Optional in v0.1 — may return not-implemented. */
  requestMission(brief: string): Promise<Result<Mission>>;

  /* — judgment — */
  listJudgmentRequests(): Promise<Result<readonly JudgmentRequest[]>>;
  getJudgmentRequest(id: RequestId): Promise<Result<JudgmentRequest>>;
  submitVerdict(id: RequestId, verdict: Verdict): Promise<Result<{ readonly receiptId: ReceiptId; readonly undoWindowSeconds: number }>>;
  /** Sweep tier only. Irreversible items are rejected with `invalid`. */
  submitBatchVerdict(ids: readonly RequestId[], verdict: Verdict): Promise<Result<{ readonly receiptIds: readonly ReceiptId[]; readonly undoWindowSeconds: number }>>;
  undo(receiptIds: readonly ReceiptId[]): Promise<Result<void>>;

  /* — ledger — */
  queryLedger(q: LedgerQuery): Promise<Result<Page<Receipt>>>;
  getReceipt(id: ReceiptId): Promise<Result<Receipt>>;
  /** Eng. Law III — the system can render its state as prose. */
  renderLedgerAsProse(q: LedgerQuery): Promise<Result<string>>;

  /* — autonomy / founder console — */
  getBoundary(): Promise<Result<BoundaryState>>;
  listRules(): Promise<Result<readonly StandingRule[]>>;
  listRuleProposals(): Promise<Result<readonly RuleProposal[]>>;
  grantRule(proposalId: string, adjustments?: Partial<Pick<StandingRule, 'cumulativeCap' | 'exclusions' | 'expiresAt'>>): Promise<Result<StandingRule>>;
  declineProposal(proposalId: string, reason?: string): Promise<Result<void>>;
  setRuleStatus(id: RuleId, status: 'active' | 'paused' | 'revoked'): Promise<Result<StandingRule>>;
  renewRule(id: RuleId, days: number): Promise<Result<StandingRule>>;
  /** §10 — one gesture, no confirmation, atomic. */
  suspendAutonomy(): Promise<Result<void>>;
  resumeAutonomy(): Promise<Result<void>>;
  /** §10 Ethics 5 — one sentence, on demand. */
  getScope(): Promise<Result<{ readonly permitted: string; readonly forbidden: string }>>;
  getDependencyAudit(year?: number): Promise<Result<DependencyAudit>>;
  listPrincipals(): Promise<Result<readonly Principal[]>>;

  /* — memory — */
  queryMemory(q: { kind?: MemoryKind; domain?: string; search?: string; cursor?: string }): Promise<Result<Page<MemoryRecord>>>;
  getMemory(id: string): Promise<Result<MemoryRecord>>;

  /* — capabilities — */
  listCapabilities(): Promise<Result<readonly Capability[]>>;

  /* — disclosures — */
  listDisclosures(): Promise<Result<readonly MistakeDisclosure[]>>;
  acknowledgeDisclosure(id: string): Promise<Result<void>>;

  /* — live event stream — */
  subscribeEvents(fn: (e: KernelEvent) => void): Unsubscribe;
  getRecentEvents(limit?: number): Promise<Result<readonly KernelEvent[]>>;
  streamStatus(): StreamStatus;
  subscribeStreamStatus(fn: (s: StreamStatus) => void): Unsubscribe;

  dispose(): void;
}
