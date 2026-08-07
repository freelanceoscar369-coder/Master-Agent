/**
 * TitleBar — 40px drag region at the top of the shell.
 *
 * Layout: wordmark left · presence sigil · window controls right.
 * Constitution: no centred text — content is left-aligned, controls right.
 *
 * DESKTOP SHELL NOTE:
 *   -webkit-app-region: drag / no-drag applies only when the app is running
 *   inside a Tauri or Electron host. In a plain browser context it has no
 *   effect and is safe to include.
 */

import React from 'react';
import { detectHost } from '@/kernel/desktop/bridge';
import { getDesktopBridge } from '@/kernel/desktop/bridge';
import { PresenceSigil } from './PresenceSigil';
import styles from './TitleBar.module.css';

/* ── Window controls — rendered only in desktop host ───────────────────── */

function WindowControls(): React.ReactElement {
  const bridge = getDesktopBridge();

  const handleMinimize = (): void => {
    void bridge.minimize();
  };

  const handleMaximize = (): void => {
    void bridge.maximize();
  };

  const handleClose = (): void => {
    void bridge.close();
  };

  return (
    <div className={styles.controls} aria-label="Window controls">
      <button
        type="button"
        className={styles.controlBtn}
        onClick={handleMinimize}
        aria-label="Minimize window"
        // no-drag: buttons must not participate in the drag region
      >
        <span className={styles.controlDot} data-action="minimize" />
      </button>
      <button
        type="button"
        className={styles.controlBtn}
        onClick={handleMaximize}
        aria-label="Maximize window"
      >
        <span className={styles.controlDot} data-action="maximize" />
      </button>
      <button
        type="button"
        className={styles.controlBtn}
        onClick={handleClose}
        aria-label="Close window"
      >
        <span className={styles.controlDot} data-action="close" />
      </button>
    </div>
  );
}

/* ── TitleBar ─────────────────────────────────────────────────────────────── */

export function TitleBar(): React.ReactElement {
  const host = detectHost();
  const isDesktop = host !== 'browser';

  return (
    <header className={styles.root} role="banner">
      {/* Left: wordmark + presence sigil — left-aligned per constitution */}
      <div className={styles.left}>
        <span className={styles.wordmark} aria-label="Kalpavriksha">
          KALPAVRIKSHA
        </span>
        <PresenceSigil />
      </div>

      {/* Right: window controls, only in desktop hosts */}
      {isDesktop && <WindowControls />}
    </header>
  );
}
