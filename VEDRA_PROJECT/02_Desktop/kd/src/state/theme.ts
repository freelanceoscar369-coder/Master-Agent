/**
 * Theme state.
 *
 * All three themes are in the dark family. A light theme is not a setting —
 * the Design Constitution's lighting model ("the only light source is the
 * intelligence") does not survive a white surface. Adding one is a
 * constitutional amendment, not a feature flag.
 */

export const THEMES = ['midnight', 'depth', 'contrast'] as const;
export type ThemeName = (typeof THEMES)[number];

export const THEME_LABELS: Record<ThemeName, string> = {
  midnight: 'Midnight — canonical',
  depth: 'Depth — long sessions',
  contrast: 'Contrast — accessibility',
};

const KEY = 'kalpa.theme';

export function getStoredTheme(): ThemeName {
  if (typeof localStorage === 'undefined') return 'midnight';
  const v = localStorage.getItem(KEY);
  return (THEMES as readonly string[]).includes(v ?? '') ? (v as ThemeName) : 'midnight';
}

export function applyTheme(name: ThemeName): void {
  if (typeof document === 'undefined') return;
  document.documentElement.setAttribute('data-theme', name);
  try { localStorage.setItem(KEY, name); } catch { /* storage unavailable — theme is session-only */ }
}

/** Density is separate from theme: it changes spacing, never colour. */
export const DENSITIES = ['comfortable', 'compact'] as const;
export type Density = (typeof DENSITIES)[number];

export function getStoredDensity(): Density {
  if (typeof localStorage === 'undefined') return 'comfortable';
  const v = localStorage.getItem('kalpa.density');
  return v === 'compact' ? 'compact' : 'comfortable';
}

export function applyDensity(d: Density): void {
  if (typeof document === 'undefined') return;
  document.documentElement.setAttribute('data-density', d);
  try { localStorage.setItem('kalpa.density', d); } catch { /* ignore */ }
}
