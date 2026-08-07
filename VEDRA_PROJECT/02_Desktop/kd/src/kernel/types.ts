/**
 * Kalpavriksha domain types.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * PROVENANCE WARNING
 * These types are derived from THE KALPAVRIKSHA EXPERIENCE BIBLE v1.0 and the
 * MasterAgent Architectural Requirements — NOT from the C15.0 Kernel's actual
 * wire format, which has not been inspected. They are the shape the UI needs.
 *
 * When the Kernel's real contract is available, DO NOT edit screens. Edit
 * `kernel/http/httpKernel.ts` and map the wire format onto these types there.
 * This file is the anti-corruption layer's vocabulary.
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * Several Bible invariants are enforced structurally here rather than by
 * convention, because conventions get worked around:
 *   · Principle VI  — a JudgmentRequest cannot exist without a full Consequence
 *                     quartet. Missing any field is a compile error.
 *   · Principle VII — every JudgmentRequest carries a SilenceDefault.
 *   · §10 Confidence — confidence is a three-level union. A number cannot be
 *                     assigned to it.
 *   · §1 Vigilance  — the calm state is a discriminated union member that only
 *                     exists when attestation is complete.
 *   · Eng. Law II   — reversibility is a required, exhaustive classification.
 */

/* ───────────────────────────── primitives ───────────────────────────── */

export type Iso8601 = string;
export type MissionId = string;
export type ReceiptId = string;
export type RuleId = string;
export type RequestId = string;
export type MemoryId = string;
export type CapabilityId = string;
export type PrincipalId = string;

/** Minor units (paise). Never a float — money is integer arithmetic. */
export interface Money {
  readonly currency: 'INR' | 'USD' | 'EUR' | 'GBP';
  readonly minor: number;
}

export type Impact = 'low' | 'medium' | 'high';

/** §2 Colour is a semantic. These are the only four signals in the system. */
export type Signal = 'live' | 'needs-you' | 'done' | 'risk';

/* ─────────────────────── reversibility (Eng. Law II) ─────────────────── */

export type Reversibility =
  | { readonly kind: 'reversible'; readonly compensatingAction: string }
  | { readonly kind: 'reversible-until'; readonly until: Iso8601; readonly compensatingAction: string }
  | { readonly kind: 'irreversible'; readonly reason: string };

/* ───────────────────── consequence quartet (Principle VI) ────────────── */

/**
 * The four questions every request for judgment must answer before asking for
 * a verdict. All four fields are required — there is deliberately no partial
 * form of this type.
 */
export interface Consequence {
  readonly whatChanges: string;
  readonly cost: Money | { readonly kind: 'non-monetary'; readonly description: string };
  readonly ifYouDoNothing: string;
  readonly reversibility: Reversibility;
}

/** §10 — never a percentage. Three levels, three fixed phrasings. */
export type Confidence =
  | { readonly level: 'recommend'; readonly phrasing: string }
  | { readonly level: 'lean'; readonly phrasing: string }
  | { readonly level: 'insufficient'; readonly phrasing: string; readonly whatWouldRaiseIt: string };

/** §5 — every open request declares what happens if the founder never replies. */
export interface SilenceDefault {
  readonly action: string;
  readonly firesAt: Iso8601;
  /** Re-verified immediately before firing; a stale default must not execute. */
  readonly staleIfFactsChange: boolean;
}

/* ───────────────────────────── evidence ─────────────────────────────── */

export interface EvidenceRef {
  readonly id: string;
  readonly label: string;
  readonly source: string;
  readonly observedAt: Iso8601;
  readonly uri?: string;
}

/* ───────────────────────────── missions ─────────────────────────────── */

export type MissionState = 'queued' | 'running' | 'held' | 'completed' | 'failed';

export interface Mission {
  readonly id: MissionId;
  readonly name: string;
  /** One line, in the founder's terms. §5 Mission summaries. */
  readonly summary: string;
  readonly state: MissionState;
  readonly impact: Impact;
  readonly startedAt: Iso8601;
  readonly endedAt?: Iso8601;
  /** 0–1. Present only while running. */
  readonly progress?: number;
  readonly etaSeconds?: number;
  readonly domain: DomainKey;
  readonly receiptIds: readonly ReceiptId[];
  readonly heldOnRequestId?: RequestId;
  readonly failure?: { readonly whatIsAtRisk: string; readonly nextAttempt: string };
}

/* ──────────────────────── judgment requests ─────────────────────────── */

export type EscalationTrigger = 'novel' | 'irreversible' | 'excluded-by-rule';
export type JudgmentTier = 'needs-you' | 'sweep';
export type JudgmentCategory = 'permission' | 'financial' | 'strategic' | 'operational';

export interface JudgmentRequest {
  readonly id: RequestId;
  readonly missionId?: MissionId;
  readonly category: JudgmentCategory;
  readonly title: string;
  /** The AI's position, in prose. Never a menu of options. §2 Founder philosophy. */
  readonly recommendation: string;
  readonly consequence: Consequence;
  readonly confidence: Confidence;
  readonly silenceDefault: SilenceDefault;
  readonly tier: JudgmentTier;
  readonly trigger: EscalationTrigger;
  readonly openedAt: Iso8601;
  readonly deadline?: Iso8601;
  readonly evidence: readonly EvidenceRef[];
  readonly domain: DomainKey;
  /** Ranking position and the justification for it. Eng. Law VII. */
  readonly rank: { readonly position: number; readonly justification: string };
  readonly actions: readonly JudgmentAction[];
}

export interface JudgmentAction {
  readonly key: string;
  readonly label: string;
  readonly intent: 'approve' | 'decline' | 'discuss' | 'delegate' | 'snooze';
}

export type Verdict =
  | { readonly kind: 'approve' }
  | { readonly kind: 'decline'; readonly reason?: string }
  | { readonly kind: 'delegate'; readonly to: PrincipalId }
  | { readonly kind: 'snooze'; readonly until: Iso8601 };

/* ─────────────────────────── receipt ledger ─────────────────────────── */

export type ReceiptPhase = 'intent' | 'outcome';
export type Actor =
  | { readonly kind: 'kernel' }
  | { readonly kind: 'rule'; readonly ruleId: RuleId }
  | { readonly kind: 'founder' }
  | { readonly kind: 'delegate'; readonly principalId: PrincipalId };

/**
 * Append-only. There is intentionally no update or delete anywhere in the
 * client surface — Eng. Law I.
 */
export interface Receipt {
  readonly id: ReceiptId;
  readonly phase: ReceiptPhase;
  readonly intentId: string;
  readonly at: Iso8601;
  readonly actor: Actor;
  readonly actionType: string;
  readonly reversibility: Reversibility;
  readonly expectedEffect: string;
  readonly actualEffect?: string;
  readonly consequence?: Consequence;
  readonly missionId?: MissionId;
  readonly requestId?: RequestId;
  readonly amount?: Money;
  readonly domain: DomainKey;
  readonly result?: 'ok' | 'failed' | 'compensated';
  /** Set when the self-audit flagged this firing as near a boundary. §C5 */
  readonly flagged?: { readonly why: string; readonly proposedNarrowing?: string };
}

/* ──────────────────────── standing rules (autonomy) ─────────────────── */

export type DomainKey =
  | 'vendors'
  | 'spend'
  | 'hiring'
  | 'operations'
  | 'legal'
  | 'product'
  | 'system';

export type RuleStatus = 'trial' | 'active' | 'paused' | 'expired' | 'revoked';

/** All five parts are required. A rule missing any is malformed by construction. */
export interface StandingRule {
  readonly id: RuleId;
  readonly statement: string;
  readonly domain: DomainKey;
  readonly trigger: string;
  readonly cumulativeCap: { readonly limit: Money; readonly windowDays: number; readonly consumed: Money };
  readonly exclusions: readonly string[];
  readonly expiresAt: Iso8601;
  readonly status: RuleStatus;
  readonly grantedAt: Iso8601;
  readonly firingCount: number;
  readonly lastFiredAt?: Iso8601;
  readonly lastReviewedAt?: Iso8601;
}

export interface RuleProposal {
  readonly id: string;
  readonly question: string;
  readonly domain: DomainKey;
  readonly draft: Omit<StandingRule, 'id' | 'status' | 'grantedAt' | 'firingCount'>;
  readonly evidence: {
    readonly observations: readonly { readonly at: Iso8601; readonly outcome: 'approved' | 'declined'; readonly amount?: Money }[];
    readonly windowDays: number;
    readonly medianDecisionSeconds: number;
    readonly boundarySettingRejection?: string;
  };
  readonly interruptionsSaved: number;
}

/* ───────────────────── the line / autonomy (§3, C4) ─────────────────── */

export interface BoundaryState {
  /** 0–1. Share of decisions handled without the founder. */
  readonly autonomyRatio: number;
  readonly delegatedDomains: readonly DomainKey[];
  readonly escalatedClasses: readonly string[];
  readonly activeRuleCount: number;
  readonly suspended: boolean;
  readonly history: readonly { readonly at: Iso8601; readonly ratio: number }[];
}

/* ─────────────────── vigilance attestation (D7, §1) ─────────────────── */

export interface DomainCoverage {
  readonly domain: DomainKey;
  readonly lastCheckedAt: Iso8601;
  readonly healthy: boolean;
  readonly note?: string;
}

/**
 * The calm state is deliberately unconstructable without complete coverage.
 * `complete: false` carries the gaps and forbids the "nothing needs you"
 * sentence — see `canClaimCalm()` in lib/vigilance.ts.
 */
export type Attestation =
  | { readonly complete: true; readonly domains: readonly DomainCoverage[]; readonly at: Iso8601 }
  | { readonly complete: false; readonly domains: readonly DomainCoverage[]; readonly gaps: readonly DomainCoverage[]; readonly at: Iso8601 };

/* ────────────────────────── presence & narration ────────────────────── */

export type PresenceState = 'idle' | 'thinking' | 'speaking' | 'awaiting';

/** §5 — text is the source of truth; speech is a layer over the same stream. */
export interface Utterance {
  readonly id: string;
  readonly text: string;
  /** Figures bound to rendered values so voice never speaks an unseen number. */
  readonly boundValues: readonly { readonly token: string; readonly rendered: string }[];
  readonly register: 'greeting' | 'brief' | 'request' | 'disclosure' | 'answer';
  readonly at: Iso8601;
}

/* ──────────────────────────── memory (M1–M5) ────────────────────────── */

export type MemoryKind = 'episodic' | 'decisional' | 'semantic' | 'procedural' | 'relational';

export interface MemoryRecord {
  readonly id: MemoryId;
  readonly kind: MemoryKind;
  readonly subject: string;
  readonly content: string;
  readonly domain: DomainKey;
  readonly recordedAt: Iso8601;
  /** Freshness is mandatory — it is what makes honest uncertainty possible. */
  readonly lastVerifiedAt: Iso8601;
  readonly retention: { readonly policy: 'permanent' | 'rolling'; readonly days?: number };
  readonly provenance: readonly EvidenceRef[];
  readonly supersedes?: MemoryId;
  readonly contradicts?: readonly MemoryId[];
}

/* ───────────────────────────── capabilities ─────────────────────────── */

export type CapabilityStatus = 'available' | 'unclassified' | 'blocked';

/** Unclassified capabilities are non-executable — the registry fails closed. */
export interface Capability {
  readonly id: CapabilityId;
  readonly name: string;
  readonly description: string;
  readonly domain: DomainKey;
  readonly reversibility: Reversibility | null;
  readonly status: CapabilityStatus;
  readonly invocations: number;
  readonly lastUsedAt?: Iso8601;
  readonly requiresJudgment: boolean;
}

/* ─────────────────────────── live event stream ──────────────────────── */

export type KernelEventType =
  | 'mission.started'
  | 'mission.progress'
  | 'mission.completed'
  | 'mission.failed'
  | 'mission.held'
  | 'receipt.intent'
  | 'receipt.outcome'
  | 'judgment.opened'
  | 'judgment.resolved'
  | 'judgment.default-fired'
  | 'rule.proposed'
  | 'rule.granted'
  | 'rule.fired'
  | 'rule.expired'
  | 'audit.flagged'
  | 'presence.changed'
  | 'attestation.updated'
  | 'boundary.changed'
  | 'mistake.disclosed';

export interface KernelEvent {
  readonly id: string;
  readonly type: KernelEventType;
  readonly at: Iso8601;
  readonly domain: DomainKey;
  /** One line, human-legible. Every event must be renderable as prose. */
  readonly line: string;
  readonly signal: Signal;
  readonly refs?: {
    readonly missionId?: MissionId;
    readonly receiptId?: ReceiptId;
    readonly requestId?: RequestId;
    readonly ruleId?: RuleId;
  };
}

/* ──────────────────────── mistakes (§8 protocol) ────────────────────── */

export interface MistakeDisclosure {
  readonly id: string;
  readonly at: Iso8601;
  readonly impact: string;
  readonly cause: string;
  readonly fix: string;
  readonly prevention: string;
  readonly proposedRuleChange?: string;
  readonly acknowledged: boolean;
}

/* ─────────────────────────── brief composition ──────────────────────── */

export interface Brief {
  readonly since: Iso8601;
  readonly attestation: Attestation;
  readonly handledCount: number;
  readonly runningCount: number;
  readonly openRequests: readonly JudgmentRequest[];
  readonly flaggedReceipts: readonly Receipt[];
  readonly disclosures: readonly MistakeDisclosure[];
  readonly headline: Utterance;
}

/* ─────────────────────────────── principals ─────────────────────────── */

export interface Principal {
  readonly id: PrincipalId;
  readonly name: string;
  readonly role: string;
  readonly isFounder: boolean;
  readonly delegatedDomains: readonly DomainKey[];
}

/* ─────────────────────────── dependency audit ───────────────────────── */

export interface DependencyAudit {
  readonly year: number;
  readonly generatedAt: Iso8601;
  readonly unaskedAuthority: readonly string[];
  readonly unexaminedRules: readonly RuleId[];
  readonly whatWouldBeLost: readonly string[];
  readonly selfAssessedOverreach: readonly string[];
}

/* ───────────────────────── paging / query shapes ────────────────────── */

export interface Page<T> {
  readonly items: readonly T[];
  readonly cursor?: string;
  readonly total?: number;
}

export interface LedgerQuery {
  readonly domain?: DomainKey;
  readonly actor?: Actor['kind'];
  readonly from?: Iso8601;
  readonly to?: Iso8601;
  readonly flaggedOnly?: boolean;
  readonly search?: string;
  readonly cursor?: string;
  readonly limit?: number;
}
