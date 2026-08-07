/**
 * Seed data for an Indian SaaS startup (~60 people).
 * Founder: Onkar.  Currency: INR, amounts in paise (minor units).
 *
 * All dates are computed relative to Date.now() so the app never looks stale.
 * Headline items are hand-written and specific; bulk receipts/events are
 * generated programmatically to keep the file sane while providing realistic
 * history depth.
 */

import type {
  Mission,
  JudgmentRequest,
  Receipt,
  StandingRule,
  RuleProposal,
  MemoryRecord,
  Capability,
  Principal,
  MistakeDisclosure,
  DependencyAudit,
  BoundaryState,
  Attestation,
  KernelEvent,
  Consequence,
  Reversibility,
  EvidenceRef,
  DomainKey,
  Money,
  Actor,
  MemoryKind,
} from '@/kernel/types';

/* ── tiny deterministic helpers ─────────────────────────────────────────── */

function ago(seconds: number): string {
  return new Date(Date.now() - seconds * 1000).toISOString();
}
function fromNow(seconds: number): string {
  return new Date(Date.now() + seconds * 1000).toISOString();
}
const MIN = 60;
const HOUR = 3600;
const DAY = 86400;

function inr(paise: number): Money {
  return { currency: 'INR', minor: paise };
}

function rev(kind: 'reversible', comp: string): Reversibility;
function rev(kind: 'reversible-until', until: string, comp: string): Reversibility;
function rev(kind: 'irreversible', reason: string): Reversibility;
function rev(
  kind: 'reversible' | 'reversible-until' | 'irreversible',
  a: string,
  b?: string,
): Reversibility {
  if (kind === 'reversible') return { kind, compensatingAction: a };
  if (kind === 'reversible-until') return { kind, until: a, compensatingAction: b ?? '' };
  return { kind, reason: a };
}

let _idSeq = 1;
function uid(prefix: string): string {
  return `${prefix}_${(_idSeq++).toString().padStart(4, '0')}`;
}

function ev(prefix: string): EvidenceRef {
  return {
    id: uid('ev'),
    label: prefix,
    source: 'kernel-memory',
    observedAt: ago(DAY * 3),
  };
}

/* ── principals ─────────────────────────────────────────────────────────── */

export const seedPrincipals: readonly Principal[] = [
  {
    id: 'principal_onkar',
    name: 'Onkar',
    role: 'Founder & CEO',
    isFounder: true,
    delegatedDomains: ['vendors', 'spend', 'hiring', 'operations', 'legal', 'product', 'system'],
  },
  {
    id: 'principal_priya',
    name: 'Priya',
    role: 'Chief Financial Officer',
    isFounder: false,
    delegatedDomains: ['spend', 'vendors'],
  },
  {
    id: 'principal_arjun',
    name: 'Arjun',
    role: 'Head of Engineering',
    isFounder: false,
    delegatedDomains: ['system', 'operations'],
  },
];

/* ── standing rules ─────────────────────────────────────────────────────── */

export const RULE_TOOLING = 'rule_tooling_renewals';
export const RULE_CONTRACTOR = 'rule_contractor_sow';
export const RULE_LARGE_INVOICES = 'rule_large_invoices_priya';
export const RULE_CUSTOMER_DATA = 'rule_customer_data_block';
export const RULE_QUARTER_END = 'rule_quarter_end_hold';
export const RULE_INTERVIEWS = 'rule_interview_schedule';

export const seedRules: readonly StandingRule[] = [
  {
    id: RULE_TOOLING,
    statement:
      'Auto-approve tooling and SaaS renewals where the vendor is already in use, the amount is under ₹50,000, and no customer data is involved.',
    domain: 'vendors',
    trigger: 'Renewal invoice received from known vendor, amount < ₹50,000',
    cumulativeCap: {
      limit: inr(50_000_00), // ₹50,000 in paise
      windowDays: 30,
      consumed: inr(29_700_00),
    },
    exclusions: ['Any action touching customer data', 'New vendors', 'Amounts above ₹50,000'],
    expiresAt: fromNow(DAY * 60),
    status: 'trial',
    grantedAt: ago(DAY * 41),
    firingCount: 9,
    lastFiredAt: ago(DAY * 3),
    lastReviewedAt: ago(DAY * 7),
  },
  {
    id: RULE_CONTRACTOR,
    statement:
      'Auto-approve contractor invoices that match a signed SOW on file: same vendor, same period, amount within 5% of agreed rate.',
    domain: 'spend',
    trigger: 'Contractor invoice received matching SOW reference on file',
    cumulativeCap: {
      limit: inr(5_00_000_00), // ₹5,00,000 in paise
      windowDays: 30,
      consumed: inr(3_78_000_00),
    },
    exclusions: ['New SOWs', 'Scope changes', 'Amount deviation > 5%'],
    expiresAt: fromNow(DAY * 90),
    status: 'active',
    grantedAt: ago(DAY * 75),
    firingCount: 12,
    lastFiredAt: ago(DAY * 1),
    lastReviewedAt: ago(DAY * 14),
  },
  {
    id: RULE_LARGE_INVOICES,
    statement:
      'Route all invoices above ₹2,00,000 to Priya (CFO) for review before processing — do not action them autonomously.',
    domain: 'spend',
    trigger: 'Invoice amount > ₹2,00,000',
    cumulativeCap: {
      limit: inr(0),
      windowDays: 30,
      consumed: inr(0),
    },
    exclusions: [],
    expiresAt: fromNow(DAY * 180),
    status: 'active',
    grantedAt: ago(DAY * 90),
    firingCount: 4,
    lastFiredAt: ago(DAY * 5),
    lastReviewedAt: ago(DAY * 30),
  },
  {
    id: RULE_CUSTOMER_DATA,
    statement:
      'Never take autonomous action on anything that touches customer data: reads, writes, exports, shares, or deletions.',
    domain: 'system',
    trigger: 'Any action classified as touching customer data',
    cumulativeCap: {
      limit: inr(0),
      windowDays: 365,
      consumed: inr(0),
    },
    exclusions: [],
    expiresAt: fromNow(DAY * 365),
    status: 'active',
    grantedAt: ago(DAY * 200),
    firingCount: 0,
    lastReviewedAt: ago(DAY * 30),
  },
  {
    id: RULE_QUARTER_END,
    statement:
      'Hold all spend decisions (approvals and payments) during the last 5 days of each quarter. Surface them for founder review on the first day of the new quarter.',
    domain: 'spend',
    trigger: 'Any spend action, if within last 5 days of a calendar quarter',
    cumulativeCap: {
      limit: inr(0),
      windowDays: 90,
      consumed: inr(0),
    },
    exclusions: ['Payroll', 'Previously approved recurring payments'],
    expiresAt: fromNow(DAY * 270),
    status: 'active',
    grantedAt: ago(DAY * 120),
    firingCount: 2,
    lastFiredAt: ago(DAY * 25),
    lastReviewedAt: ago(DAY * 25),
  },
  {
    id: RULE_INTERVIEWS,
    statement:
      'Auto-schedule initial screening calls for candidates who pass the resume screen: propose 3 time slots, send calendar invites, no founder input needed.',
    domain: 'hiring',
    trigger: 'Candidate advances past resume screen stage',
    cumulativeCap: {
      limit: inr(0),
      windowDays: 30,
      consumed: inr(0),
    },
    exclusions: ['VP and above roles', 'Founder-referred candidates'],
    expiresAt: fromNow(DAY * 30),
    status: 'paused',
    grantedAt: ago(DAY * 55),
    firingCount: 7,
    lastFiredAt: ago(DAY * 10),
    lastReviewedAt: ago(DAY * 10),
  },
];

/* ── rule proposals ─────────────────────────────────────────────────────── */

export const seedProposals: readonly RuleProposal[] = [
  {
    id: 'proposal_tooling_auto',
    question:
      "You've approved 9 of 9 tooling renewals under ₹50,000. Want me to stop asking?",
    domain: 'vendors',
    draft: {
      statement:
        'Auto-approve tooling renewals under ₹50,000 from vendors already in use, with no customer-data involvement.',
      domain: 'vendors',
      trigger: 'Renewal from known vendor, amount < ₹50,000',
      cumulativeCap: {
        limit: inr(50_000_00),
        windowDays: 30,
        consumed: inr(0),
      },
      exclusions: ['New vendors', 'Customer data', 'Amount ≥ ₹50,000'],
      expiresAt: fromNow(DAY * 90),
    },
    evidence: {
      observations: [
        { at: ago(DAY * 41), outcome: 'approved', amount: inr(7_200_00) },
        { at: ago(DAY * 39), outcome: 'approved', amount: inr(18_500_00) },
        { at: ago(DAY * 35), outcome: 'approved', amount: inr(34_000_00) },
        { at: ago(DAY * 30), outcome: 'approved', amount: inr(12_000_00) },
        { at: ago(DAY * 27), outcome: 'approved', amount: inr(9_500_00) },
        { at: ago(DAY * 24), outcome: 'approved', amount: inr(22_000_00) },
        { at: ago(DAY * 20), outcome: 'approved', amount: inr(48_000_00) },
        { at: ago(DAY * 16), outcome: 'approved', amount: inr(15_000_00) },
        { at: ago(DAY * 12), outcome: 'declined', amount: inr(64_000_00) },
        { at: ago(DAY * 8), outcome: 'approved', amount: inr(7_200_00) },
      ],
      windowDays: 41,
      medianDecisionSeconds: 240, // 4 minutes
      boundarySettingRejection: '₹64,000 declined — sets the ceiling at ₹50,000',
    },
    interruptionsSaved: 9,
  },
];

/* ── missions ────────────────────────────────────────────────────────────── */

export const seedMissions: readonly Mission[] = [
  {
    id: 'mission_datastack_renewal',
    name: 'Datastack renewal negotiation',
    summary:
      'Evaluate Datastack renewal at ₹18,40,000/yr (22% above market) and negotiate to ₹14,50,000 target before Friday 00:00 lock-in.',
    state: 'held',
    impact: 'high',
    startedAt: ago(DAY * 2),
    domain: 'vendors',
    receiptIds: ['receipt_ds_001', 'receipt_ds_002'],
    heldOnRequestId: 'req_datastack_verdict',
    progress: 0.45,
  },
  {
    id: 'mission_staff_eng_offer',
    name: 'Staff Engineer offer — Rohan Verma',
    summary:
      'Complete offer for Staff Engineer at ₹92,00,000. Candidate has competing offer expiring Wednesday.',
    state: 'held',
    impact: 'high',
    startedAt: ago(HOUR * 18),
    domain: 'hiring',
    receiptIds: ['receipt_hire_001'],
    heldOnRequestId: 'req_staff_eng_offer',
    progress: 0.7,
  },
  {
    id: 'mission_infra_decision',
    name: 'Infra stack decision',
    summary: 'Resolve EKS vs. managed Kubernetes decision blocking two engineers for 6 days.',
    state: 'held',
    impact: 'medium',
    startedAt: ago(DAY * 6),
    domain: 'system',
    receiptIds: ['receipt_infra_001'],
    heldOnRequestId: 'req_infra_decision',
    progress: 0.6,
  },
  {
    id: 'mission_sweep_q2',
    name: 'Q2 sweep-tier approvals',
    summary: 'Five routine items ready for batch review: AWS reserved top-up, Figma seats, contractor invoice, Sentry, SaaSBoomi booth.',
    state: 'running',
    impact: 'low',
    startedAt: ago(HOUR * 4),
    domain: 'spend',
    receiptIds: [],
    progress: 0.2,
  },
  {
    id: 'mission_vendor_audit',
    name: 'Quarterly vendor audit',
    summary: 'Cross-check all active vendor contracts against current usage and flag underutilised tools.',
    state: 'running',
    impact: 'medium',
    startedAt: ago(HOUR * 8),
    domain: 'vendors',
    receiptIds: ['receipt_audit_001', 'receipt_audit_002'],
    progress: 0.55,
    etaSeconds: HOUR * 3,
  },
  {
    id: 'mission_payroll_aug',
    name: 'August payroll processing',
    summary: 'Process payroll for 62 employees. All inputs verified, no variances.',
    state: 'completed',
    impact: 'high',
    startedAt: ago(DAY * 5),
    endedAt: ago(DAY * 4 + HOUR * 20),
    domain: 'spend',
    receiptIds: ['receipt_payroll_aug'],
  },
  {
    id: 'mission_contract_renewal_slack',
    name: 'Slack Enterprise renewal',
    summary: 'Processed Slack annual renewal at ₹3,12,000 (within cap, matching last year).',
    state: 'completed',
    impact: 'low',
    startedAt: ago(DAY * 8),
    endedAt: ago(DAY * 8 + HOUR * 2),
    domain: 'vendors',
    receiptIds: ['receipt_slack_renewal'],
  },
];

/* ── judgment requests ───────────────────────────────────────────────────── */

const datastackConsequence: Consequence = {
  whatChanges:
    'Sign a 12-month renewal at ₹18,40,000 instead of opening a counter-position. Counter opens at ₹13,80,000 and we expect to settle at ₹14,50,000.',
  cost: inr(18_40_000_00), // ₹18,40,000 in paise
  ifYouDoNothing:
    'The auto-renewal clause fires Friday at 00:00 IST, locking us in at ₹18,40,000 for 12 months — no further negotiation possible.',
  reversibility: rev(
    'reversible-until',
    fromNow(DAY * 3 - HOUR * 6), // Friday 00:00
    'Cancel before Friday 00:00 and open counter-position at ₹13,80,000',
  ),
};

const staffEngConsequence: Consequence = {
  whatChanges:
    'Extend offer to Rohan Verma at ₹92,00,000 total compensation. Band was set 14 months ago; this is 11% above the midpoint.',
  cost: inr(92_00_000_00),
  ifYouDoNothing:
    "Rohan's competing offer expires Wednesday. If we haven't extended by then he will almost certainly accept the other offer.",
  reversibility: rev('reversible', 'Offer can be rescinded before acceptance — standard 48h window'),
};

const infraConsequence: Consequence = {
  whatChanges:
    'Commit to managed Kubernetes (EKS) for the next 18 months. Two engineers are currently blocked on this decision.',
  cost: { kind: 'non-monetary', description: 'No direct spend increase — EKS costs are already in the AWS budget' },
  ifYouDoNothing:
    'Engineers remain blocked. Each additional day costs approximately ₹26,000 in salary on stalled work.',
  reversibility: rev('irreversible', 'Migrating away mid-project would cost 3–4 engineer-weeks and incur data-transfer fees'),
};

export const seedRequests: readonly JudgmentRequest[] = [
  /* ── needs-you: Datastack renewal ── */
  {
    id: 'req_datastack_verdict',
    missionId: 'mission_datastack_renewal',
    category: 'financial',
    tier: 'needs-you',
    trigger: 'irreversible',
    title: 'Datastack renewal: counter-position or lock in?',
    recommendation:
      'Open counter-position at ₹13,80,000 targeting ₹14,50,000. We use 34% of seats, are 22% above market, and have a credible walk position. Expected upside ~₹4,10,000/yr. Deadline Friday 00:00 — the auto-renewal is irreversible after that.',
    consequence: datastackConsequence,
    confidence: {
      level: 'recommend',
      phrasing:
        'Market data from three comparable deals and our usage telemetry both point to the same negotiating position.',
    },
    silenceDefault: {
      action: 'Allow auto-renewal at ₹18,40,000 — do nothing, miss the negotiation window.',
      firesAt: fromNow(DAY * 3 - HOUR * 6),
      staleIfFactsChange: true,
    },
    openedAt: ago(HOUR * 14),
    deadline: fromNow(DAY * 3 - HOUR * 6),
    domain: 'vendors',
    rank: { position: 1, justification: 'Irreversible deadline Friday — highest urgency in queue.' },
    evidence: [
      {
        id: 'ev_ds_market',
        label: 'Market benchmark — 3 comparable SaaS deals',
        source: 'Kernel research, vendor pricing intel',
        observedAt: ago(DAY * 1),
      },
      {
        id: 'ev_ds_usage',
        label: 'Seat usage: 34% over trailing 90 days',
        source: 'Datastack usage API',
        observedAt: ago(HOUR * 6),
      },
      {
        id: 'ev_ds_clause',
        label: 'Auto-renewal clause — contract §7.2',
        source: 'Contract on file',
        observedAt: ago(DAY * 30),
      },
    ],
    actions: [
      { key: 'counter', label: 'Open counter at ₹13,80,000', intent: 'approve' },
      { key: 'renew', label: 'Accept ₹18,40,000 renewal', intent: 'decline' },
      { key: 'discuss', label: 'Discuss negotiation strategy', intent: 'discuss' },
    ],
  },

  /* ── needs-you: Staff Engineer offer ── */
  {
    id: 'req_staff_eng_offer',
    missionId: 'mission_staff_eng_offer',
    category: 'strategic',
    tier: 'needs-you',
    trigger: 'novel',
    title: 'Staff Engineer offer — Rohan Verma — above band',
    recommendation:
      'Extend the offer at ₹92,00,000. The band was set 14 months ago and the market has moved. Rohan has a competing offer expiring Wednesday — delaying risks losing the candidate. Recommend also scheduling a band review for Q3.',
    consequence: staffEngConsequence,
    confidence: {
      level: 'lean',
      phrasing:
        'Strong candidate, credible competing offer — but this is a judgment call on band policy, not pure analysis.',
    },
    silenceDefault: {
      action: "Take no action — Rohan's window closes and the competing offer will likely be accepted.",
      firesAt: fromNow(DAY * 2 - HOUR * 4), // Wednesday
      staleIfFactsChange: true,
    },
    openedAt: ago(HOUR * 18),
    deadline: fromNow(DAY * 2 - HOUR * 4),
    domain: 'hiring',
    rank: { position: 2, justification: 'Time-sensitive (Wednesday deadline) and high-impact hire.' },
    evidence: [
      {
        id: 'ev_hire_comp',
        label: 'Competing offer details — ₹88,00,000 + RSUs',
        source: 'Recruiter notes',
        observedAt: ago(HOUR * 20),
      },
      {
        id: 'ev_hire_band',
        label: 'Staff Eng band — set 14 months ago',
        source: 'Compensation framework v2.1',
        observedAt: ago(DAY * 14 * 30),
      },
      {
        id: 'ev_hire_interview',
        label: 'Interview panel scores — 4.4/5 average',
        source: 'Hiring system',
        observedAt: ago(DAY * 2),
      },
    ],
    actions: [
      { key: 'extend', label: 'Extend offer at ₹92,00,000', intent: 'approve' },
      { key: 'counter', label: 'Counter at band midpoint ₹82,00,000', intent: 'decline' },
      { key: 'delegate', label: 'Delegate to Arjun (Head of Eng)', intent: 'delegate' },
    ],
  },

  /* ── needs-you: infra decision ── */
  {
    id: 'req_infra_decision',
    missionId: 'mission_infra_decision',
    category: 'strategic',
    tier: 'needs-you',
    trigger: 'irreversible',
    title: 'Infra stack decision: EKS vs. managed Kubernetes — blocking 2 engineers, 6 days',
    recommendation:
      'Commit to EKS. Two engineers are blocked right now. Comparable teams at this scale are on EKS and the operational overhead advantage of managed Kubernetes does not materialise until 15+ services. Our current count is 8.',
    consequence: infraConsequence,
    confidence: {
      level: 'recommend',
      phrasing: 'Analysis of team size, service count, and operational cost consistently favours EKS at this stage.',
    },
    silenceDefault: {
      action: 'Engineers remain blocked. The decision will resurface in 48h with a revised cost estimate.',
      firesAt: fromNow(DAY * 2),
      staleIfFactsChange: false,
    },
    openedAt: ago(DAY * 6),
    domain: 'system',
    rank: {
      position: 3,
      justification: '6 days of blocked engineering work accumulating daily — cost of delay is real and measurable.',
    },
    evidence: [
      {
        id: 'ev_infra_blocked',
        label: 'Engineering status — 2 engineers blocked since Monday',
        source: 'Linear project tracker',
        observedAt: ago(HOUR * 2),
      },
      {
        id: 'ev_infra_cost',
        label: 'Daily opportunity cost estimate: ₹26,000',
        source: 'Kernel salary model',
        observedAt: ago(DAY * 1),
      },
    ],
    actions: [
      { key: 'eks', label: 'Commit to EKS', intent: 'approve' },
      { key: 'managed', label: 'Choose managed Kubernetes instead', intent: 'decline' },
      { key: 'discuss', label: 'Discuss tradeoffs with Arjun', intent: 'discuss' },
    ],
  },

  /* ── sweep: AWS reserved instance top-up ── */
  {
    id: 'req_aws_reserved',
    category: 'financial',
    tier: 'sweep',
    trigger: 'excluded-by-rule',
    title: 'AWS reserved instance top-up — ₹34,000',
    recommendation: 'Approve. Matches last quarter purchase, 23% discount over on-demand.',
    consequence: {
      whatChanges: 'Purchase 3 additional reserved instances (1yr, t3.medium).',
      cost: inr(34_000_00),
      ifYouDoNothing: 'Continue at on-demand rates — costs ~₹9,000 more per month.',
      reversibility: rev('reversible-until', fromNow(DAY * 30), 'Cancel reserved instances within 30 days for partial refund'),
    },
    confidence: { level: 'recommend', phrasing: 'Straightforward cost optimisation, precedent from last quarter.' },
    silenceDefault: {
      action: 'Defer — no automatic action.',
      firesAt: fromNow(DAY * 7),
      staleIfFactsChange: false,
    },
    openedAt: ago(HOUR * 2),
    domain: 'spend',
    rank: { position: 4, justification: 'Low value, routine precedent — bottom of queue.' },
    evidence: [ev('AWS billing export')],
    actions: [
      { key: 'approve', label: 'Approve ₹34,000', intent: 'approve' },
      { key: 'decline', label: 'Decline', intent: 'decline' },
    ],
  },

  /* ── sweep: Figma seats ── */
  {
    id: 'req_figma_seats',
    category: 'financial',
    tier: 'sweep',
    trigger: 'excluded-by-rule',
    title: 'Figma — 3 additional seats — ₹18,500',
    recommendation: 'Approve. Design team has 3 contractors starting Monday, seats needed day-1.',
    consequence: {
      whatChanges: 'Add 3 Figma Professional seats for the quarter.',
      cost: inr(18_500_00),
      ifYouDoNothing: 'Contractors start without tool access — first day lost.',
      reversibility: rev('reversible', 'Remove seats at end of contract, prorated refund'),
    },
    confidence: { level: 'recommend', phrasing: 'Operational necessity — contractors start Monday.' },
    silenceDefault: {
      action: 'Defer until next sweep review.',
      firesAt: fromNow(DAY * 3),
      staleIfFactsChange: true,
    },
    openedAt: ago(HOUR * 3),
    domain: 'vendors',
    rank: { position: 5, justification: 'Time-sensitive (Monday) but small amount.' },
    evidence: [ev('Contractor onboarding checklist')],
    actions: [
      { key: 'approve', label: 'Approve ₹18,500', intent: 'approve' },
      { key: 'decline', label: 'Decline', intent: 'decline' },
    ],
  },

  /* ── sweep: contractor invoice ── */
  {
    id: 'req_contractor_invoice',
    category: 'financial',
    tier: 'sweep',
    trigger: 'excluded-by-rule',
    title: 'Contractor invoice — Meera Krishnan — ₹1,26,000 — matches SOW',
    recommendation: 'Approve. Invoice matches SOW-2024-089 exactly. Same vendor, same rate, correct period.',
    consequence: {
      whatChanges: 'Pay Meera Krishnan July invoice per SOW-2024-089.',
      cost: inr(1_26_000_00),
      ifYouDoNothing: 'Payment 5 days late — contractor contract specifies a 7-day payment window.',
      reversibility: rev('irreversible', 'Bank transfer cannot be recalled once initiated'),
    },
    confidence: { level: 'recommend', phrasing: 'Exact SOW match, no variance.' },
    silenceDefault: {
      action: 'Defer — risk late payment breach.',
      firesAt: fromNow(DAY * 2),
      staleIfFactsChange: false,
    },
    openedAt: ago(HOUR * 5),
    domain: 'spend',
    rank: { position: 6, justification: 'Payment deadline in 2 days.' },
    evidence: [ev('SOW-2024-089 on file'), ev('Invoice INV-MK-2024-07')],
    actions: [
      { key: 'approve', label: 'Approve ₹1,26,000', intent: 'approve' },
      { key: 'decline', label: 'Decline', intent: 'decline' },
    ],
  },

  /* ── sweep: Sentry upgrade ── */
  {
    id: 'req_sentry_upgrade',
    category: 'financial',
    tier: 'sweep',
    trigger: 'excluded-by-rule',
    title: 'Sentry Business upgrade — ₹7,200',
    recommendation:
      'Approve. Team upgraded plan to add performance monitoring. Note: a similar Sentry item was approved 3 days ago — see flagged receipt for context.',
    consequence: {
      whatChanges: 'Upgrade Sentry plan from Team to Business tier for the month.',
      cost: inr(7_200_00),
      ifYouDoNothing: 'Performance monitoring features unavailable — engineers lose visibility into p95 latency.',
      reversibility: rev('reversible', 'Downgrade plan at month end'),
    },
    confidence: { level: 'lean', phrasing: 'Unusual to have two Sentry items in one week — flagged for awareness.' },
    silenceDefault: {
      action: 'Defer to next review.',
      firesAt: fromNow(DAY * 5),
      staleIfFactsChange: false,
    },
    openedAt: ago(HOUR * 1),
    domain: 'system',
    rank: { position: 7, justification: 'Sweep-tier, low amount, no deadline.' },
    evidence: [ev('Sentry billing page'), ev('Engineering request ticket #4821')],
    actions: [
      { key: 'approve', label: 'Approve ₹7,200', intent: 'approve' },
      { key: 'decline', label: 'Decline', intent: 'decline' },
    ],
  },

  /* ── sweep: SaaSBoomi booth deposit ── */
  {
    id: 'req_saasboomi_booth',
    category: 'financial',
    tier: 'sweep',
    trigger: 'novel',
    title: 'SaaSBoomi 2025 booth deposit — ₹48,000',
    recommendation: 'Approve. Early-bird deposit to reserve a booth at SaaSBoomi Annual (Chennai, Feb 2025). Last year generated 12 qualified pipeline leads.',
    consequence: {
      whatChanges: 'Pay ₹48,000 deposit; full booth cost ₹1,80,000 due December.',
      cost: inr(48_000_00),
      ifYouDoNothing: 'Early-bird slots close tomorrow; standard rate is ₹2,40,000.',
      reversibility: rev('reversible-until', fromNow(DAY * 45), 'Full refund within 45 days'),
    },
    confidence: { level: 'lean', phrasing: 'Good ROI precedent from last year — but this is a go-to-market call.' },
    silenceDefault: {
      action: 'Defer — miss early-bird pricing.',
      firesAt: fromNow(DAY * 1),
      staleIfFactsChange: false,
    },
    openedAt: ago(MIN * 30),
    domain: 'operations',
    rank: { position: 8, justification: 'Tomorrow deadline for early-bird — sweep but time-sensitive.' },
    evidence: [ev('SaaSBoomi 2024 pipeline report'), ev('Booth booking form')],
    actions: [
      { key: 'approve', label: 'Approve deposit ₹48,000', intent: 'approve' },
      { key: 'decline', label: 'Decline', intent: 'decline' },
    ],
  },
];

/* ── receipts ────────────────────────────────────────────────────────────── */

// Headline hand-written receipts
const headlineReceipts: Receipt[] = [
  {
    id: 'receipt_ds_001',
    phase: 'intent',
    intentId: 'intent_ds_001',
    at: ago(DAY * 2),
    actor: { kind: 'kernel' },
    actionType: 'vendor.renewal-research',
    reversibility: rev('reversible', 'Research has no side effects'),
    expectedEffect: 'Gather market pricing data for Datastack negotiation.',
    domain: 'vendors',
    missionId: 'mission_datastack_renewal',
  },
  {
    id: 'receipt_ds_002',
    phase: 'outcome',
    intentId: 'intent_ds_001',
    at: ago(DAY * 1 + HOUR * 22),
    actor: { kind: 'kernel' },
    actionType: 'vendor.renewal-research',
    reversibility: rev('reversible', 'Research has no side effects'),
    expectedEffect: 'Gather market pricing data for Datastack negotiation.',
    actualEffect: 'Found 3 comparable deals at ₹14,00,000–₹15,20,000. Usage at 34%. Recommend counter at ₹13,80,000.',
    domain: 'vendors',
    missionId: 'mission_datastack_renewal',
    result: 'ok',
  },
  {
    id: 'receipt_hire_001',
    phase: 'intent',
    intentId: 'intent_hire_001',
    at: ago(HOUR * 18),
    actor: { kind: 'kernel' },
    actionType: 'hiring.candidate-research',
    reversibility: rev('reversible', 'Read-only action'),
    expectedEffect: 'Compile compensation benchmark for Staff Eng role vs. Rohan offer.',
    domain: 'hiring',
    missionId: 'mission_staff_eng_offer',
  },
  {
    id: 'receipt_infra_001',
    phase: 'intent',
    intentId: 'intent_infra_001',
    at: ago(DAY * 6),
    actor: { kind: 'kernel' },
    actionType: 'system.infra-research',
    reversibility: rev('reversible', 'Read-only action'),
    expectedEffect: 'Analyse EKS vs managed Kubernetes for current team/service scale.',
    domain: 'system',
    missionId: 'mission_infra_decision',
  },
  {
    id: 'receipt_payroll_aug',
    phase: 'outcome',
    intentId: 'intent_payroll_aug',
    at: ago(DAY * 4 + HOUR * 20),
    actor: { kind: 'rule', ruleId: RULE_CONTRACTOR },
    actionType: 'spend.payroll-process',
    reversibility: rev('irreversible', 'Bank transfers cannot be recalled'),
    expectedEffect: 'Process August payroll for 62 employees.',
    actualEffect: 'Payroll processed successfully. Total disbursed ₹83,40,000.',
    amount: inr(83_40_000_00),
    domain: 'spend',
    missionId: 'mission_payroll_aug',
    result: 'ok',
  },
  {
    id: 'receipt_slack_renewal',
    phase: 'outcome',
    intentId: 'intent_slack_001',
    at: ago(DAY * 8 + HOUR * 2),
    actor: { kind: 'rule', ruleId: RULE_TOOLING },
    actionType: 'vendor.renewal-approve',
    reversibility: rev('reversible-until', fromNow(DAY * 0), 'Within 30 days of renewal — window has passed'),
    expectedEffect: 'Renew Slack Enterprise for 12 months.',
    actualEffect: 'Slack Enterprise renewed at ₹3,12,000/yr.',
    amount: inr(3_12_000_00),
    domain: 'vendors',
    missionId: 'mission_contract_renewal_slack',
    result: 'ok',
  },
  // The flagged Sentry receipt
  {
    id: 'receipt_sentry_flagged',
    phase: 'outcome',
    intentId: 'intent_sentry_001',
    at: ago(DAY * 3),
    actor: { kind: 'rule', ruleId: RULE_TOOLING },
    actionType: 'vendor.renewal-approve',
    reversibility: rev('reversible', 'Downgrade plan at month end'),
    expectedEffect: 'Approve Sentry Team plan renewal ₹7,200.',
    actualEffect: 'Approved under tooling rule. Note: second Sentry item in one week.',
    amount: inr(7_200_00),
    domain: 'system',
    result: 'ok',
    flagged: {
      why: 'Second Sentry approval within 7 days — near-boundary pattern detected. The rule was designed for once-per-cycle renewals.',
      proposedNarrowing: 'Narrow tooling rule exclusions: add "max once per vendor per calendar month".',
    },
  },
  {
    id: 'receipt_audit_001',
    phase: 'intent',
    intentId: 'intent_audit_001',
    at: ago(HOUR * 8),
    actor: { kind: 'kernel' },
    actionType: 'vendors.audit-scan',
    reversibility: rev('reversible', 'Read-only'),
    expectedEffect: 'Scan all vendor contracts for underutilisation.',
    domain: 'vendors',
    missionId: 'mission_vendor_audit',
  },
  {
    id: 'receipt_audit_002',
    phase: 'outcome',
    intentId: 'intent_audit_001',
    at: ago(HOUR * 6),
    actor: { kind: 'kernel' },
    actionType: 'vendors.audit-scan',
    reversibility: rev('reversible', 'Read-only'),
    expectedEffect: 'Scan all vendor contracts for underutilisation.',
    actualEffect: 'Found 3 tools with usage < 20%: Notion (18%), Loom (14%), Intercom legacy (9%). Report ready.',
    domain: 'vendors',
    missionId: 'mission_vendor_audit',
    result: 'ok',
  },
];

// Programmatic bulk receipts — 30 days of routine activity
type ActorKind = Actor['kind'];
const DOMAINS: DomainKey[] = ['vendors', 'spend', 'hiring', 'operations', 'system'];
const ACTORS: ActorKind[] = ['kernel', 'rule', 'founder'];
const ACTIONS = [
  'vendor.invoice-approve',
  'vendor.renewal-approve',
  'spend.payment-initiate',
  'system.alert-triage',
  'hiring.screen-schedule',
  'operations.report-generate',
  'vendors.contract-check',
];

function makeActor(kind: ActorKind): Actor {
  if (kind === 'rule') return { kind: 'rule', ruleId: RULE_TOOLING };
  return { kind };
}

const bulkReceipts: Receipt[] = [];
for (let day = 1; day <= 30; day++) {
  const countToday = 4 + (day % 3); // 4–6 per day
  for (let i = 0; i < countToday; i++) {
    const seqId = `bulk_${day}_${i}`;
    const domainIdx = (day * 3 + i) % DOMAINS.length;
    const domain = DOMAINS[domainIdx] ?? 'spend';
    const actorKind = ACTORS[(day + i) % ACTORS.length] ?? 'kernel';
    const action = ACTIONS[(day * 2 + i) % ACTIONS.length] ?? 'vendor.invoice-approve';
    const phase: 'intent' | 'outcome' = i % 2 === 0 ? 'intent' : 'outcome';
    const baseAmount = (day * 1_000 + i * 200) * 100; // in paise, 10–150 range in rupees * 100

    bulkReceipts.push({
      id: `receipt_${seqId}`,
      phase,
      intentId: `intent_bulk_${day}_${Math.floor(i / 2)}`,
      at: ago(DAY * (31 - day) + HOUR * (i * 3)),
      actor: makeActor(actorKind),
      actionType: action,
      reversibility: rev('reversible', 'Compensating action available within 30 days'),
      expectedEffect: `Routine ${action.replace('.', ' ')} — day ${day}, item ${i + 1}.`,
      ...(phase === 'outcome' && {
        actualEffect: `Completed successfully.`,
        result: 'ok' as const,
        ...(action.includes('payment') || action.includes('approve')
          ? { amount: inr(baseAmount) }
          : {}),
      }),
      domain,
    });
  }
}

export const seedReceipts: readonly Receipt[] = [...headlineReceipts, ...bulkReceipts];

/* ── mistake disclosure ─────────────────────────────────────────────────── */

export const seedDisclosure: readonly MistakeDisclosure[] = [
  {
    id: 'mistake_datastack_contact',
    at: ago(DAY * 60), // stale since ~March
    impact:
      'Reached out to wrong contact at Datastack for renewal negotiation. Stale CRM record showed Vikram Malhotra as Account Manager — he moved to a different role in March. Three outreach attempts went unanswered before the error was caught.',
    cause:
      'CRM record for Datastack had not been refreshed since March. The Kernel used the stored contact without verification.',
    fix: 'Contacted correct AM (Riya Sharma) directly. Negotiation restarted with 2 days to spare.',
    prevention:
      'Before any vendor outreach, verify contact record is < 60 days old. Flag stale records to founder for re-verification.',
    proposedRuleChange:
      'Add exclusion to vendor communication rules: require contact record verification if last_updated > 60 days.',
    acknowledged: false,
  },
];

/* ── memory ─────────────────────────────────────────────────────────────── */

const MEM_KINDS: MemoryKind[] = ['episodic', 'decisional', 'semantic', 'procedural', 'relational'];

// Core hand-written memories
const coreMemories: MemoryRecord[] = [
  {
    id: 'mem_datastack_pricing',
    kind: 'semantic',
    subject: 'Datastack market pricing',
    content:
      'Current market for comparable Datastack tiers is ₹14,00,000–₹15,20,000/yr based on 3 public benchmarks and 1 comparable deal at a peer company. Datastack renewal quote of ₹18,40,000 is 22% above the market midpoint of ₹14,60,000.',
    domain: 'vendors',
    recordedAt: ago(DAY * 1),
    lastVerifiedAt: ago(HOUR * 6),
    retention: { policy: 'rolling', days: 90 },
    provenance: [
      { id: 'prov_ds_bench', label: 'SaaSIntelligence benchmark Q3-2024', source: 'SaaSIntelligence', observedAt: ago(DAY * 7) },
    ],
  },
  {
    id: 'mem_datastack_contact',
    kind: 'relational',
    subject: 'Datastack account management contact',
    content:
      'Current Account Manager: Riya Sharma (riya.sharma@datastack.io). Previous contact Vikram Malhotra changed roles in March 2024 — record was stale for 5 months before the mistake was caught.',
    domain: 'vendors',
    recordedAt: ago(DAY * 60),
    lastVerifiedAt: ago(DAY * 2),
    retention: { policy: 'rolling', days: 180 },
    provenance: [
      { id: 'prov_ds_contact', label: 'Direct confirmation from Riya Sharma', source: 'Email thread', observedAt: ago(DAY * 2) },
    ],
    supersedes: 'mem_datastack_contact_stale',
  },
  {
    id: 'mem_datastack_contact_stale',
    kind: 'relational',
    subject: 'Datastack account management contact (stale)',
    content:
      'Account Manager: Vikram Malhotra (vikram@datastack.io) — SUPERSEDED. Vikram changed roles March 2024. This record caused the missed outreach mistake.',
    domain: 'vendors',
    recordedAt: ago(DAY * 180),
    lastVerifiedAt: ago(DAY * 60),
    retention: { policy: 'rolling', days: 90 },
    provenance: [],
  },
  {
    id: 'mem_staff_eng_band',
    kind: 'decisional',
    subject: 'Staff Engineer compensation band',
    content:
      'Band set 14 months ago: ₹72,00,000–₹88,00,000 total comp. Midpoint ₹80,00,000. Market has moved since; Rohan Verma offer at ₹92,00,000 is 11% above midpoint. Band review scheduled for Q3 2025.',
    domain: 'hiring',
    recordedAt: ago(DAY * 14 * 30),
    lastVerifiedAt: ago(HOUR * 18),
    retention: { policy: 'rolling', days: 365 },
    provenance: [
      { id: 'prov_comp_v2', label: 'Compensation framework v2.1', source: 'HR system', observedAt: ago(DAY * 14 * 30) },
    ],
  },
  {
    id: 'mem_infra_service_count',
    kind: 'episodic',
    subject: 'Current microservices count',
    content:
      '8 services in production as of today. Industry threshold for managed Kubernetes overhead to justify cost is ~15 services. EKS recommended until service count exceeds 15.',
    domain: 'system',
    recordedAt: ago(DAY * 1),
    lastVerifiedAt: ago(HOUR * 2),
    retention: { policy: 'rolling', days: 30 },
    provenance: [
      { id: 'prov_infra_map', label: 'Service registry snapshot', source: 'Infra team', observedAt: ago(HOUR * 2) },
    ],
  },
  {
    id: 'mem_tooling_rule_history',
    kind: 'procedural',
    subject: 'Tooling renewal rule — approval history',
    content:
      '9 of 9 tooling renewals approved under ₹50,000 over 41 days. Median decision time 4 minutes. One rejection at ₹64,000 established the ceiling. Rule in trial status; proposal to graduate to active pending.',
    domain: 'vendors',
    recordedAt: ago(DAY * 41),
    lastVerifiedAt: ago(DAY * 1),
    retention: { policy: 'rolling', days: 180 },
    provenance: [],
  },
  {
    id: 'mem_saasboomi_roi',
    kind: 'episodic',
    subject: 'SaaSBoomi 2024 pipeline outcome',
    content:
      '12 qualified pipeline leads from SaaSBoomi Annual 2024 (Chennai). 3 converted to customers within 6 months. Estimated pipeline value ₹48,00,000. Booth cost ₹2,10,000. ROI positive.',
    domain: 'operations',
    recordedAt: ago(DAY * 180),
    lastVerifiedAt: ago(DAY * 30),
    retention: { policy: 'permanent' },
    provenance: [
      { id: 'prov_saasboomi', label: 'CRM pipeline report — SaaSBoomi 2024', source: 'CRM', observedAt: ago(DAY * 30) },
    ],
  },
  {
    id: 'mem_onkar_decision_style',
    kind: 'relational',
    subject: "Onkar's decision-making preferences",
    content:
      "Onkar approves financial decisions faster when given a clear recommendation with evidence and a deadline. Prefers single recommendation over a menu of options. Typically responds to needs-you items within 2–4 hours during working hours.",
    domain: 'operations',
    recordedAt: ago(DAY * 120),
    lastVerifiedAt: ago(DAY * 7),
    retention: { policy: 'permanent' },
    provenance: [],
  },
  {
    id: 'mem_priya_authority',
    kind: 'procedural',
    subject: 'Priya CFO approval authority',
    content:
      'Priya (CFO) has authority to approve invoices up to ₹5,00,000 without founder sign-off. Invoices above ₹2,00,000 routed to her per Rule rule_large_invoices_priya. Priya not available Fridays after 3pm.',
    domain: 'spend',
    recordedAt: ago(DAY * 90),
    lastVerifiedAt: ago(DAY * 14),
    retention: { policy: 'permanent' },
    provenance: [],
    contradicts: ['mem_priya_old_limit'],
  },
  {
    id: 'mem_priya_old_limit',
    kind: 'procedural',
    subject: 'Priya CFO approval authority (old limit)',
    content:
      'Priya (CFO) authority limit was ₹3,00,000 — CONTRADICTED by mem_priya_authority. Limit was raised to ₹5,00,000 in April 2024.',
    domain: 'spend',
    recordedAt: ago(DAY * 300),
    lastVerifiedAt: ago(DAY * 90),
    retention: { policy: 'rolling', days: 60 },
    provenance: [],
  },
  {
    id: 'mem_aws_reserved_pattern',
    kind: 'decisional',
    subject: 'AWS reserved instance purchasing pattern',
    content:
      'Bought reserved instances quarterly for last 3 quarters. Consistent 23% saving over on-demand. t3.medium instances fit the backend workload profile. Pattern supports autonomous approval under ₹50,000.',
    domain: 'spend',
    recordedAt: ago(DAY * 90),
    lastVerifiedAt: ago(DAY * 1),
    retention: { policy: 'rolling', days: 365 },
    provenance: [],
  },
  {
    id: 'mem_seat_utilisation_datastack',
    kind: 'semantic',
    subject: 'Datastack seat utilisation',
    content:
      'Trailing 90-day seat utilisation: 34%. Of 60 seats contracted, ~20 are active users. Negotiation leverage: significant overcapacity relative to actual usage.',
    domain: 'vendors',
    recordedAt: ago(HOUR * 6),
    lastVerifiedAt: ago(HOUR * 6),
    retention: { policy: 'rolling', days: 30 },
    provenance: [
      { id: 'prov_ds_usage', label: 'Datastack usage API export', source: 'Datastack', observedAt: ago(HOUR * 6) },
    ],
  },
];

// Programmatic bulk memories to hit 40+
const bulkMemories: MemoryRecord[] = [];
const memSubjects = [
  ['Notion workspace usage', 'semantic', 'vendors'],
  ['Loom video platform utilisation', 'semantic', 'vendors'],
  ['Intercom legacy plan underuse', 'semantic', 'vendors'],
  ['Q1 vendor spend summary', 'episodic', 'spend'],
  ['Q2 vendor spend summary', 'episodic', 'spend'],
  ['Contractor Meera Krishnan — SOW terms', 'procedural', 'spend'],
  ['Contractor Ravi Nair — SOW terms', 'procedural', 'spend'],
  ['Engineering hiring pipeline state', 'episodic', 'hiring'],
  ['Design team headcount plan', 'decisional', 'hiring'],
  ['Arjun — engineering authority scope', 'relational', 'system'],
  ['Deployment process — prod safeguards', 'procedural', 'system'],
  ['Customer data classification policy', 'semantic', 'legal'],
  ['GDPR compliance checklist', 'procedural', 'legal'],
  ['Annual leave calendar — Aug–Sep', 'episodic', 'operations'],
  ['Board meeting cadence', 'procedural', 'operations'],
  ['Product roadmap Q3 summary', 'semantic', 'product'],
  ['Feature flag policy', 'procedural', 'product'],
  ['Pricing page last update', 'episodic', 'product'],
  ['Security incident response plan', 'procedural', 'system'],
  ['On-call rotation August', 'procedural', 'system'],
  ['AWS cost centre breakdown', 'semantic', 'spend'],
  ['Figma licensing history', 'episodic', 'vendors'],
  ['GitHub Copilot seats — 45 of 50 active', 'semantic', 'vendors'],
  ['Linear project tracker — team adoption', 'semantic', 'system'],
  ['Mixpanel analytics plan', 'semantic', 'vendors'],
  ['Payroll vendor — Razorpay Payroll terms', 'procedural', 'spend'],
  ['Lease — Koramangala office expiry', 'decisional', 'legal'],
  ['Startup India DPIIT certification', 'semantic', 'legal'],
  ['Team offsites — budget history', 'episodic', 'operations'],
] as const;

for (let i = 0; i < memSubjects.length; i++) {
  const entry = memSubjects[i];
  if (!entry) continue;
  const [subject, kind, domain] = entry;
  bulkMemories.push({
    id: `mem_bulk_${i.toString().padStart(3, '0')}`,
    kind: kind as MemoryKind,
    subject,
    content: `Stored knowledge about ${subject}. Last verified within the retention window.`,
    domain: domain as DomainKey,
    recordedAt: ago(DAY * (10 + i * 2)),
    lastVerifiedAt: ago(DAY * (1 + (i % 7))),
    retention: i % 4 === 0 ? { policy: 'permanent' } : { policy: 'rolling', days: 90 + (i % 3) * 30 },
    provenance: [],
  });
}

export const seedMemory: readonly MemoryRecord[] = [...coreMemories, ...bulkMemories];

/* ── capabilities ────────────────────────────────────────────────────────── */

export const seedCapabilities: readonly Capability[] = [
  // Core classified
  {
    id: 'cap_vendor_invoice_approve',
    name: 'Approve vendor invoice',
    description: 'Mark a vendor invoice as approved and queue it for payment processing.',
    domain: 'vendors',
    reversibility: rev('reversible-until', fromNow(HOUR * 24), 'Cancel before payment processing begins'),
    status: 'available',
    invocations: 47,
    lastUsedAt: ago(DAY * 1),
    requiresJudgment: false,
  },
  {
    id: 'cap_vendor_renewal_approve',
    name: 'Approve SaaS renewal',
    description: 'Approve a recurring SaaS subscription renewal and trigger the payment.',
    domain: 'vendors',
    reversibility: rev('reversible-until', fromNow(DAY * 30), 'Cancel within standard refund window'),
    status: 'available',
    invocations: 31,
    lastUsedAt: ago(DAY * 3),
    requiresJudgment: false,
  },
  {
    id: 'cap_payment_initiate',
    name: 'Initiate bank transfer',
    description: 'Submit a payment via the banking API. Funds leave the account.',
    domain: 'spend',
    reversibility: rev('irreversible', 'Bank transfers cannot be recalled once submitted'),
    status: 'available',
    invocations: 23,
    lastUsedAt: ago(DAY * 1),
    requiresJudgment: true,
  },
  {
    id: 'cap_candidate_screen_schedule',
    name: 'Schedule candidate screening',
    description: 'Book initial screening calls for candidates and send calendar invites.',
    domain: 'hiring',
    reversibility: rev('reversible', 'Cancel calendar invite with 24h notice'),
    status: 'available',
    invocations: 14,
    lastUsedAt: ago(DAY * 10),
    requiresJudgment: false,
  },
  {
    id: 'cap_offer_extend',
    name: 'Extend job offer',
    description: 'Send a formal offer letter to a candidate with compensation details.',
    domain: 'hiring',
    reversibility: rev('reversible', 'Rescind offer before acceptance — standard 48h window'),
    status: 'available',
    invocations: 5,
    lastUsedAt: ago(DAY * 14),
    requiresJudgment: true,
  },
  {
    id: 'cap_contract_sign',
    name: 'Sign vendor contract',
    description: 'Countersign a vendor agreement via the e-signature integration.',
    domain: 'legal',
    reversibility: rev('irreversible', 'Executed contracts create binding obligations'),
    status: 'available',
    invocations: 3,
    lastUsedAt: ago(DAY * 30),
    requiresJudgment: true,
  },
  {
    id: 'cap_vendor_outreach',
    name: 'Contact vendor representative',
    description: 'Send email to a vendor contact for negotiation, support, or billing queries.',
    domain: 'vendors',
    reversibility: rev('reversible', 'Follow-up to clarify or retract'),
    status: 'available',
    invocations: 18,
    lastUsedAt: ago(DAY * 2),
    requiresJudgment: false,
  },
  {
    id: 'cap_report_generate',
    name: 'Generate spend or vendor report',
    description: 'Compile a report from internal data sources. Read-only, no side effects.',
    domain: 'spend',
    reversibility: rev('reversible', 'No side effects — report can be discarded'),
    status: 'available',
    invocations: 62,
    lastUsedAt: ago(HOUR * 8),
    requiresJudgment: false,
  },
  {
    id: 'cap_rule_fire',
    name: 'Execute standing rule action',
    description: 'Trigger the action prescribed by a standing rule without founder input.',
    domain: 'system',
    reversibility: rev('reversible', 'Actions log to receipt ledger; compensating actions available per capability'),
    status: 'available',
    invocations: 29,
    lastUsedAt: ago(DAY * 3),
    requiresJudgment: false,
  },
  {
    id: 'cap_alert_triage',
    name: 'Triage system alert',
    description: 'Classify incoming system alerts by severity and route to on-call.',
    domain: 'system',
    reversibility: rev('reversible', 'Routing can be overridden manually'),
    status: 'available',
    invocations: 88,
    lastUsedAt: ago(HOUR * 3),
    requiresJudgment: false,
  },
  {
    id: 'cap_crm_contact_update',
    name: 'Update CRM contact record',
    description: 'Write changes to a contact record in the CRM — name, role, email, phone.',
    domain: 'vendors',
    reversibility: rev('reversible', 'Previous record can be restored from CRM history'),
    status: 'available',
    invocations: 9,
    lastUsedAt: ago(DAY * 2),
    requiresJudgment: false,
  },
  {
    id: 'cap_customer_data_read',
    name: 'Read customer data record',
    description: 'Query the customer database for a specific record or segment.',
    domain: 'system',
    reversibility: rev('reversible', 'Read-only — no state change'),
    status: 'blocked',
    invocations: 0,
    requiresJudgment: true,
  },
  {
    id: 'cap_customer_data_export',
    name: 'Export customer data',
    description: 'Generate a data export of customer records for a given segment.',
    domain: 'system',
    reversibility: rev('irreversible', 'Data once exported cannot be unexported from recipient systems'),
    status: 'blocked',
    invocations: 0,
    requiresJudgment: true,
  },
  {
    id: 'cap_payroll_run',
    name: 'Run payroll',
    description: 'Submit payroll batch to Razorpay Payroll for processing.',
    domain: 'spend',
    reversibility: rev('irreversible', 'Payroll disbursements cannot be recalled'),
    status: 'available',
    invocations: 8,
    lastUsedAt: ago(DAY * 5),
    requiresJudgment: true,
  },
  {
    id: 'cap_calendar_invite',
    name: 'Send calendar invite',
    description: 'Create and send a Google Calendar invite to specified recipients.',
    domain: 'operations',
    reversibility: rev('reversible', 'Cancel or update the invite'),
    status: 'available',
    invocations: 34,
    lastUsedAt: ago(DAY * 1),
    requiresJudgment: false,
  },
  {
    id: 'cap_email_send',
    name: 'Send email',
    description: 'Send an email on behalf of a principal via the configured email account.',
    domain: 'operations',
    reversibility: rev('irreversible', 'Emails cannot be recalled once delivered'),
    status: 'available',
    invocations: 41,
    lastUsedAt: ago(HOUR * 5),
    requiresJudgment: false,
  },
  {
    id: 'cap_infra_provision',
    name: 'Provision cloud infrastructure',
    description: 'Run Terraform plan and apply to provision or modify cloud resources.',
    domain: 'system',
    reversibility: rev('reversible-until', fromNow(HOUR * 1), 'Destroy provisioned resources within 1 hour'),
    status: 'available',
    invocations: 6,
    lastUsedAt: ago(DAY * 7),
    requiresJudgment: true,
  },
  {
    id: 'cap_infra_destroy',
    name: 'Destroy cloud infrastructure',
    description: 'Run terraform destroy on a named stack.',
    domain: 'system',
    reversibility: rev('irreversible', 'Destroyed infra and associated data cannot be restored without backup'),
    status: 'available',
    invocations: 1,
    lastUsedAt: ago(DAY * 60),
    requiresJudgment: true,
  },
  {
    id: 'cap_document_generate',
    name: 'Generate document or contract draft',
    description: 'Use a template to generate a draft contract, SOW, or policy document.',
    domain: 'legal',
    reversibility: rev('reversible', 'Draft discarded until countersigned'),
    status: 'available',
    invocations: 12,
    lastUsedAt: ago(DAY * 4),
    requiresJudgment: false,
  },
  {
    id: 'cap_access_grant',
    name: 'Grant tool access',
    description: 'Provision access to an internal tool or SaaS workspace for a team member.',
    domain: 'system',
    reversibility: rev('reversible', 'Revoke access via the same integration'),
    status: 'available',
    invocations: 17,
    lastUsedAt: ago(DAY * 3),
    requiresJudgment: false,
  },
  {
    id: 'cap_access_revoke',
    name: 'Revoke tool access',
    description: 'Remove a team member from a tool workspace — permanent until re-granted.',
    domain: 'system',
    reversibility: rev('reversible', 'Re-grant access via cap_access_grant'),
    status: 'available',
    invocations: 4,
    lastUsedAt: ago(DAY * 14),
    requiresJudgment: false,
  },
  // Three unclassified capabilities (fail-closed)
  {
    id: 'cap_unclassified_audit_log_write',
    name: 'Write to audit log (external)',
    description: 'Append entries to the external compliance audit log via a third-party API. Reversibility not yet assessed.',
    domain: 'legal',
    reversibility: null,
    status: 'unclassified',
    invocations: 0,
    requiresJudgment: true,
  },
  {
    id: 'cap_unclassified_crm_bulk_update',
    name: 'Bulk-update CRM records',
    description: 'Run a bulk update across all CRM contact records matching a filter. Reversibility not yet assessed.',
    domain: 'vendors',
    reversibility: null,
    status: 'unclassified',
    invocations: 0,
    requiresJudgment: true,
  },
  {
    id: 'cap_unclassified_data_pipeline',
    name: 'Trigger data pipeline run',
    description: 'Manually trigger an ETL pipeline run. Downstream effects on dependent tables not fully mapped.',
    domain: 'system',
    reversibility: null,
    status: 'unclassified',
    invocations: 0,
    requiresJudgment: true,
  },
  // Additional classified capabilities
  {
    id: 'cap_feature_flag_toggle',
    name: 'Toggle feature flag',
    description: 'Enable or disable a product feature flag for a user segment or globally.',
    domain: 'product',
    reversibility: rev('reversible', 'Toggle flag back — takes effect within 60 seconds'),
    status: 'available',
    invocations: 22,
    lastUsedAt: ago(DAY * 2),
    requiresJudgment: false,
  },
];

/* ── attestation ─────────────────────────────────────────────────────────── */

export const seedAttestation: Attestation = {
  complete: true,
  at: ago(MIN * 12),
  domains: [
    { domain: 'vendors', lastCheckedAt: ago(MIN * 12), healthy: true },
    { domain: 'spend', lastCheckedAt: ago(MIN * 12), healthy: true },
    { domain: 'hiring', lastCheckedAt: ago(MIN * 14), healthy: true },
    { domain: 'operations', lastCheckedAt: ago(MIN * 10), healthy: true },
    { domain: 'legal', lastCheckedAt: ago(MIN * 15), healthy: true },
    { domain: 'product', lastCheckedAt: ago(MIN * 11), healthy: true },
    { domain: 'system', lastCheckedAt: ago(MIN * 9), healthy: true },
  ],
};

// Degraded attestation — used to demonstrate the degraded path in the UI
export const seedAttestationDegraded: Attestation = {
  complete: false,
  at: ago(MIN * 45),
  domains: [
    { domain: 'vendors', lastCheckedAt: ago(MIN * 45), healthy: true },
    { domain: 'spend', lastCheckedAt: ago(MIN * 45), healthy: true },
    { domain: 'hiring', lastCheckedAt: ago(MIN * 45), healthy: true },
    { domain: 'operations', lastCheckedAt: ago(MIN * 45), healthy: true },
    { domain: 'product', lastCheckedAt: ago(MIN * 45), healthy: true },
  ],
  gaps: [
    {
      domain: 'legal',
      lastCheckedAt: ago(DAY * 2 + HOUR * 3),
      healthy: false,
      note: 'Legal domain monitor has not reported in over 2 days — last check was before the weekend.',
    },
    {
      domain: 'system',
      lastCheckedAt: ago(HOUR * 4),
      healthy: true,
      note: 'System domain check is stale (> 2h threshold).',
    },
  ],
};

/* ── boundary state ──────────────────────────────────────────────────────── */

// 28 weekly history points showing rising autonomy 18% → 64%
function buildAutonomyHistory(): readonly { at: string; ratio: number }[] {
  const history: { at: string; ratio: number }[] = [];
  const startRatio = 0.18;
  const endRatio = 0.64;
  const points = 28;
  for (let i = 0; i < points; i++) {
    // Slight noise for realism
    const base = startRatio + ((endRatio - startRatio) * i) / (points - 1);
    const noise = (((i * 17 + 3) % 7) - 3) * 0.008;
    const ratio = Math.min(0.95, Math.max(0.05, base + noise));
    history.push({
      at: ago(DAY * 7 * (points - 1 - i)),
      ratio: Math.round(ratio * 1000) / 1000,
    });
  }
  return history;
}

export const seedBoundary: BoundaryState = {
  autonomyRatio: 0.64,
  delegatedDomains: ['vendors', 'spend', 'operations', 'system'],
  escalatedClasses: [
    'Any action touching customer data',
    'Contracts above ₹2,00,000',
    'New vendor relationships',
    'Hirings above Staff Engineer',
    'Spend in last 5 days of quarter',
  ],
  activeRuleCount: 5, // RULE_INTERVIEWS is paused
  suspended: false,
  history: buildAutonomyHistory(),
};

/* ── dependency audit ────────────────────────────────────────────────────── */

export const seedAudit: DependencyAudit = {
  year: 2025,
  generatedAt: ago(DAY * 30),
  unaskedAuthority: [
    'CRM bulk-update (cap_unclassified_crm_bulk_update) — reversibility unclassified, never invoked',
    'External audit log write (cap_unclassified_audit_log_write) — scope of downstream effects unclear',
    'Data pipeline trigger (cap_unclassified_data_pipeline) — downstream table dependencies not mapped',
  ],
  unexaminedRules: [RULE_INTERVIEWS],
  whatWouldBeLost: [
    'Tooling renewal handling for ~9 items/quarter, ~4 min average decision saved each',
    'Contractor invoice matching for 12 SOW-matched payments/quarter',
    'Large-invoice routing to Priya (4 items past 90 days)',
    'Candidate screening scheduling (paused — 7 past firings)',
  ],
  selfAssessedOverreach: [
    'Sentry double-approval in one week — tooling rule fired on a near-boundary case without flagging at time of action (now flagged retroactively)',
    'Datastack outreach to stale contact — CRM record not verified before action (see MistakeDisclosure)',
  ],
};

/* ── events (seed for recent event history) ──────────────────────────────── */

export const seedEvents: readonly KernelEvent[] = [
  {
    id: 'event_ds_research_done',
    type: 'mission.progress',
    at: ago(DAY * 1 + HOUR * 22),
    domain: 'vendors',
    line: 'Datastack market research complete — 22% above market, 34% seat utilisation confirmed.',
    signal: 'live',
    refs: { missionId: 'mission_datastack_renewal', receiptId: 'receipt_ds_002' },
  },
  {
    id: 'event_ds_judgment_opened',
    type: 'judgment.opened',
    at: ago(HOUR * 14),
    domain: 'vendors',
    line: 'Judgment request opened: Datastack renewal — counter-position or lock in before Friday?',
    signal: 'needs-you',
    refs: { requestId: 'req_datastack_verdict', missionId: 'mission_datastack_renewal' },
  },
  {
    id: 'event_hire_judgment_opened',
    type: 'judgment.opened',
    at: ago(HOUR * 18),
    domain: 'hiring',
    line: 'Judgment request opened: Staff Engineer offer above band — Wednesday deadline.',
    signal: 'needs-you',
    refs: { requestId: 'req_staff_eng_offer', missionId: 'mission_staff_eng_offer' },
  },
  {
    id: 'event_sentry_flagged',
    type: 'audit.flagged',
    at: ago(DAY * 3),
    domain: 'system',
    line: 'Self-audit flag: Sentry approved twice in one week under tooling rule — near-boundary pattern.',
    signal: 'risk',
    refs: { receiptId: 'receipt_sentry_flagged', ruleId: RULE_TOOLING },
  },
  {
    id: 'event_payroll_complete',
    type: 'mission.completed',
    at: ago(DAY * 4 + HOUR * 20),
    domain: 'spend',
    line: 'August payroll processed — ₹83,40,000 disbursed to 62 employees.',
    signal: 'done',
    refs: { missionId: 'mission_payroll_aug', receiptId: 'receipt_payroll_aug' },
  },
  {
    id: 'event_slack_renewal',
    type: 'rule.fired',
    at: ago(DAY * 8 + HOUR * 2),
    domain: 'vendors',
    line: 'Tooling rule fired: Slack Enterprise renewed at ₹3,12,000 — no founder input needed.',
    signal: 'done',
    refs: { missionId: 'mission_contract_renewal_slack', receiptId: 'receipt_slack_renewal', ruleId: RULE_TOOLING },
  },
  {
    id: 'event_proposal_raised',
    type: 'rule.proposed',
    at: ago(DAY * 1),
    domain: 'vendors',
    line: 'Rule proposal: 9 of 9 tooling renewals approved under ₹50,000 — ready to graduate to standing rule.',
    signal: 'live',
    refs: {},
  },
  {
    id: 'event_infra_mission_opened',
    type: 'mission.started',
    at: ago(DAY * 6),
    domain: 'system',
    line: 'Mission started: infra stack decision — EKS vs. managed Kubernetes, 2 engineers blocked.',
    signal: 'live',
    refs: { missionId: 'mission_infra_decision' },
  },
  {
    id: 'event_vendor_audit_started',
    type: 'mission.started',
    at: ago(HOUR * 8),
    domain: 'vendors',
    line: 'Quarterly vendor audit started — scanning 18 active contracts for utilisation.',
    signal: 'live',
    refs: { missionId: 'mission_vendor_audit' },
  },
  {
    id: 'event_mistake_disclosed',
    type: 'mistake.disclosed',
    at: ago(DAY * 60),
    domain: 'vendors',
    line: 'Mistake disclosed: wrong contact at Datastack — stale CRM record used for 3 outreach attempts.',
    signal: 'risk',
    refs: {},
  },
];
