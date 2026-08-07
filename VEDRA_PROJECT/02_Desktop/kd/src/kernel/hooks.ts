/**
 * Data hooks for Kernel state.
 *
 * Dependency-free (no react-query, no SWR). Each hook is self-contained and
 * safe to use across React 18 strict mode (double-invocation in dev).
 *
 * Race condition handling: every async operation is guarded by a request
 * sequence counter. Stale responses from superseded requests are discarded.
 *
 * Unmount safety: effects clean up via the `alive` flag pattern.
 */

import {
  useCallback,
  useEffect,
  useReducer,
  useRef,
  useState,
} from 'react';

import type { KernelClient, KernelError, Result, StreamStatus } from './client';
import type { KernelEvent, PresenceState } from './types';
import { useKernel } from './KernelProvider';

/* ── useAsync ────────────────────────────────────────────────────────────── */

export interface AsyncState<T> {
  readonly data: T | undefined;
  readonly error: KernelError | undefined;
  readonly loading: boolean;
  readonly reload: () => void;
}

type AsyncAction<T> =
  | { type: 'loading' }
  | { type: 'ok'; value: T }
  | { type: 'err'; error: KernelError };

function asyncReducer<T>(
  state: AsyncState<T>,
  action: AsyncAction<T>,
): AsyncState<T> {
  switch (action.type) {
    case 'loading':
      return { ...state, loading: true, error: undefined };
    case 'ok':
      return { data: action.value, error: undefined, loading: false, reload: state.reload };
    case 'err':
      return { ...state, error: action.error, loading: false };
  }
}

/**
 * Run an async function that returns a Result<T> and manage its loading/error
 * state. Re-runs when `deps` change or `reload()` is called.
 *
 * Race condition guard: if a newer call starts before an older one resolves,
 * the older result is silently discarded.
 */
export function useAsync<T>(
  fn: () => Promise<Result<T>>,
  deps: readonly unknown[],
): AsyncState<T> {
  const seqRef = useRef(0);

  // We need reload to be stable — wrap it in a ref so the dispatch can be called
  // without causing the reducer to see a stale reload.
  const reloadRef = useRef<() => void>(() => undefined);

  const [state, dispatch] = useReducer(asyncReducer<T>, {
    data: undefined,
    error: undefined,
    loading: true,
    reload: () => reloadRef.current(),
  });

  const run = useCallback(async () => {
    const seq = ++seqRef.current;
    dispatch({ type: 'loading' });

    const result = await fn();

    if (seq !== seqRef.current) return; // stale — discard

    if (result.ok) {
      dispatch({ type: 'ok', value: result.value });
    } else {
      dispatch({ type: 'err', error: result.error });
    }
    // fn is intentionally excluded — callers pass stable refs or inline fns.
    // The deps array controls re-running.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  reloadRef.current = run;

  useEffect(() => {
    let alive = true;
    seqRef.current++;

    void (async () => {
      const seq = seqRef.current;
      dispatch({ type: 'loading' });
      const result = await fn();
      if (!alive) return;
      if (seq !== seqRef.current) return;

      if (result.ok) {
        dispatch({ type: 'ok', value: result.value });
      } else {
        dispatch({ type: 'err', error: result.error });
      }
    })();

    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { ...state, reload: run };
}

/* ── useKernelEvents ─────────────────────────────────────────────────────── */

const DEFAULT_EVENT_LIMIT = 100;

/**
 * Seeds from getRecentEvents then appends live events via subscribeEvents.
 * Maintains a capped ring buffer of `limit` events, newest first.
 */
export function useKernelEvents(limit: number = DEFAULT_EVENT_LIMIT): readonly KernelEvent[] {
  const kernel = useKernel();
  const [events, setEvents] = useState<readonly KernelEvent[]>([]);
  const limitRef = useRef(limit);
  limitRef.current = limit;

  useEffect(() => {
    let alive = true;

    // Seed from recent events
    void kernel.getRecentEvents(limit).then((result) => {
      if (!alive) return;
      if (result.ok) {
        setEvents(result.value.slice(0, limit));
      }
    });

    // Subscribe to live events
    const unsub = kernel.subscribeEvents((event) => {
      if (!alive) return;
      setEvents((prev) => {
        const next = [event, ...prev];
        return next.slice(0, limitRef.current);
      });
    });

    return () => {
      alive = false;
      unsub();
    };
  }, [kernel, limit]);

  return events;
}

/* ── useStreamStatus ─────────────────────────────────────────────────────── */

/** Subscribe to the stream connection status. */
export function useStreamStatus(): StreamStatus {
  const kernel = useKernel();
  const [status, setStatus] = useState<StreamStatus>(() => kernel.streamStatus());

  useEffect(() => {
    const unsub = kernel.subscribeStreamStatus(setStatus);
    return unsub;
  }, [kernel]);

  return status;
}

/* ── usePresence ─────────────────────────────────────────────────────────── */

/** Subscribe to the Kernel's presence state. */
export function usePresence(): PresenceState {
  const kernel = useKernel();
  const [presence, setPresence] = useState<PresenceState>('idle');

  useEffect(() => {
    const unsub = kernel.subscribePresence(setPresence);
    return unsub;
  }, [kernel]);

  return presence;
}

/* ── useMutation ─────────────────────────────────────────────────────────── */

export interface MutationState<A, R> {
  readonly run: (arg: A) => Promise<Result<R>>;
  readonly pending: boolean;
  readonly error: KernelError | undefined;
}

/**
 * Wraps a mutation function in pending/error state management.
 *
 * Example:
 *   const { run, pending, error } = useMutation(
 *     (client, id: RequestId) => client.submitVerdict(id, { kind: 'approve' })
 *   );
 */
export function useMutation<A, R>(
  fn: (client: KernelClient, arg: A) => Promise<Result<R>>,
): MutationState<A, R> {
  const kernel = useKernel();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<KernelError | undefined>(undefined);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const run = useCallback(
    async (arg: A): Promise<Result<R>> => {
      setPending(true);
      setError(undefined);

      const result = await fn(kernel, arg);

      if (mountedRef.current) {
        setPending(false);
        if (!result.ok) {
          setError(result.error);
        }
      }

      return result;
    },
    // fn is intentionally excluded from deps — callers are expected to pass
    // a stable reference (module-level or useMemo'd).
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [kernel],
  );

  return { run, pending, error };
}
