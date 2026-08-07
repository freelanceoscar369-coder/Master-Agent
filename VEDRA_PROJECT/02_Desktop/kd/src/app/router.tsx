/**
 * A ~90 line hash router.
 *
 * Why not react-router: this app has seven flat routes and one optional detail
 * segment. A routing library would be the largest dependency in the tree and
 * would buy nothing. Hash routing also means the built bundle works unchanged
 * from a `file://` URL inside a desktop shell, where history routing needs a
 * custom protocol handler.
 *
 * Replace this file if the route graph ever becomes genuinely nested.
 */

import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
  type ReactNode,
} from 'react';

export interface Location {
  /** e.g. "/missions" */
  readonly path: string;
  /** e.g. "MSN-2294" — the optional detail segment after the section */
  readonly detail?: string;
  readonly query: Readonly<Record<string, string>>;
}

interface RouterValue {
  readonly location: Location;
  navigate(to: string, opts?: { replace?: boolean }): void;
  back(): void;
}

const RouterContext = createContext<RouterValue | null>(null);

function parseHash(hash: string): Location {
  const raw = hash.replace(/^#/, '') || '/';
  const [pathPart = '/', queryPart = ''] = raw.split('?');
  const query: Record<string, string> = {};
  if (queryPart) {
    for (const pair of queryPart.split('&')) {
      const [k, v] = pair.split('=');
      if (k) query[decodeURIComponent(k)] = decodeURIComponent(v ?? '');
    }
  }
  const segments = pathPart.split('/').filter(Boolean);
  const section = segments[0] ? `/${segments[0]}` : '/';
  const detail = segments[1] ? decodeURIComponent(segments[1]) : undefined;
  return detail === undefined
    ? { path: section, query }
    : { path: section, detail, query };
}

export function RouterProvider({ children }: { children: ReactNode }) {
  const [location, setLocation] = useState<Location>(() =>
    parseHash(typeof window === 'undefined' ? '' : window.location.hash),
  );

  useEffect(() => {
    const onChange = () => setLocation(parseHash(window.location.hash));
    window.addEventListener('hashchange', onChange);
    if (!window.location.hash) window.location.replace('#/');
    return () => window.removeEventListener('hashchange', onChange);
  }, []);

  const navigate = useCallback((to: string, opts?: { replace?: boolean }) => {
    const next = to.startsWith('#') ? to : `#${to}`;
    if (opts?.replace) window.location.replace(next);
    else window.location.hash = next;
  }, []);

  const back = useCallback(() => window.history.back(), []);

  const value = useMemo<RouterValue>(() => ({ location, navigate, back }), [location, navigate, back]);
  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
}

export function useRouter(): RouterValue {
  const ctx = useContext(RouterContext);
  if (!ctx) throw new Error('useRouter must be used inside <RouterProvider>');
  return ctx;
}

export function useLocation(): Location {
  return useRouter().location;
}

/** Anchor that keeps hash-routing semantics and marks its own active state. */
export function Link({
  to, children, className, activeClassName,
}: {
  to: string;
  children: ReactNode;
  className?: string;
  activeClassName?: string;
}) {
  const { location, navigate } = useRouter();
  const active = location.path === to || (to !== '/' && location.path.startsWith(to));
  const cls = [className, active && activeClassName].filter(Boolean).join(' ');
  return (
    <a
      href={`#${to}`}
      className={cls || undefined}
      aria-current={active ? 'page' : undefined}
      onClick={(e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
        e.preventDefault();
        navigate(to);
      }}
    >
      {children}
    </a>
  );
}
