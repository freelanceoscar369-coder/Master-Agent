/**
 * Shared helper: human label + signal tone for an Actor discriminated union.
 * Used by LedgerExplorer and any other screen that displays Actor provenance.
 */
import type { Signal } from '@/kernel/types';
import type { Actor } from '@/kernel/types';

export interface ActorDisplay {
  readonly label: string;
  readonly tone: Signal | 'muted';
}

export function actorDisplay(actor: Actor): ActorDisplay {
  switch (actor.kind) {
    case 'kernel':
      return { label: 'kernel', tone: 'live' };
    case 'rule':
      return { label: 'rule', tone: 'done' };
    case 'founder':
      return { label: 'founder', tone: 'needs-you' };
    case 'delegate':
      return { label: 'delegate', tone: 'muted' };
  }
}
