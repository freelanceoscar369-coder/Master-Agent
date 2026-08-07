/**
 * The route table. This is the single place a new section is registered —
 * the nav rail, the command bar and the router all read from it, so adding a
 * screen is one entry here plus one component.
 *
 * `gate` records the Bible §12 justification for the screen's existence:
 *   'explains'  — it explains what the AI did
 *   'judgment'  — it requests human judgment
 *   'operator'  — operator/inspection surface, not founder-facing
 * A route with no gate cannot be added. See docs/ARCHITECTURE.md.
 */

import type { ComponentType } from 'react';

export interface RouteDef {
  readonly path: string;
  /** Two-character mono index shown in the collapsed rail. */
  readonly index: string;
  readonly label: string;
  /** One line, shown in the command bar. */
  readonly hint: string;
  readonly gate: 'explains' | 'judgment' | 'operator';
  readonly group: 'founder' | 'operate' | 'inspect';
  readonly Component: ComponentType;
  /** Optional live count badge source. Deliberately NOT a notification badge —
   *  it is a count of open judgment, which the founder asked to see. */
  readonly countKey?: 'openRequests';
}

/** Registered in src/app/registry.tsx to avoid a circular import with features. */
export type RouteRegistry = readonly RouteDef[];

export const ROUTE_GROUPS: ReadonlyArray<{ key: RouteDef['group']; label: string }> = [
  { key: 'founder', label: 'Founder' },
  { key: 'operate', label: 'Operate' },
  { key: 'inspect', label: 'Inspect' },
];
