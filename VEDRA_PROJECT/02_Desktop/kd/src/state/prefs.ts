/** Small, typed localStorage-backed preferences. No dependency, no store lib. */

import { useCallback, useEffect, useState } from 'react';

export function usePref<T extends string | boolean | number>(
  key: string,
  fallback: T,
): [T, (v: T) => void] {
  const full = `kalpa.${key}`;
  const [value, setValue] = useState<T>(() => {
    if (typeof localStorage === 'undefined') return fallback;
    const raw = localStorage.getItem(full);
    if (raw === null) return fallback;
    try { return JSON.parse(raw) as T; } catch { return fallback; }
  });
  const set = useCallback((v: T) => {
    setValue(v);
    try { localStorage.setItem(full, JSON.stringify(v)); } catch { /* ignore */ }
  }, [full]);
  return [value, set];
}

/** Global keyboard shortcut binding, cleaned up on unmount. */
export function useHotkey(
  match: (e: KeyboardEvent) => boolean,
  handler: (e: KeyboardEvent) => void,
  deps: unknown[] = [],
): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      const typing = !!t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable);
      if (typing && e.key !== 'Escape' && !(e.metaKey || e.ctrlKey)) return;
      if (match(e)) { handler(e); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
