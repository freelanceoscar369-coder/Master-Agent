/**
 * Application root.
 *
 * Composition order:
 *   ErrorBoundary (catches render errors — a React class component requirement)
 *   └── KernelProvider (kernel client lifetime)
 *       └── RouterProvider (hash router)
 *           └── AppShell (layout + routing)
 */

import React, { Component, type ErrorInfo, type ReactNode } from 'react';
import { KernelProvider } from '@/kernel/KernelProvider';
import { RouterProvider } from '@/app/router';
import { AppShell } from '@/app/shell';

/* ── ErrorBoundary ────────────────────────────────────────────────────────── */

interface ErrorBoundaryState {
  readonly caught: boolean;
  readonly message: string;
}

interface ErrorBoundaryProps {
  readonly children: ReactNode;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { caught: false, message: '' };
  }

  static getDerivedStateFromError(error: unknown): ErrorBoundaryState {
    const message =
      error instanceof Error
        ? error.message
        : 'An unexpected error occurred.';
    return { caught: true, message };
  }

  override componentDidCatch(error: unknown, info: ErrorInfo): void {
    // Log to console only — no analytics, no external reporting here.
    console.error('[ErrorBoundary] Caught render error:', error, info.componentStack);
  }

  private handleReload = (): void => {
    window.location.reload();
  };

  override render(): ReactNode {
    if (!this.state.caught) {
      return this.props.children;
    }

    return (
      <div className="error-boundary-root" role="alert">
        <div className="error-boundary-inner">
          <p className="error-boundary-kicker">something went wrong</p>
          <p className="error-boundary-message">{this.state.message}</p>
          <p className="error-boundary-sub">
            The application encountered an error it could not recover from.
            Your data is intact. Reload to try again.
          </p>
          <button
            type="button"
            className="error-boundary-reload"
            onClick={this.handleReload}
          >
            Reload
          </button>
        </div>

        {/* Inline styles: the CSS files may not have loaded if the error is early. */}
        <style>{`
          .error-boundary-root {
            display: flex;
            align-items: center;
            justify-content: flex-start;
            min-height: 100dvh;
            padding: 64px 48px;
            background-color: #05070a;
            color: #e9eff5;
            font-family: 'Inter', system-ui, sans-serif;
          }
          .error-boundary-inner {
            max-width: 480px;
          }
          .error-boundary-kicker {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 11px;
            line-height: 16px;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #ff6b6b;
            margin-bottom: 16px;
          }
          .error-boundary-message {
            font-size: 19px;
            line-height: 32px;
            font-weight: 500;
            margin-bottom: 16px;
          }
          .error-boundary-sub {
            font-size: 15px;
            line-height: 24px;
            color: #9fb0bf;
            margin-bottom: 32px;
          }
          .error-boundary-reload {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 12px;
            line-height: 24px;
            background: transparent;
            border: 1px solid rgba(150, 190, 220, 0.16);
            color: #e9eff5;
            padding: 8px 16px;
            cursor: pointer;
            letter-spacing: 0.04em;
          }
          .error-boundary-reload:hover {
            border-color: rgba(150, 190, 220, 0.30);
          }
          .error-boundary-reload:focus-visible {
            outline: 2px solid #7fd3ff;
            outline-offset: 2px;
          }
        `}</style>
      </div>
    );
  }
}

/* ── App ──────────────────────────────────────────────────────────────────── */

export default function App(): React.ReactElement {
  return (
    <ErrorBoundary>
      <KernelProvider>
        <RouterProvider>
          <AppShell />
        </RouterProvider>
      </KernelProvider>
    </ErrorBoundary>
  );
}
