/**
 * Desktop shell bridge.
 *
 * Runtime detection for Tauri and Electron without taking a compile-time
 * dependency on either framework. When running in a plain browser context,
 * all methods are safe no-ops.
 *
 * NOTE: No desktop framework has been chosen yet. This module is forward-
 * compatible with Tauri and Electron — wire the real implementations here
 * once the framework decision is made. Until then detectHost() returns
 * 'browser' and DesktopBridge methods are no-ops.
 */

/* ── module augmentation — no `any` ─────────────────────────────────────── */

declare global {
  interface Window {
    // Tauri injects __TAURI__ on the window before the page script runs.
    readonly __TAURI__?: {
      readonly invoke: (cmd: string, args?: Record<string, unknown>) => Promise<unknown>;
    };

    // Electron exposes process via its preload bridge (contextIsolation: true
    // means it's attached to window, not globalThis.process directly).
    readonly process?: {
      readonly versions?: {
        readonly electron?: string;
      };
    };
  }
}

/* ── host type ───────────────────────────────────────────────────────────── */

export type DesktopHost = 'tauri' | 'electron' | 'browser';

/** Detect the desktop shell at runtime. */
export function detectHost(): DesktopHost {
  if (typeof window === 'undefined') return 'browser';
  if (window.__TAURI__ !== undefined) return 'tauri';
  if (window.process?.versions?.electron !== undefined) return 'electron';
  return 'browser';
}

/* ── window state ────────────────────────────────────────────────────────── */

export interface WindowState {
  readonly fullscreen: boolean;
  readonly maximized: boolean;
  readonly focused: boolean;
}

export type WindowStateCallback = (state: WindowState) => void;

/* ── the bridge interface ────────────────────────────────────────────────── */

export interface DesktopBridge {
  readonly host: DesktopHost;
  minimize(): Promise<void>;
  maximize(): Promise<void>;
  close(): Promise<void>;
  isFullscreen(): Promise<boolean>;
  /** Returns an unsubscribe function. */
  onWindowStateChange(fn: WindowStateCallback): () => void;
}

/* ── browser (no-op) implementation ─────────────────────────────────────── */

function noop(): Promise<void> {
  return Promise.resolve();
}

const browserBridge: DesktopBridge = {
  host: 'browser',
  minimize: noop,
  maximize: noop,
  close: noop,
  isFullscreen: () => Promise.resolve(document.fullscreenElement !== null),
  onWindowStateChange: (_fn: WindowStateCallback) => {
    // No window state change events in a plain browser context.
    return () => undefined;
  },
};

/* ── Tauri placeholder ───────────────────────────────────────────────────── */

// Wire real Tauri commands here once @tauri-apps/api is installed.
// Each invoke() call maps to a Rust command in src-tauri/src/main.rs.
function createTauriBridge(): DesktopBridge {
  const tauri = window.__TAURI__;
  if (!tauri) return browserBridge;

  return {
    host: 'tauri',
    minimize: () => tauri.invoke('minimize_window').then(() => undefined),
    maximize: () => tauri.invoke('maximize_window').then(() => undefined),
    close: () => tauri.invoke('close_window').then(() => undefined),
    isFullscreen: () =>
      tauri.invoke('is_fullscreen').then((v) => (v === true ? true : false)),
    onWindowStateChange: (_fn: WindowStateCallback) => {
      // TODO: wire tauri.event.listen('window-state-changed', fn) here.
      return () => undefined;
    },
  };
}

/* ── Electron placeholder ────────────────────────────────────────────────── */

// Wire real Electron IPC here once contextBridge API is installed in preload.
// Shape: window.electronAPI = { minimize, maximize, close, isFullscreen, onWindowState }
function createElectronBridge(): DesktopBridge {
  return {
    host: 'electron',
    minimize: noop,
    maximize: noop,
    close: noop,
    isFullscreen: () => Promise.resolve(false),
    onWindowStateChange: (_fn: WindowStateCallback) => {
      // TODO: wire window.electronAPI.onWindowState(fn) here.
      return () => undefined;
    },
  };
}

/* ── factory ─────────────────────────────────────────────────────────────── */

let _bridge: DesktopBridge | null = null;

/**
 * Returns the singleton DesktopBridge for the current host.
 * Safe to call before the DOM is fully loaded.
 */
export function getDesktopBridge(): DesktopBridge {
  if (_bridge !== null) return _bridge;

  const host = detectHost();
  switch (host) {
    case 'tauri':
      _bridge = createTauriBridge();
      break;
    case 'electron':
      _bridge = createElectronBridge();
      break;
    case 'browser':
    default:
      _bridge = browserBridge;
  }

  return _bridge;
}
