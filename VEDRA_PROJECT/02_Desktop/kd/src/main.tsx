/**
 * Application entry point.
 *
 * CSS import order matters — tokens first so themes can override them,
 * base provides the reset, grid provides layout primitives.
 */

import '@/design/tokens.css';
import '@/design/themes.css';
import '@/design/base.css';
import '@/design/grid.css';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { applyDensity, applyTheme, getStoredDensity, getStoredTheme } from '@/state/theme';
import App from './App';

// Apply stored theme and density before the first React paint so there is no
// flash of unstyled content. Both functions guard against SSR / missing document.
applyTheme(getStoredTheme());
applyDensity(getStoredDensity());

const root = document.getElementById('root');
if (root === null) {
  throw new Error('Root element #root not found. Check index.html.');
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
