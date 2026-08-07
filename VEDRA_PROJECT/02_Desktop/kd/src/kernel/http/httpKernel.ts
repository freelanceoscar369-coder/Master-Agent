/**
 * HTTP placeholder for the Kalpavriksha Kernel (C15.0).
 *
 * Every method returns notImplemented() right now — this is intentional.
 * The real plumbing (request helper, SSE/WebSocket manager) is already wired
 * so that enabling real endpoints is a small diff: replace notImplemented()
 * with a call to request() and map the wire response.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * UNVERIFIED — these paths are proposals, not observed API.
 * Confirm against C15.0 before enabling any of them.
 * ─────────────────────────────────────────────────────────────────────────────
 */

import type {
  Attestation,
  BoundaryState,
  Brief,
  Capability,
  DependencyAudit,
  JudgmentRequest,
  KernelEvent,
  LedgerQuery,
  MemoryKind,
  MemoryRecord,
  Mission,
  MissionId,
  MistakeDisclosure,
  Page,
  PresenceState,
  Principal,
  Receipt,
  ReceiptId,
  RequestId,
  RuleId,
  RuleProposal,
  StandingRule,
  Utterance,
  Verdict,
} from '@/kernel/types';

import {
  type KernelClient,
  type KernelError,
  type Result,
  type StreamStatus,
  type Unsubscribe,
  err,
  notImplemented,
  ok,
} from '@/kernel/client';

/* ─────────────────────────────────────────────────────────────────────────────
 * UNVERIFIED endpoint proposals.
 * Confirm against C15.0 before enabling. Do not deploy with real base URL.
 * ───────────────────────────────────────────────────────────────────────────── */
const ENDPOINTS = {
  // Session
  principal: '/v1/principal',
  presence: '/v1/presence',
  // Brief
  brief: '/v1/brief',
  attestation: '/v1/attestation',
  greeting: '/v1/greeting',
  // Missions
  missions: '/v1/missions',
  mission: '/v1/missions/:id',
  missionRequest: '/v1/missions',
  // Judgment
  judgmentRequests: '/v1/judgment',
  judgmentRequest: '/v1/judgment/:id',
  submitVerdict: '/v1/judgment/:id/verdict',
  submitBatchVerdict: '/v1/judgment/batch-verdict',
  undo: '/v1/judgment/undo',
  // Ledger
  ledger: '/v1/ledger',
  receipt: '/v1/ledger/:id',
  ledgerProse: '/v1/ledger/prose',
  // Autonomy
  boundary: '/v1/boundary',
  rules: '/v1/rules',
  ruleProposals: '/v1/rules/proposals',
  grantRule: '/v1/rules/proposals/:id/grant',
  declineProposal: '/v1/rules/proposals/:id/decline',
  setRuleStatus: '/v1/rules/:id/status',
  renewRule: '/v1/rules/:id/renew',
  suspendAutonomy: '/v1/boundary/suspend',
  resumeAutonomy: '/v1/boundary/resume',
  scope: '/v1/boundary/scope',
  dependencyAudit: '/v1/audit/dependency',
  principals: '/v1/principals',
  // Memory
  memory: '/v1/memory',
  memoryRecord: '/v1/memory/:id',
  // Capabilities
  capabilities: '/v1/capabilities',
  // Disclosures
  disclosures: '/v1/disclosures',
  acknowledgeDisclosure: '/v1/disclosures/:id/acknowledge',
  // Events
  events: '/v1/events',
  recentEvents: '/v1/events/recent',
  // Streams
  sseStream: '/v1/stream/events',
  wsStream: '/v1/ws',
} as const;

/* ── HTTP client configuration ──────────────────────────────────────────── */

export interface HttpKernelConfig {
  baseUrl: string;
  stream: 'sse' | 'websocket' | 'poll';
  /** Request timeout in milliseconds. Default: 15_000. */
  timeoutMs?: number;
}

/* ── HTTP error mapping ──────────────────────────────────────────────────── */

function mapHttpStatus(status: number, body: unknown): KernelError {
  const msg = (typeof body === 'object' && body !== null && 'message' in body && typeof (body as Record<string, unknown>)['message'] === 'string')
    ? (body as Record<string, string>)['message'] ?? 'An unexpected error occurred.'
    : 'An unexpected error occurred.';

  if (status === 401) return { code: 'unauthorized', message: 'Not authorised.', retryable: false };
  if (status === 403) return { code: 'unauthorized', message: 'Access denied.', retryable: false };
  if (status === 404) return { code: 'not-found', message: msg, retryable: false };
  if (status === 409) return { code: 'conflict', message: msg, retryable: false };
  if (status === 422) return { code: 'invalid', message: msg, retryable: false };
  if (status === 503 || status === 502) return { code: 'unavailable', message: 'The Kernel is temporarily unavailable.', retryable: true };
  if (status >= 500) return { code: 'internal', message: msg, retryable: true };
  return { code: 'internal', message: msg, retryable: false };
}

/* ── subscription manager ────────────────────────────────────────────────── */

type EventListener = (e: KernelEvent) => void;
type StreamStatusListener = (s: StreamStatus) => void;
type PresenceListener = (s: PresenceState) => void;

interface SubscriptionManager {
  subscribeEvents: (fn: EventListener) => Unsubscribe;
  subscribeStreamStatus: (fn: StreamStatusListener) => Unsubscribe;
  subscribePresence: (fn: PresenceListener) => Unsubscribe;
  status: () => StreamStatus;
  dispose: () => void;
}

function createSubscriptionManager(cfg: HttpKernelConfig): SubscriptionManager {
  const eventListeners = new Set<EventListener>();
  const statusListeners = new Set<StreamStatusListener>();
  const presenceListeners = new Set<PresenceListener>();

  let streamStatus: StreamStatus = {
    connected: false,
    transport: cfg.stream === 'poll' ? 'poll' : cfg.stream === 'websocket' ? 'websocket' : 'sse',
    retries: 0,
  };
  let retryCount = 0;
  let disposed = false;

  // Reconnect with exponential backoff, capped at 30s
  function backoffMs(): number {
    return Math.min(30_000, 1_000 * Math.pow(2, retryCount));
  }

  function setStatus(connected: boolean): void {
    streamStatus = { ...streamStatus, connected, retries: retryCount };
    statusListeners.forEach((fn) => fn(streamStatus));
  }

  function emitEvent(e: KernelEvent): void {
    streamStatus = { ...streamStatus, lastEventAt: e.at };
    eventListeners.forEach((fn) => fn(e));
  }

  let eventSource: EventSource | null = null;
  let ws: WebSocket | null = null;
  let pollTimer: ReturnType<typeof setTimeout> | null = null;

  function connectSSE(): void {
    if (disposed) return;
    const url = cfg.baseUrl + ENDPOINTS.sseStream;
    eventSource = new EventSource(url, { withCredentials: true });

    eventSource.onopen = () => {
      retryCount = 0;
      setStatus(true);
    };

    eventSource.onmessage = (ev) => {
      try {
        const e = JSON.parse(ev.data) as KernelEvent;
        // MAP: wire KernelEvent shape — confirm field names against C15.0
        emitEvent(e);
      } catch {
        // Malformed event — ignore
      }
    };

    eventSource.onerror = () => {
      eventSource?.close();
      eventSource = null;
      setStatus(false);
      retryCount++;
      if (!disposed) setTimeout(connectSSE, backoffMs());
    };
  }

  function connectWebSocket(): void {
    if (disposed) return;
    const wsUrl = cfg.baseUrl.replace(/^http/, 'ws') + ENDPOINTS.wsStream;
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      retryCount = 0;
      setStatus(true);
    };

    ws.onmessage = (ev) => {
      try {
        const e = JSON.parse(ev.data as string) as KernelEvent;
        // MAP: wire KernelEvent shape — confirm field names against C15.0
        emitEvent(e);
      } catch {
        // Malformed message — ignore
      }
    };

    ws.onclose = () => {
      ws = null;
      setStatus(false);
      retryCount++;
      if (!disposed) setTimeout(connectWebSocket, backoffMs());
    };
  }

  function startPoll(): void {
    // MAP: polling uses GET /v1/events/recent — confirm pagination cursor format
    const poll = (): void => {
      // Placeholder — actual fetch + emit goes here once endpoint is confirmed
      pollTimer = setTimeout(poll, 5_000);
    };
    poll();
  }

  // Start the appropriate transport
  switch (cfg.stream) {
    case 'sse':
      connectSSE();
      break;
    case 'websocket':
      connectWebSocket();
      break;
    case 'poll':
      startPoll();
      break;
  }

  return {
    subscribeEvents: (fn) => {
      eventListeners.add(fn);
      return () => eventListeners.delete(fn);
    },
    subscribeStreamStatus: (fn) => {
      statusListeners.add(fn);
      fn(streamStatus);
      return () => statusListeners.delete(fn);
    },
    subscribePresence: (fn) => {
      presenceListeners.add(fn);
      return () => presenceListeners.delete(fn);
    },
    status: () => streamStatus,
    dispose: () => {
      disposed = true;
      eventSource?.close();
      ws?.close();
      if (pollTimer !== null) clearTimeout(pollTimer);
      eventListeners.clear();
      statusListeners.clear();
      presenceListeners.clear();
    },
  };
}

/* ── core request helper ─────────────────────────────────────────────────── */

async function request<T>(
  baseUrl: string,
  path: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<Result<T>> {
  const controller = new AbortController();
  const timerId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(baseUrl + path, {
      ...init,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        ...(init.headers ?? {}),
      },
    });

    clearTimeout(timerId);

    let body: unknown = null;
    const ct = response.headers.get('content-type') ?? '';
    if (ct.includes('application/json')) {
      body = await response.json();
    }

    if (!response.ok) {
      return err(mapHttpStatus(response.status, body));
    }

    return ok(body as T);
  } catch (e) {
    clearTimeout(timerId);
    if (e instanceof DOMException && e.name === 'AbortError') {
      return err({
        code: 'unavailable',
        message: 'Request timed out. The Kernel did not respond in time.',
        retryable: true,
      });
    }
    return err({
      code: 'unavailable',
      message: 'Could not reach the Kernel.',
      retryable: true,
    });
  }
}

/* ── factory ─────────────────────────────────────────────────────────────── */

export function createHttpKernel(cfg: HttpKernelConfig): KernelClient {
  const timeoutMs = cfg.timeoutMs ?? 15_000;
  const sub = createSubscriptionManager(cfg);

  // Convenience alias: POST to a path
  function post<T>(path: string, body?: unknown): Promise<Result<T>> {
    return request<T>(cfg.baseUrl, path, {
      method: 'POST',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }, timeoutMs);
  }

  // GET helper (unused until endpoints confirmed, kept for wire-up diff)
  function get<T>(path: string): Promise<Result<T>> {
    return request<T>(cfg.baseUrl, path, { method: 'GET' }, timeoutMs);
  }

  // Keep TypeScript happy — these will be used when wiring is enabled.
  void post;
  void get;

  return {
    kind: 'http',

    /* ── session & presence ─────────────────────────────────────────────── */

    getPrincipal(): Promise<Result<Principal>> {
      // MAP: GET /v1/principal → { id, name, role, isFounder, delegatedDomains }
      return Promise.resolve(notImplemented('getPrincipal'));
    },

    getPresence(): Promise<Result<PresenceState>> {
      // MAP: GET /v1/presence → { state: PresenceState }
      return Promise.resolve(notImplemented('getPresence'));
    },

    subscribePresence(fn: (s: PresenceState) => void): Unsubscribe {
      return sub.subscribePresence(fn);
    },

    /* ── the brief ──────────────────────────────────────────────────────── */

    getBrief(): Promise<Result<Brief>> {
      // MAP: GET /v1/brief → Brief shape; must gate headline on attestation.complete
      return Promise.resolve(notImplemented('getBrief'));
    },

    getAttestation(): Promise<Result<Attestation>> {
      // MAP: GET /v1/attestation → Attestation discriminated union
      return Promise.resolve(notImplemented('getAttestation'));
    },

    getGreeting(): Promise<Result<Utterance>> {
      // MAP: GET /v1/greeting → Utterance
      return Promise.resolve(notImplemented('getGreeting'));
    },

    /* ── missions ───────────────────────────────────────────────────────── */

    listMissions(filter?: { state?: Mission['state'] }): Promise<Result<Page<Mission>>> {
      void filter;
      // MAP: GET /v1/missions?state=running → Page<Mission>
      return Promise.resolve(notImplemented('listMissions'));
    },

    getMission(id: MissionId): Promise<Result<Mission>> {
      void id;
      // MAP: GET /v1/missions/:id → Mission
      return Promise.resolve(notImplemented('getMission'));
    },

    requestMission(brief: string): Promise<Result<Mission>> {
      void brief;
      // MAP: POST /v1/missions { brief } → Mission
      return Promise.resolve(notImplemented('requestMission'));
    },

    /* ── judgment ───────────────────────────────────────────────────────── */

    listJudgmentRequests(): Promise<Result<readonly JudgmentRequest[]>> {
      // MAP: GET /v1/judgment → JudgmentRequest[]
      return Promise.resolve(notImplemented('listJudgmentRequests'));
    },

    getJudgmentRequest(id: RequestId): Promise<Result<JudgmentRequest>> {
      void id;
      // MAP: GET /v1/judgment/:id → JudgmentRequest
      return Promise.resolve(notImplemented('getJudgmentRequest'));
    },

    submitVerdict(
      id: RequestId,
      verdict: Verdict,
    ): Promise<Result<{ readonly receiptId: ReceiptId; readonly undoWindowSeconds: number }>> {
      void id; void verdict;
      // MAP: POST /v1/judgment/:id/verdict { kind, reason?, to?, until? } → { receiptId, undoWindowSeconds }
      return Promise.resolve(notImplemented('submitVerdict'));
    },

    submitBatchVerdict(
      ids: readonly RequestId[],
      verdict: Verdict,
    ): Promise<Result<{ readonly receiptIds: readonly ReceiptId[]; readonly undoWindowSeconds: number }>> {
      void ids; void verdict;
      // MAP: POST /v1/judgment/batch-verdict { ids, verdict } → { receiptIds, undoWindowSeconds }
      return Promise.resolve(notImplemented('submitBatchVerdict'));
    },

    undo(receiptIds: readonly ReceiptId[]): Promise<Result<void>> {
      void receiptIds;
      // MAP: POST /v1/judgment/undo { receiptIds } → 204
      return Promise.resolve(notImplemented('undo'));
    },

    /* ── ledger ─────────────────────────────────────────────────────────── */

    queryLedger(q: LedgerQuery): Promise<Result<Page<Receipt>>> {
      void q;
      // MAP: GET /v1/ledger?domain=&actor=&from=&to=&flaggedOnly= → Page<Receipt>
      return Promise.resolve(notImplemented('queryLedger'));
    },

    getReceipt(id: ReceiptId): Promise<Result<Receipt>> {
      void id;
      // MAP: GET /v1/ledger/:id → Receipt
      return Promise.resolve(notImplemented('getReceipt'));
    },

    renderLedgerAsProse(q: LedgerQuery): Promise<Result<string>> {
      void q;
      // MAP: GET /v1/ledger/prose?... → { prose: string }
      return Promise.resolve(notImplemented('renderLedgerAsProse'));
    },

    /* ── autonomy / founder console ─────────────────────────────────────── */

    getBoundary(): Promise<Result<BoundaryState>> {
      // MAP: GET /v1/boundary → BoundaryState
      return Promise.resolve(notImplemented('getBoundary'));
    },

    listRules(): Promise<Result<readonly StandingRule[]>> {
      // MAP: GET /v1/rules → StandingRule[]
      return Promise.resolve(notImplemented('listRules'));
    },

    listRuleProposals(): Promise<Result<readonly RuleProposal[]>> {
      // MAP: GET /v1/rules/proposals → RuleProposal[]
      return Promise.resolve(notImplemented('listRuleProposals'));
    },

    grantRule(
      proposalId: string,
      adjustments?: Partial<Pick<StandingRule, 'cumulativeCap' | 'exclusions' | 'expiresAt'>>,
    ): Promise<Result<StandingRule>> {
      void proposalId; void adjustments;
      // MAP: POST /v1/rules/proposals/:id/grant { adjustments? } → StandingRule
      return Promise.resolve(notImplemented('grantRule'));
    },

    declineProposal(proposalId: string, reason?: string): Promise<Result<void>> {
      void proposalId; void reason;
      // MAP: POST /v1/rules/proposals/:id/decline { reason? } → 204
      return Promise.resolve(notImplemented('declineProposal'));
    },

    setRuleStatus(
      id: RuleId,
      status: 'active' | 'paused' | 'revoked',
    ): Promise<Result<StandingRule>> {
      void id; void status;
      // MAP: PATCH /v1/rules/:id/status { status } → StandingRule
      return Promise.resolve(notImplemented('setRuleStatus'));
    },

    renewRule(id: RuleId, days: number): Promise<Result<StandingRule>> {
      void id; void days;
      // MAP: POST /v1/rules/:id/renew { days } → StandingRule
      return Promise.resolve(notImplemented('renewRule'));
    },

    suspendAutonomy(): Promise<Result<void>> {
      // MAP: POST /v1/boundary/suspend → 204
      return Promise.resolve(notImplemented('suspendAutonomy'));
    },

    resumeAutonomy(): Promise<Result<void>> {
      // MAP: POST /v1/boundary/resume → 204
      return Promise.resolve(notImplemented('resumeAutonomy'));
    },

    getScope(): Promise<Result<{ readonly permitted: string; readonly forbidden: string }>> {
      // MAP: GET /v1/boundary/scope → { permitted: string, forbidden: string }
      return Promise.resolve(notImplemented('getScope'));
    },

    getDependencyAudit(year?: number): Promise<Result<DependencyAudit>> {
      void year;
      // MAP: GET /v1/audit/dependency?year=2025 → DependencyAudit
      return Promise.resolve(notImplemented('getDependencyAudit'));
    },

    listPrincipals(): Promise<Result<readonly Principal[]>> {
      // MAP: GET /v1/principals → Principal[]
      return Promise.resolve(notImplemented('listPrincipals'));
    },

    /* ── memory ─────────────────────────────────────────────────────────── */

    queryMemory(q: {
      kind?: MemoryKind;
      domain?: string;
      search?: string;
      cursor?: string;
    }): Promise<Result<Page<MemoryRecord>>> {
      void q;
      // MAP: GET /v1/memory?kind=&domain=&search=&cursor= → Page<MemoryRecord>
      return Promise.resolve(notImplemented('queryMemory'));
    },

    getMemory(id: string): Promise<Result<MemoryRecord>> {
      void id;
      // MAP: GET /v1/memory/:id → MemoryRecord
      return Promise.resolve(notImplemented('getMemory'));
    },

    /* ── capabilities ────────────────────────────────────────────────────── */

    listCapabilities(): Promise<Result<readonly Capability[]>> {
      // MAP: GET /v1/capabilities → Capability[]
      return Promise.resolve(notImplemented('listCapabilities'));
    },

    /* ── disclosures ─────────────────────────────────────────────────────── */

    listDisclosures(): Promise<Result<readonly MistakeDisclosure[]>> {
      // MAP: GET /v1/disclosures → MistakeDisclosure[]
      return Promise.resolve(notImplemented('listDisclosures'));
    },

    acknowledgeDisclosure(id: string): Promise<Result<void>> {
      void id;
      // MAP: POST /v1/disclosures/:id/acknowledge → 204
      return Promise.resolve(notImplemented('acknowledgeDisclosure'));
    },

    /* ── live event stream ───────────────────────────────────────────────── */

    subscribeEvents(fn: (e: KernelEvent) => void): Unsubscribe {
      return sub.subscribeEvents(fn);
    },

    getRecentEvents(limit?: number): Promise<Result<readonly KernelEvent[]>> {
      void limit;
      // MAP: GET /v1/events/recent?limit=50 → KernelEvent[]
      return Promise.resolve(notImplemented('getRecentEvents'));
    },

    streamStatus(): StreamStatus {
      return sub.status();
    },

    subscribeStreamStatus(fn: (s: StreamStatus) => void): Unsubscribe {
      return sub.subscribeStreamStatus(fn);
    },

    dispose(): void {
      sub.dispose();
    },
  };
}
