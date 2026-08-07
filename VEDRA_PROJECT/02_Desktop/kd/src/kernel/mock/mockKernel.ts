/**
 * In-memory mock implementation of KernelClient.
 *
 * Implements every method. Mutations are reflected by subsequent reads.
 * Enforces the constitutional rules — not just represents them.
 *
 * Deterministic mode: set localStorage.getItem('kalpa.seed') to a numeric
 * string to seed the PRNG, making demos repeatable.
 */

import type {
  Attestation,
  BoundaryState,
  Brief,
  Capability,
  DependencyAudit,
  JudgmentRequest,
  KernelEvent,
  KernelEventType,
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
  DomainKey,
  Signal,
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

import {
  seedAttestation,
  seedAudit,
  seedBoundary,
  seedCapabilities,
  seedDisclosure,
  seedEvents,
  seedMemory,
  seedMissions,
  seedPrincipals,
  seedProposals,
  seedReceipts,
  seedRequests,
  seedRules,
} from './fixtures';

/* ── mulberry32 PRNG ─────────────────────────────────────────────────────── */

function mulberry32(seed: number): () => number {
  let s = seed;
  return () => {
    s += 0x6d2b79f5;
    let z = s;
    z = Math.imul(z ^ (z >>> 15), z | 1);
    z ^= z + Math.imul(z ^ (z >>> 7), z | 61);
    return ((z ^ (z >>> 14)) >>> 0) / 0x100000000;
  };
}

function getRng(): () => number {
  try {
    const stored = localStorage.getItem('kalpa.seed');
    if (stored !== null) {
      const seed = parseInt(stored, 10);
      if (!isNaN(seed)) return mulberry32(seed);
    }
  } catch {
    // localStorage may not be available in SSR contexts.
  }
  return Math.random;
}

/* ── latency simulation ──────────────────────────────────────────────────── */

function delay(rng: () => number, opts: MockOpts): Promise<void> {
  const min = 120;
  const max = opts.latencyMs ?? 380;
  const ms = min + Math.floor(rng() * (max - min));
  return new Promise((r) => setTimeout(r, ms));
}

function maybeError(rng: () => number, opts: MockOpts): KernelError | null {
  const rate = opts.failRate ?? 0;
  if (rate > 0 && rng() < rate) {
    return {
      code: 'unavailable',
      message: 'The Kernel is temporarily unreachable. Try again in a moment.',
      retryable: true,
    };
  }
  return null;
}

/* ── undo ledger ─────────────────────────────────────────────────────────── */

interface UndoEntry {
  receiptIds: readonly ReceiptId[];
  expiresAt: number;
  undo: () => void;
}

/* ── event listeners ─────────────────────────────────────────────────────── */

type EventListener = (e: KernelEvent) => void;
type PresenceListener = (s: PresenceState) => void;
type StreamStatusListener = (s: StreamStatus) => void;

/* ── mock options ────────────────────────────────────────────────────────── */

export interface MockOpts {
  latencyMs?: number;
  failRate?: number;
}

/* ── id generator ────────────────────────────────────────────────────────── */

let _seq = 1_000;
function nextId(prefix: string): string {
  return `${prefix}_${(_seq++).toString()}`;
}

/* ── main factory ────────────────────────────────────────────────────────── */

export function createMockKernel(opts: MockOpts = {}): KernelClient {
  const rng = getRng();

  // Mutable in-memory state — all reads go through these.
  const missions = new Map<MissionId, Mission>(seedMissions.map((m) => [m.id, m]));
  const requests = new Map<RequestId, JudgmentRequest>(seedRequests.map((r) => [r.id, r]));
  const receipts: Receipt[] = [...seedReceipts];
  const rules = new Map<RuleId, StandingRule>(seedRules.map((r) => [r.id, r]));
  const proposals = new Map<string, RuleProposal>(seedProposals.map((p) => [p.id, p]));
  const memory = new Map<string, MemoryRecord>(seedMemory.map((m) => [m.id, m]));
  const disclosures = new Map<string, MistakeDisclosure>(seedDisclosure.map((d) => [d.id, d]));
  let boundary: BoundaryState = { ...seedBoundary };
  let attestation: Attestation = seedAttestation;
  let events: KernelEvent[] = [...seedEvents];
  const undoLedger = new Map<string, UndoEntry>();

  // Subscription registries
  const eventListeners = new Set<EventListener>();
  const presenceListeners = new Set<PresenceListener>();
  const streamStatusListeners = new Set<StreamStatusListener>();

  // Presence & stream state
  let presenceState: PresenceState = 'idle';
  let streamStatus: StreamStatus = {
    connected: true,
    transport: 'mock',
    lastEventAt: new Date().toISOString(),
    retries: 0,
  };

  /* ── internal helpers ──────────────────────────────────────────────────── */

  function emit(event: KernelEvent): void {
    events = [event, ...events].slice(0, 500);
    streamStatus = { ...streamStatus, lastEventAt: event.at };
    eventListeners.forEach((fn) => fn(event));
    streamStatusListeners.forEach((fn) => fn(streamStatus));
  }

  function makeEvent(
    type: KernelEventType,
    domain: DomainKey,
    line: string,
    signal: Signal,
    refs?: KernelEvent['refs'],
  ): KernelEvent {
    return {
      id: nextId('event'),
      type,
      at: new Date().toISOString(),
      domain,
      line,
      signal,
      refs,
    };
  }

  function setPresence(s: PresenceState): void {
    if (s === presenceState) return;
    presenceState = s;
    presenceListeners.forEach((fn) => fn(s));
    emit(makeEvent('presence.changed', 'system', `Presence: ${s}`, 'live'));
  }

  function appendReceipt(r: Receipt): void {
    receipts.push(r);
    emit(
      makeEvent(
        r.phase === 'intent' ? 'receipt.intent' : 'receipt.outcome',
        r.domain,
        r.expectedEffect,
        'done',
        { receiptId: r.id, missionId: r.missionId, requestId: r.requestId },
      ),
    );
  }

  function openRequestsExist(): boolean {
    for (const r of requests.values()) {
      if (r.tier === 'needs-you') return true;
    }
    return false;
  }

  /* ── live synthetic event stream ───────────────────────────────────────── */

  const DOMAINS: DomainKey[] = ['vendors', 'spend', 'hiring', 'operations', 'system'];

  function pickDomain(): DomainKey {
    return DOMAINS[Math.floor(rng() * DOMAINS.length)] ?? 'system';
  }

  const syntheticEventTemplates: Array<() => KernelEvent | null> = [
    // mission progress tick
    () => {
      const running = [...missions.values()].filter((m) => m.state === 'running' && m.progress !== undefined);
      if (running.length === 0) return null;
      const m = running[Math.floor(rng() * running.length)];
      if (!m) return null;
      const newProgress = Math.min(1, (m.progress ?? 0) + rng() * 0.08);
      missions.set(m.id, { ...m, progress: Math.round(newProgress * 100) / 100 });
      return makeEvent('mission.progress', m.domain, `${m.name} — ${Math.round(newProgress * 100)}% complete.`, 'live', { missionId: m.id });
    },
    // receipt write
    () => {
      const domain = pickDomain();
      return makeEvent('receipt.outcome', domain, `Routine action completed in ${domain}.`, 'done');
    },
    // rule firing
    () => {
      const active = [...rules.values()].filter((r) => r.status === 'active' || r.status === 'trial');
      if (active.length === 0) return null;
      const rule = active[Math.floor(rng() * active.length)];
      if (!rule) return null;
      return makeEvent('rule.fired', rule.domain, `Standing rule fired: ${rule.statement.slice(0, 60)}…`, 'done', { ruleId: rule.id });
    },
    // occasional judgment opened
    () => {
      if (rng() > 0.15) return null;
      return makeEvent('judgment.opened', pickDomain(), 'A new judgment request has entered the queue.', 'needs-you');
    },
  ];

  let syntheticTimerId: ReturnType<typeof setTimeout> | null = null;

  function scheduleSynthetic(): void {
    const delay_ms = 2500 + Math.floor(rng() * 3500); // 2.5–6s
    syntheticTimerId = setTimeout(() => {
      if (eventListeners.size > 0) {
        const template = syntheticEventTemplates[Math.floor(rng() * syntheticEventTemplates.length)];
        const event = template?.();
        if (event) emit(event);
      }
      scheduleSynthetic();
    }, delay_ms);
  }

  /* ── presence cycling ──────────────────────────────────────────────────── */

  const PRESENCE_SEQUENCE: PresenceState[] = ['idle', 'thinking', 'speaking', 'idle'];
  let presenceIdx = 0;
  let presenceTimerId: ReturnType<typeof setTimeout> | null = null;

  function schedulePresenceTick(): void {
    const durations: Record<PresenceState, [number, number]> = {
      idle: [8_000, 15_000],
      thinking: [2_000, 5_000],
      speaking: [3_000, 8_000],
      awaiting: [5_000, 10_000],
    };

    const current = openRequestsExist() ? 'awaiting' : (PRESENCE_SEQUENCE[presenceIdx % PRESENCE_SEQUENCE.length] ?? 'idle');
    setPresence(current);
    presenceIdx++;

    const range = durations[current] ?? [5_000, 10_000];
    const [lo, hi] = range;
    const ms = lo + Math.floor(rng() * (hi - lo));
    presenceTimerId = setTimeout(schedulePresenceTick, ms);
  }

  /* ── start the streams ─────────────────────────────────────────────────── */

  scheduleSynthetic();
  schedulePresenceTick();

  /* ── dispose ───────────────────────────────────────────────────────────── */

  function dispose(): void {
    if (syntheticTimerId !== null) clearTimeout(syntheticTimerId);
    if (presenceTimerId !== null) clearTimeout(presenceTimerId);
    eventListeners.clear();
    presenceListeners.clear();
    streamStatusListeners.clear();
  }

  /* ── paging helper ──────────────────────────────────────────────────────── */

  function paginate<T>(items: T[], cursor?: string, limit = 50): Page<T> {
    const start = cursor ? parseInt(cursor, 10) : 0;
    const slice = items.slice(start, start + limit);
    const nextCursor = start + limit < items.length ? String(start + limit) : undefined;
    return {
      items: slice,
      ...(nextCursor !== undefined && { cursor: nextCursor }),
      total: items.length,
    };
  }

  /* ── wrap with latency/fail simulation ─────────────────────────────────── */

  async function sim<T>(fn: () => Result<T>): Promise<Result<T>> {
    await delay(rng, opts);
    const e = maybeError(rng, opts);
    if (e) return { ok: false, error: e };
    return fn();
  }

  /* ═════════════════════════════════════════════════════════════════════════
   * CLIENT IMPLEMENTATION
   * ═════════════════════════════════════════════════════════════════════════ */

  return {
    kind: 'mock',

    /* ── session & presence ─────────────────────────────────────────────── */

    async getPrincipal() {
      return sim(() => {
        const founder = seedPrincipals.find((p) => p.isFounder);
        if (!founder) return err({ code: 'not-found', message: 'No founder principal configured.', retryable: false });
        return ok(founder);
      });
    },

    async getPresence() {
      return sim(() => ok(presenceState));
    },

    subscribePresence(fn: (s: PresenceState) => void): Unsubscribe {
      presenceListeners.add(fn);
      fn(presenceState);
      return () => presenceListeners.delete(fn);
    },

    /* ── the brief ──────────────────────────────────────────────────────── */

    async getBrief() {
      return sim(() => {
        const currentAttestation = attestation;
        const openReqs = [...requests.values()].filter((r) => r.tier === 'needs-you');
        const flaggedR = receipts.filter((r) => r.flagged !== undefined);
        const activeDisclosures = [...disclosures.values()].filter((d) => !d.acknowledged);

        let headlineText: string;
        if (!currentAttestation.complete) {
          // Must name the gap — cannot claim calm.
          const gapDomains = currentAttestation.gaps.map((g) => g.domain).join(', ');
          headlineText = `Attestation incomplete — ${gapDomains} ${currentAttestation.gaps.length === 1 ? 'has' : 'have'} not been verified. Showing available information.`;
        } else if (openReqs.length > 0) {
          headlineText = `${openReqs.length} ${openReqs.length === 1 ? 'item needs' : 'items need'} your attention. Everything else is handled.`;
        } else {
          headlineText = 'Everything is handled. Nothing needs you right now.';
        }

        const headline: Utterance = {
          id: nextId('utterance'),
          text: headlineText,
          boundValues: [],
          register: 'brief',
          at: new Date().toISOString(),
        };

        const brief: Brief = {
          since: new Date(Date.now() - 24 * 3600 * 1000).toISOString(),
          attestation: currentAttestation,
          handledCount: receipts.filter((r) => r.phase === 'outcome' && r.result === 'ok').length,
          runningCount: [...missions.values()].filter((m) => m.state === 'running').length,
          openRequests: openReqs,
          flaggedReceipts: flaggedR,
          disclosures: activeDisclosures,
          headline,
        };

        return ok(brief);
      });
    },

    async getAttestation() {
      return sim(() => ok(attestation));
    },

    async getGreeting() {
      return sim(() => {
        const hour = new Date().getHours();
        const salutation = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
        const openCount = [...requests.values()].filter((r) => r.tier === 'needs-you').length;
        const text = openCount > 0
          ? `${salutation}, Onkar. ${openCount} ${openCount === 1 ? 'item needs' : 'items need'} you — the Datastack deadline is closest.`
          : `${salutation}, Onkar. Everything is in order.`;

        return ok<Utterance>({
          id: nextId('utterance'),
          text,
          boundValues: [],
          register: 'greeting',
          at: new Date().toISOString(),
        });
      });
    },

    /* ── missions ───────────────────────────────────────────────────────── */

    async listMissions(filter) {
      return sim(() => {
        let items = [...missions.values()];
        if (filter?.state !== undefined) {
          const s = filter.state;
          items = items.filter((m) => m.state === s);
        }
        return ok(paginate(items));
      });
    },

    async getMission(id: MissionId) {
      return sim(() => {
        const m = missions.get(id);
        if (!m) return err({ code: 'not-found', message: `Mission ${id} not found.`, retryable: false });
        return ok(m);
      });
    },

    async requestMission(_brief: string) {
      return notImplemented('Founder-initiated missions');
    },

    /* ── judgment ───────────────────────────────────────────────────────── */

    async listJudgmentRequests() {
      return sim(() => ok([...requests.values()]));
    },

    async getJudgmentRequest(id: RequestId) {
      return sim(() => {
        const r = requests.get(id);
        if (!r) return err({ code: 'not-found', message: `Request ${id} not found.`, retryable: false });
        return ok(r);
      });
    },

    async submitVerdict(id: RequestId, verdict: Verdict) {
      setPresence('thinking');
      await delay(rng, { latencyMs: 600 });

      const req = requests.get(id);
      if (!req) {
        setPresence('idle');
        return err({ code: 'not-found', message: `Request ${id} not found.`, retryable: false });
      }

      if (boundary.suspended) {
        setPresence('idle');
        return err({
          code: 'suspended',
          message: 'Autonomy is suspended. No actions are being taken.',
          retryable: false,
        });
      }

      // Determine undo window
      const rev = req.consequence.reversibility;
      let undoWindowSeconds: number;
      if (rev.kind === 'irreversible') {
        undoWindowSeconds = 0;
      } else if (req.tier === 'needs-you' ? true : false) {
        undoWindowSeconds = 30;
      } else {
        undoWindowSeconds = 60;
      }

      const receiptId = nextId('receipt');
      const now = new Date().toISOString();

      const intentReceipt: Receipt = {
        id: nextId('receipt'),
        phase: 'intent',
        intentId: receiptId,
        at: now,
        actor: { kind: 'founder' },
        actionType: `judgment.verdict.${verdict.kind}`,
        reversibility: req.consequence.reversibility,
        expectedEffect: req.consequence.whatChanges,
        domain: req.domain,
        requestId: id,
        missionId: req.missionId,
      };

      const outcomeReceipt: Receipt = {
        id: receiptId,
        phase: 'outcome',
        intentId: receiptId,
        at: now,
        actor: { kind: 'founder' },
        actionType: `judgment.verdict.${verdict.kind}`,
        reversibility: req.consequence.reversibility,
        expectedEffect: req.consequence.whatChanges,
        actualEffect: `Verdict submitted: ${verdict.kind}.`,
        domain: req.domain,
        requestId: id,
        missionId: req.missionId,
        result: 'ok',
      };

      appendReceipt(intentReceipt);
      appendReceipt(outcomeReceipt);

      // Remove from open requests
      requests.delete(id);

      // Update boundary ratio (small bump for founder decision)
      boundary = {
        ...boundary,
        autonomyRatio: Math.min(0.95, boundary.autonomyRatio + 0.002),
      };

      emit(makeEvent(
        'judgment.resolved',
        req.domain,
        `Judgment resolved: ${req.title} — ${verdict.kind}.`,
        'done',
        { requestId: id, receiptId, missionId: req.missionId },
      ));

      // Register undo entry if reversible
      if (undoWindowSeconds > 0) {
        undoLedger.set(receiptId, {
          receiptIds: [receiptId, intentReceipt.id],
          expiresAt: Date.now() + undoWindowSeconds * 1000,
          undo: () => {
            // Restore the request
            requests.set(id, req);
            // Remove outcome receipts (only practical in mock — real system would compensate)
            const idx = receipts.findIndex((r) => r.id === receiptId);
            if (idx >= 0) receipts.splice(idx, 1);
          },
        });
      }

      setPresence(openRequestsExist() ? 'awaiting' : 'idle');

      return ok({ receiptId, undoWindowSeconds });
    },

    async submitBatchVerdict(ids: readonly RequestId[], verdict: Verdict) {
      // Constitutional enforcement: reject if ANY item is needs-you or irreversible
      for (const id of ids) {
        const req = requests.get(id);
        if (!req) continue;

        if (req.tier === 'needs-you') {
          return err({
            code: 'invalid',
            message: `Batch verdict rejected — "${req.title}" is a needs-you item and must be decided individually.`,
            detail: `Request ${id} has tier 'needs-you'. Batch verdicts are for sweep-tier items only.`,
            retryable: false,
          });
        }

        if (req.consequence.reversibility.kind === 'irreversible') {
          return err({
            code: 'invalid',
            message: `Batch verdict rejected — "${req.title}" has irreversible consequence and cannot be batch-approved.`,
            detail: `Request ${id} has irreversible consequence. Each irreversible action must be individually confirmed.`,
            retryable: false,
          });
        }
      }

      if (boundary.suspended) {
        return err({
          code: 'suspended',
          message: 'Autonomy is suspended. No batch actions are being taken.',
          retryable: false,
        });
      }

      setPresence('thinking');
      await delay(rng, { latencyMs: 800 });

      const receiptIds: ReceiptId[] = [];
      const now = new Date().toISOString();

      for (const id of ids) {
        const req = requests.get(id);
        if (!req) continue;

        const receiptId = nextId('receipt');
        receiptIds.push(receiptId);

        appendReceipt({
          id: receiptId,
          phase: 'outcome',
          intentId: receiptId,
          at: now,
          actor: { kind: 'founder' },
          actionType: `judgment.batch-verdict.${verdict.kind}`,
          reversibility: req.consequence.reversibility,
          expectedEffect: req.consequence.whatChanges,
          actualEffect: `Batch verdict: ${verdict.kind}.`,
          domain: req.domain,
          requestId: id,
          missionId: req.missionId,
          result: 'ok',
        });

        requests.delete(id);
      }

      emit(makeEvent(
        'judgment.resolved',
        'spend',
        `Batch verdict applied to ${ids.length} sweep items — ${verdict.kind}.`,
        'done',
      ));

      setPresence(openRequestsExist() ? 'awaiting' : 'idle');

      // Batch window is 60s
      const undoWindowSeconds = 60;
      const entry: UndoEntry = {
        receiptIds,
        expiresAt: Date.now() + undoWindowSeconds * 1000,
        undo: () => {
          // Restore all requests
          for (const id of ids) {
            const req = requests.get(id);
            if (req) continue; // already exists somehow
            const orig = seedRequests.find((r) => r.id === id);
            if (orig) requests.set(id, orig);
          }
        },
      };

      const batchUndoKey = nextId('batch_undo');
      undoLedger.set(batchUndoKey, entry);

      return ok({ receiptIds, undoWindowSeconds });
    },

    async undo(receiptIds: readonly ReceiptId[]) {
      await delay(rng, opts);

      for (const id of receiptIds) {
        const entry = undoLedger.get(id);
        if (!entry) {
          return err({
            code: 'not-found',
            message: `No undo entry found for receipt ${id}.`,
            retryable: false,
          });
        }
        if (Date.now() > entry.expiresAt) {
          return err({
            code: 'invalid',
            message: 'The undo window has closed — this action can no longer be reversed.',
            retryable: false,
          });
        }
        entry.undo();
        undoLedger.delete(id);
        emit(makeEvent('receipt.outcome', 'system', `Undo applied for receipt ${id}.`, 'live'));
      }

      return ok(undefined);
    },

    /* ── ledger ─────────────────────────────────────────────────────────── */

    async queryLedger(q: LedgerQuery) {
      return sim(() => {
        let items = [...receipts];

        if (q.domain !== undefined) {
          const d = q.domain;
          items = items.filter((r) => r.domain === d);
        }
        if (q.actor !== undefined) {
          const a = q.actor;
          items = items.filter((r) => r.actor.kind === a);
        }
        if (q.from !== undefined) {
          const from = q.from;
          items = items.filter((r) => r.at >= from);
        }
        if (q.to !== undefined) {
          const to = q.to;
          items = items.filter((r) => r.at <= to);
        }
        if (q.flaggedOnly === true) {
          items = items.filter((r) => r.flagged !== undefined);
        }
        if (q.search !== undefined) {
          const s = q.search.toLowerCase();
          items = items.filter(
            (r) =>
              r.expectedEffect.toLowerCase().includes(s) ||
              (r.actualEffect?.toLowerCase().includes(s) ?? false) ||
              r.actionType.toLowerCase().includes(s),
          );
        }

        // Sort newest first
        items.sort((a, b) => (a.at < b.at ? 1 : -1));

        return ok(paginate(items, q.cursor, q.limit));
      });
    },

    async getReceipt(id: ReceiptId) {
      return sim(() => {
        const r = receipts.find((rec) => rec.id === id);
        if (!r) return err({ code: 'not-found', message: `Receipt ${id} not found.`, retryable: false });
        return ok(r);
      });
    },

    async renderLedgerAsProse(q: LedgerQuery) {
      return sim(() => {
        const domain = q.domain ? ` in ${q.domain}` : '';
        const actor = q.actor ? ` by ${q.actor}` : '';
        const count = receipts.filter((r) => {
          if (q.domain !== undefined && r.domain !== q.domain) return false;
          if (q.actor !== undefined && r.actor.kind !== q.actor) return false;
          return true;
        }).length;

        const prose =
          `Over the requested window${domain}${actor}, the Kernel logged ${count} actions. ` +
          `${receipts.filter((r) => r.flagged !== undefined).length} ${receipts.filter((r) => r.flagged !== undefined).length === 1 ? 'was' : 'were'} flagged for founder awareness. ` +
          `The autonomy ratio is currently ${Math.round(boundary.autonomyRatio * 100)}%.`;

        return ok(prose);
      });
    },

    /* ── autonomy / founder console ─────────────────────────────────────── */

    async getBoundary() {
      return sim(() => ok(boundary));
    },

    async listRules() {
      return sim(() => ok([...rules.values()]));
    },

    async listRuleProposals() {
      return sim(() => ok([...proposals.values()]));
    },

    async grantRule(
      proposalId: string,
      adjustments?: Partial<Pick<StandingRule, 'cumulativeCap' | 'exclusions' | 'expiresAt'>>,
    ) {
      setPresence('thinking');
      await delay(rng, opts);

      const proposal = proposals.get(proposalId);
      if (!proposal) {
        setPresence('idle');
        return err({ code: 'not-found', message: `Proposal ${proposalId} not found.`, retryable: false });
      }

      const newRule: StandingRule = {
        id: nextId('rule'),
        statement: proposal.draft.statement,
        domain: proposal.draft.domain,
        trigger: proposal.draft.trigger,
        cumulativeCap: adjustments?.cumulativeCap ?? proposal.draft.cumulativeCap,
        exclusions: adjustments?.exclusions ?? proposal.draft.exclusions,
        expiresAt: adjustments?.expiresAt ?? proposal.draft.expiresAt,
        status: 'trial',
        grantedAt: new Date().toISOString(),
        firingCount: 0,
      };

      rules.set(newRule.id, newRule);
      proposals.delete(proposalId);

      // Bump autonomy ratio slightly
      boundary = {
        ...boundary,
        autonomyRatio: Math.min(0.95, boundary.autonomyRatio + 0.015),
        activeRuleCount: boundary.activeRuleCount + 1,
      };

      emit(makeEvent(
        'rule.granted',
        newRule.domain,
        `Rule granted: ${newRule.statement.slice(0, 60)}…`,
        'live',
        { ruleId: newRule.id },
      ));
      emit(makeEvent('boundary.changed', 'system', `Autonomy ratio updated to ${Math.round(boundary.autonomyRatio * 100)}%.`, 'live'));

      setPresence('idle');
      return ok(newRule);
    },

    async declineProposal(proposalId: string, _reason?: string) {
      await delay(rng, opts);
      if (!proposals.has(proposalId)) {
        return err({ code: 'not-found', message: `Proposal ${proposalId} not found.`, retryable: false });
      }
      proposals.delete(proposalId);
      return ok(undefined);
    },

    async setRuleStatus(id: RuleId, status: 'active' | 'paused' | 'revoked') {
      await delay(rng, opts);
      const rule = rules.get(id);
      if (!rule) return err({ code: 'not-found', message: `Rule ${id} not found.`, retryable: false });

      const updated: StandingRule = { ...rule, status };
      rules.set(id, updated);

      if (status === 'paused' || status === 'revoked') {
        boundary = {
          ...boundary,
          activeRuleCount: Math.max(0, boundary.activeRuleCount - 1),
        };
      } else if (status === 'active' && rule.status !== 'active') {
        boundary = {
          ...boundary,
          activeRuleCount: boundary.activeRuleCount + 1,
        };
      }

      return ok(updated);
    },

    async renewRule(id: RuleId, days: number) {
      await delay(rng, opts);
      const rule = rules.get(id);
      if (!rule) return err({ code: 'not-found', message: `Rule ${id} not found.`, retryable: false });

      const updated: StandingRule = {
        ...rule,
        expiresAt: new Date(Date.now() + days * 86400 * 1000).toISOString(),
        lastReviewedAt: new Date().toISOString(),
      };
      rules.set(id, updated);
      return ok(updated);
    },

    async suspendAutonomy() {
      await delay(rng, opts);
      boundary = { ...boundary, suspended: true };
      emit(makeEvent('boundary.changed', 'system', 'Autonomy suspended by founder — all rule-covered actions paused.', 'risk'));
      setPresence('idle');
      return ok(undefined);
    },

    async resumeAutonomy() {
      await delay(rng, opts);
      boundary = { ...boundary, suspended: false };
      emit(makeEvent('boundary.changed', 'system', 'Autonomy resumed — standing rules are active again.', 'live'));
      return ok(undefined);
    },

    async getScope() {
      return sim(() =>
        ok({
          permitted:
            'Approve tooling renewals and contractor invoices matching a signed SOW. Schedule candidate screenings. Generate reports. Triage alerts. Route large invoices to Priya.',
          forbidden:
            'Any action touching customer data. New vendor relationships. Spend in the last 5 days of a quarter. Hirings above Staff Engineer level. Executing contracts above ₹2,00,000 without CFO sign-off.',
        }),
      );
    },

    async getDependencyAudit(_year?: number) {
      return sim(() => ok(seedAudit));
    },

    async listPrincipals() {
      return sim(() => ok(seedPrincipals));
    },

    /* ── memory ─────────────────────────────────────────────────────────── */

    async queryMemory(q: { kind?: MemoryKind; domain?: string; search?: string; cursor?: string }) {
      return sim(() => {
        let items = [...memory.values()];

        if (q.kind !== undefined) {
          const k = q.kind;
          items = items.filter((m) => m.kind === k);
        }
        if (q.domain !== undefined) {
          const d = q.domain;
          items = items.filter((m) => m.domain === d);
        }
        if (q.search !== undefined) {
          const s = q.search.toLowerCase();
          items = items.filter(
            (m) =>
              m.subject.toLowerCase().includes(s) ||
              m.content.toLowerCase().includes(s),
          );
        }

        return ok(paginate(items, q.cursor));
      });
    },

    async getMemory(id: string) {
      return sim(() => {
        const m = memory.get(id);
        if (!m) return err({ code: 'not-found', message: `Memory ${id} not found.`, retryable: false });
        return ok(m);
      });
    },

    /* ── capabilities ────────────────────────────────────────────────────── */

    async listCapabilities() {
      return sim(() => ok(seedCapabilities));
    },

    /* ── disclosures ─────────────────────────────────────────────────────── */

    async listDisclosures() {
      return sim(() => ok([...disclosures.values()]));
    },

    async acknowledgeDisclosure(id: string) {
      await delay(rng, opts);
      const d = disclosures.get(id);
      if (!d) return err({ code: 'not-found', message: `Disclosure ${id} not found.`, retryable: false });
      disclosures.set(id, { ...d, acknowledged: true });
      return ok(undefined);
    },

    /* ── live event stream ───────────────────────────────────────────────── */

    subscribeEvents(fn: (e: KernelEvent) => void): Unsubscribe {
      eventListeners.add(fn);
      return () => eventListeners.delete(fn);
    },

    async getRecentEvents(limit = 50) {
      return sim(() => ok(events.slice(0, limit)));
    },

    streamStatus() {
      return streamStatus;
    },

    subscribeStreamStatus(fn: (s: StreamStatus) => void): Unsubscribe {
      streamStatusListeners.add(fn);
      fn(streamStatus);
      return () => streamStatusListeners.delete(fn);
    },

    dispose,
  };
}
