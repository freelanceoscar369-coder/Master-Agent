/**
 * React context for the KernelClient.
 *
 * Usage:
 *   <KernelProvider>          — uses createKernel() from the environment
 *   <KernelProvider client={myClient}>   — inject a specific client (testing)
 *
 * The client is created once (via useRef) and disposed on unmount.
 */

import React, { createContext, useContext, useEffect, useRef, type ReactNode } from 'react';
import type { KernelClient } from './client';
import { createKernel } from './index';

/* ── context ─────────────────────────────────────────────────────────────── */

const KernelContext = createContext<KernelClient | null>(null);
KernelContext.displayName = 'KernelContext';

/* ── provider props ──────────────────────────────────────────────────────── */

interface KernelProviderProps {
  readonly children: ReactNode;
  /**
   * Inject a specific client. When omitted, createKernel() is called once and
   * the result is disposed on unmount.
   */
  readonly client?: KernelClient;
}

/* ── provider ────────────────────────────────────────────────────────────── */

export function KernelProvider({ children, client: injected }: KernelProviderProps): React.ReactElement {
  // When no client is injected, create one on first render and dispose on unmount.
  const ownedRef = useRef<KernelClient | null>(null);

  if (injected === undefined && ownedRef.current === null) {
    ownedRef.current = createKernel();
  }

  const client = injected ?? ownedRef.current;

  useEffect(() => {
    // Only dispose clients we created — not injected ones (the caller owns those).
    return () => {
      if (injected === undefined && ownedRef.current !== null) {
        ownedRef.current.dispose();
        ownedRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentionally empty: client lifetime matches component lifetime
  }, []);

  if (client === null) {
    // Should be unreachable, but TypeScript needs the guard.
    throw new Error('KernelProvider: client could not be initialised.');
  }

  return (
    <KernelContext.Provider value={client}>
      {children}
    </KernelContext.Provider>
  );
}

/* ── consumer hook ───────────────────────────────────────────────────────── */

/**
 * Returns the KernelClient from the nearest KernelProvider.
 * Throws when called outside a KernelProvider.
 */
export function useKernel(): KernelClient {
  const client = useContext(KernelContext);
  if (client === null) {
    throw new Error(
      'useKernel() was called outside of a <KernelProvider>. ' +
      'Wrap your app (or the component tree) with <KernelProvider>.',
    );
  }
  return client;
}
