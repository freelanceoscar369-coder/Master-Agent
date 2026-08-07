/**
 * AppShell — the full-screen CSS Grid frame.
 *
 * Grid areas:
 *   "titlebar titlebar" — 40px
 *   "nav      main"     — flex remainder
 *   "statusbar statusbar" — 32px
 *
 * The main region renders the active route's component via React.Suspense.
 * Unknown paths render NotFound.
 *
 * Responsive:
 *   ≤ 1180px — NavRail collapses to icons + index numbers
 *   ≤  860px — NavRail becomes a horizontal top bar
 * Both breakpoints are handled entirely inside NavRail.module.css so the
 * grid here only needs to swap the template at 860px.
 *
 * CommandBar is a transient-plane sheet anchored to the top of .main.
 * It uses position:absolute inside .mainWrapper so it overlays the content
 * without disturbing the grid.
 */

import React, { Suspense } from 'react';
import { useLocation } from '@/app/router';
import { REGISTRY } from '@/app/registry';
import { TitleBar } from './TitleBar';
import { NavRail } from './NavRail';
import { StatusBar } from './StatusBar';
import { CommandBar, useCommandBar } from './CommandBar';
import { NotFound } from './NotFound';
import styles from './AppShell.module.css';

/* ── Grid overlay helper ──────────────────────────────────────────────────── */

function GridGuides(): React.ReactElement {
  return (
    <div className="k-guides" aria-hidden="true">
      <div className="k-guides__labels">
        {Array.from({ length: 12 }, (_, i) => (
          <span key={i} className="k-guides__label">{i + 1}</span>
        ))}
      </div>
    </div>
  );
}

/* ── Route content ────────────────────────────────────────────────────────── */

function RouteContent(): React.ReactElement {
  const { path } = useLocation();
  const route = REGISTRY.find((r) => {
    if (r.path === '/') return path === '/';
    return path === r.path || path.startsWith(r.path + '/');
  });

  if (route === undefined) {
    return <NotFound />;
  }

  const { Component } = route;
  return <Component />;
}

/* ── AppShell ─────────────────────────────────────────────────────────────── */

export function AppShell(): React.ReactElement {
  const { open, onClose } = useCommandBar();

  return (
    <div className={styles.root}>
      <TitleBar />
      <NavRail />
      <div className={styles.mainWrapper}>
        {/* CommandBar: NOT a modal — transient-plane sheet at the top of the content area */}
        <CommandBar open={open} onClose={onClose} />

        <main className={styles.main} id="main-content">
          <div className={styles.contentWrap}>
            <Suspense fallback={<RouteLoadingFallback />}>
              <RouteContent />
            </Suspense>
          </div>
          <GridGuides />
        </main>
      </div>
      <StatusBar />
    </div>
  );
}

/* ── Loading fallback for lazy route chunks ───────────────────────────────── */

function RouteLoadingFallback(): React.ReactElement {
  return (
    <div className={styles.loadingFallback} aria-busy="true" aria-label="Loading">
      {/* Deliberate empty — no spinner per constitution. The shell is visible,
          the content area is blank while the chunk loads. */}
    </div>
  );
}
