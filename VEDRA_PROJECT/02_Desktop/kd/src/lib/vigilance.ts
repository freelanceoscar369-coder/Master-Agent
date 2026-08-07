/**
 * Vigilance gate — Bible §1, module D7.
 *
 * The "calm" sentence ("everything is handled, nothing needs you") is
 * unconstructable without passing this gate. A degraded attestation means the
 * system has not verified all domains and must name the gap instead.
 *
 * No imports beyond the type. This module has no side effects.
 */
import type { Attestation, DomainCoverage } from '@/kernel/types';

/**
 * Type guard: true only when the attestation covers every domain and none are
 * flagged as unhealthy. Only then may the UI surface the calm sentence.
 *
 * Call site pattern:
 *   if (canClaimCalm(attestation)) {
 *     // safe to render "Everything is handled."
 *   } else {
 *     // must render describeGaps(attestation)
 *   }
 */
export function canClaimCalm(
  a: Attestation,
): a is Extract<Attestation, { complete: true }> {
  if (!a.complete) return false;
  // All domains must be healthy — unhealthy domains prevent the calm claim even
  // when structural completeness is satisfied.
  return a.domains.every((d) => d.healthy);
}

/**
 * Returns a human-readable sentence naming the gap(s), or null when the
 * attestation is complete and all domains are healthy.
 *
 * Returned string is a founder-readable prose fragment, never a machine string.
 */
export function describeGaps(a: Attestation): string | null {
  if (!a.complete) {
    const unhealthy = a.gaps.filter((d) => !d.healthy);
    const stale = a.gaps.filter((d) => d.healthy);

    const parts: string[] = [];

    if (unhealthy.length > 0) {
      const names = humanList(unhealthy.map(domainLabel));
      parts.push(`${names} ${unhealthy.length === 1 ? 'is' : 'are'} reporting problems`);
    }
    if (stale.length > 0) {
      const names = humanList(stale.map(domainLabel));
      parts.push(`${names} ${stale.length === 1 ? 'has' : 'have'} not been checked recently`);
    }

    if (parts.length === 0) {
      // Gaps array exists but all entries appear fine — still not complete.
      return 'Some domains could not be verified.';
    }
    return capitalize(parts.join(' and ')) + '.';
  }

  // Structurally complete — check for unhealthy domains.
  const unhealthy = a.domains.filter((d) => !d.healthy);
  if (unhealthy.length > 0) {
    const names = humanList(unhealthy.map(domainLabel));
    return `${capitalize(names)} ${unhealthy.length === 1 ? 'is' : 'are'} reporting problems.`;
  }

  return null;
}

/* ── helpers ────────────────────────────────────────────────────────────── */

function domainLabel(d: DomainCoverage): string {
  const labels: Record<string, string> = {
    vendors: 'Vendors',
    spend: 'Spend',
    hiring: 'Hiring',
    operations: 'Operations',
    legal: 'Legal',
    product: 'Product',
    system: 'System',
  };
  return labels[d.domain] ?? d.domain;
}

function humanList(items: readonly string[]): string {
  if (items.length === 0) return '';
  if (items.length === 1) return items[0] ?? '';
  if (items.length === 2) return `${items[0] ?? ''} and ${items[1] ?? ''}`;
  const last = items[items.length - 1] ?? '';
  const rest = items.slice(0, -1);
  return `${rest.join(', ')}, and ${last}`;
}

function capitalize(s: string): string {
  if (s.length === 0) return s;
  return s.charAt(0).toUpperCase() + s.slice(1);
}
