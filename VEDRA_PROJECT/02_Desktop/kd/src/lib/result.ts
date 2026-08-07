/**
 * Utilities over the Result<T> type from kernel/client.ts.
 *
 * Imported widely — keep this dependency-free.
 */
import type { Result, KernelError } from '@/kernel/client';

/** Unwrap the value or return the fallback. */
export function unwrapOr<T>(r: Result<T>, fallback: T): T {
  return r.ok ? r.value : fallback;
}

/** Transform the success branch; propagate the error branch unchanged. */
export function mapResult<T, U>(
  r: Result<T>,
  fn: (v: T) => U,
): Result<U> {
  if (r.ok) {
    return { ok: true, value: fn(r.value) };
  }
  return r;
}

/** Narrow a Result to the success branch. */
export function isOk<T>(r: Result<T>): r is { readonly ok: true; readonly value: T } {
  return r.ok;
}

/** Narrow a Result to the error branch. */
export function isErr<T>(
  r: Result<T>,
): r is { readonly ok: false; readonly error: KernelError } {
  return !r.ok;
}

/** Chain two result-returning operations. */
export function chainResult<T, U>(
  r: Result<T>,
  fn: (v: T) => Result<U>,
): Result<U> {
  if (r.ok) {
    return fn(r.value);
  }
  return r;
}
