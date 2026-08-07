/**
 * NavRail — left navigation column.
 *
 * Reads the registry and renders routes grouped by ROUTE_GROUPS.
 * Each item: mono index + label, active = left 2px --signal-live border.
 *
 * /console count: fetched via useAsync(c => c.listJudgmentRequests()).
 * NOTE: This is a count of open judgment requests that the founder asked
 * to see — it is NOT a notification badge. The constitution forbids badges.
 * It is rendered as a plain mono number in --signal-needs-you.
 *
 * Bottom dock: theme switcher, density toggle, grid-overlay toggle (G key),
 * and the founder's initial from getPrincipal().
 */

import React, { useCallback } from 'react';
import { useKernel } from '@/kernel/KernelProvider';
import { useAsync } from '@/kernel/hooks';
import { Link, useLocation } from '@/app/router';
import { REGISTRY } from '@/app/registry';
import { ROUTE_GROUPS } from '@/app/routes';
import {
  THEMES,
  THEME_LABELS,
  DENSITIES,
  applyTheme,
  applyDensity,
  getStoredTheme,
  getStoredDensity,
  type ThemeName,
  type Density,
} from '@/state/theme';
import { useHotkey } from '@/state/prefs';
import styles from './NavRail.module.css';

/* ── judgment count ──────────────────────────────────────────────────────── */

function JudgmentCount(): React.ReactElement | null {
  const kernel = useKernel();
  const { data } = useAsync(
    useCallback(() => kernel.listJudgmentRequests(), [kernel]),
    [kernel],
  );
  if (data === undefined || data.length === 0) return null;
  return (
    // Plain mono number, not a badge — see module header note above.
    <span className={styles.judgmentCount} aria-label={`${data.length} open judgment requests`}>
      {data.length}
    </span>
  );
}

/* ── bottom dock items ────────────────────────────────────────────────────── */

function FounderInitial(): React.ReactElement {
  const kernel = useKernel();
  const { data } = useAsync(
    useCallback(() => kernel.getPrincipal(), [kernel]),
    [kernel],
  );
  const initial = data?.name.charAt(0).toUpperCase() ?? '—';
  return (
    <span className={styles.founderInitial} aria-label={data?.name ?? 'Founder'} title={data?.name}>
      {initial}
    </span>
  );
}

/* ── NavRail ──────────────────────────────────────────────────────────────── */

export function NavRail(): React.ReactElement {
  const { path } = useLocation();

  // Theme cycling
  const cycleTheme = useCallback((): void => {
    const current = getStoredTheme();
    const idx = THEMES.indexOf(current);
    const next: ThemeName = THEMES[(idx + 1) % THEMES.length] ?? 'midnight';
    applyTheme(next);
    // Force a re-render by triggering a storage event ourselves isn't practical
    // here without a state store. Since applyTheme writes to localStorage and
    // sets the data-theme attribute, the CSS tokens update immediately. A full
    // re-render of this component isn't necessary — the visual update is instant.
  }, []);

  // Density toggle
  const toggleDensity = useCallback((): void => {
    const current = getStoredDensity();
    const next: Density = current === 'comfortable' ? 'compact' : 'comfortable';
    applyDensity(next);
  }, []);

  // Grid overlay toggle — G key (global hotkey, not inside typing context)
  const toggleGrid = useCallback((): void => {
    document.body.classList.toggle('grid-on');
  }, []);

  useHotkey(
    (e) => e.key === 'g' || e.key === 'G',
    toggleGrid,
    [toggleGrid],
  );

  return (
    <nav className={styles.root} aria-label="Main navigation">
      <div className={styles.groups}>
        {ROUTE_GROUPS.map((group) => {
          const routes = REGISTRY.filter((r) => r.group === group.key);
          if (routes.length === 0) return null;
          return (
            <div key={group.key} className={styles.group}>
              <span className={styles.groupLabel}>{group.label}</span>
              <ul className={styles.list} role="list">
                {routes.map((route) => (
                  <li key={route.path} className={styles.item}>
                    <Link
                      to={route.path}
                      className={styles.link}
                      activeClassName={styles.linkActive}
                    >
                      <span className={styles.index}>{route.index}</span>
                      <span className={styles.label}>{route.label}</span>
                      {route.countKey === 'openRequests' && <JudgmentCount />}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>

      {/* Bottom dock */}
      <div className={styles.dock}>
        <button
          type="button"
          className={styles.dockBtn}
          onClick={cycleTheme}
          aria-label={`Cycle theme. Current: ${THEME_LABELS[getStoredTheme()]}`}
          title={`Theme: ${THEME_LABELS[getStoredTheme()]}`}
        >
          <span className={styles.dockBtnLabel}>TH</span>
        </button>
        <button
          type="button"
          className={styles.dockBtn}
          onClick={toggleDensity}
          aria-label={`Toggle density. Current: ${getStoredDensity()}`}
          title={`Density: ${getStoredDensity()}`}
        >
          <span className={styles.dockBtnLabel}>DN</span>
        </button>
        <button
          type="button"
          className={styles.dockBtn}
          onClick={toggleGrid}
          aria-label="Toggle grid overlay (G)"
          title="Grid overlay (G)"
        >
          <span className={styles.dockBtnLabel}>G</span>
        </button>
        <FounderInitial />
      </div>
    </nav>
  );
}
