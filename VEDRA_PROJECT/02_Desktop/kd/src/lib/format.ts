/**
 * Pure formatting helpers — no imports beyond kernel types.
 *
 * All output is founder-readable prose, never machine strings.
 * The Indian grouping convention for INR (₹18,40,000) is enforced via
 * Intl.NumberFormat with locale 'en-IN'.
 */
import type { Money, Reversibility } from '@/kernel/types';

/* ── money ──────────────────────────────────────────────────────────────── */

/** Full INR display with Indian grouping: ₹18,40,000 */
export function formatMoney(m: Money): string {
  const major = m.minor / 100;
  if (m.currency === 'INR') {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(major);
  }
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: m.currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(major);
}

/**
 * Compact form for tight UI: ₹18.4L, ₹92L, ₹34K.
 * Stays founder-legible — uses Indian short-scale (lakh, crore) for INR.
 */
export function formatMoneyCompact(m: Money): string {
  const major = m.minor / 100;
  if (m.currency !== 'INR') {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: m.currency,
      notation: 'compact',
      maximumSignificantDigits: 3,
    }).format(major);
  }
  // Indian short scale.
  if (major >= 1_00_00_000) {
    return `₹${(major / 1_00_00_000).toFixed(1).replace(/\.0$/, '')}Cr`;
  }
  if (major >= 1_00_000) {
    return `₹${(major / 1_00_000).toFixed(1).replace(/\.0$/, '')}L`;
  }
  if (major >= 1_000) {
    return `₹${(major / 1_000).toFixed(1).replace(/\.0$/, '')}K`;
  }
  return formatMoney(m);
}

/* ── reversibility ──────────────────────────────────────────────────────── */

/** Human sentence for the reversibility classification. */
export function formatReversibility(r: Reversibility): string {
  switch (r.kind) {
    case 'reversible':
      return `Reversible — ${r.compensatingAction}`;
    case 'reversible-until': {
      const deadline = formatRelative(r.until);
      return `Reversible ${deadline} — ${r.compensatingAction}`;
    }
    case 'irreversible':
      return `Cannot be undone — ${r.reason}`;
  }
}

/* ── time ───────────────────────────────────────────────────────────────── */

const MINUTE = 60;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

/**
 * Relative time from now. Returns prose fragments like:
 *   "just now", "4 min ago", "14h 22m ago", "in 3 days", "in 4 hours"
 */
export function formatRelative(iso: string): string {
  const diff = (new Date(iso).getTime() - Date.now()) / 1000; // seconds, positive = future
  const abs = Math.abs(diff);
  const past = diff < 0;

  let fragment: string;

  if (abs < 60) {
    fragment = 'just now';
    return fragment;
  } else if (abs < HOUR) {
    const mins = Math.round(abs / MINUTE);
    fragment = `${mins} min`;
  } else if (abs < DAY) {
    const hrs = Math.floor(abs / HOUR);
    const mins = Math.floor((abs % HOUR) / MINUTE);
    fragment = mins > 0 ? `${hrs}h ${mins}m` : `${hrs}h`;
  } else if (abs < 7 * DAY) {
    const days = Math.round(abs / DAY);
    fragment = `${days} ${days === 1 ? 'day' : 'days'}`;
  } else {
    // Beyond a week: absolute date is clearer.
    return new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short' }).format(
      new Date(iso),
    );
  }

  return past ? `${fragment} ago` : `in ${fragment}`;
}

/** Formatted clock time, optionally in a named timezone. */
export function formatClock(iso: string, tz?: string): string {
  const opts: Intl.DateTimeFormatOptions = {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  };
  if (tz !== undefined) {
    opts.timeZone = tz;
    opts.timeZoneName = 'short';
  }
  return new Intl.DateTimeFormat('en-IN', opts).format(new Date(iso));
}

/**
 * Duration in human terms. Input is seconds.
 * "3 days 2h", "14h 22m", "45 min", "30s"
 */
export function formatDuration(seconds: number): string {
  if (seconds < MINUTE) return `${Math.round(seconds)}s`;
  if (seconds < HOUR) return `${Math.round(seconds / MINUTE)} min`;

  const days = Math.floor(seconds / DAY);
  const hrs = Math.floor((seconds % DAY) / HOUR);
  const mins = Math.floor((seconds % HOUR) / MINUTE);

  if (days > 0) {
    return hrs > 0 ? `${days} ${days === 1 ? 'day' : 'days'} ${hrs}h` : `${days} ${days === 1 ? 'day' : 'days'}`;
  }
  return mins > 0 ? `${hrs}h ${mins}m` : `${hrs}h`;
}

/* ── simple scalars ─────────────────────────────────────────────────────── */

/** 0–1 fraction → "34%" */
export function formatPercent(n: number): string {
  return `${Math.round(n * 100)}%`;
}

/** Integer count with commas: 1,240 */
export function formatCount(n: number): string {
  return new Intl.NumberFormat('en-IN').format(n);
}
