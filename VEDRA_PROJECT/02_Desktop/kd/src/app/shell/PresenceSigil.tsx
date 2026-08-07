/**
 * PresenceSigil — 28×28px canvas particle mark.
 *
 * Four states (from kernel/types.ts):
 *   idle     — slow breathe (amplitude ×1, period ~4s)
 *   thinking — drift ×3 (three particles orbiting)
 *   speaking — pulse (radius expands rhythmically)
 *   awaiting — colour warms toward --signal-needs-you
 *
 * Constitution rules enforced here:
 *   · Never reacts to the cursor.
 *   · Never used as a loading spinner.
 *   · Colour interpolation is slow (~2% per frame at 60fps ≈ ~3s full shift).
 *   · devicePixelRatio capped at 2.
 *   · Colours read from getComputedStyle(document.documentElement) so they
 *     follow the active theme without recompilation.
 *   · Full static fallback under prefers-reduced-motion.
 */

import React, {
  useEffect,
  useRef,
  type CSSProperties,
} from 'react';
import { usePresence } from '@/kernel/hooks';
import type { PresenceState } from '@/kernel/types';
import styles from './PresenceSigil.module.css';

/* ── colour helpers ──────────────────────────────────────────────────────── */

interface RGB { r: number; g: number; b: number }

function hexToRgb(hex: string): RGB {
  const h = hex.replace('#', '');
  return {
    r: parseInt(h.slice(0, 2), 16),
    g: parseInt(h.slice(2, 4), 16),
    b: parseInt(h.slice(4, 6), 16),
  };
}

function lerpRgb(a: RGB, b: RGB, t: number): RGB {
  return {
    r: a.r + (b.r - a.r) * t,
    g: a.g + (b.g - a.g) * t,
    b: a.b + (b.b - a.b) * t,
  };
}

function rgbCss(c: RGB, alpha = 1): string {
  return `rgba(${Math.round(c.r)},${Math.round(c.g)},${Math.round(c.b)},${alpha})`;
}

function readToken(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Parse a CSS colour token that is in hex format (our tokens always are). */
function tokenRgb(name: string): RGB {
  const raw = readToken(name);
  if (raw.startsWith('#')) return hexToRgb(raw);
  // fallback if token is not hex (e.g. rgba)
  return { r: 127, g: 211, b: 255 };
}

/* ── target colour per state ─────────────────────────────────────────────── */

function targetForState(state: PresenceState): RGB {
  switch (state) {
    case 'idle':      return tokenRgb('--signal-live');
    case 'thinking':  return tokenRgb('--signal-live');
    case 'speaking':  return tokenRgb('--signal-done');
    case 'awaiting':  return tokenRgb('--signal-needs-you');
  }
}

/* ── canvas renderer ─────────────────────────────────────────────────────── */

const SIZE = 28;
// ~2% per frame colour lerp — at 60fps ≈ 50 frames to reach target (≈833ms)
const COLOUR_LERP_RATE = 0.02;

export function PresenceSigil(): React.ReactElement {
  const presence = usePresence();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef<PresenceState>(presence);
  const colourRef = useRef<RGB>(tokenRgb('--signal-live'));
  const frameRef = useRef<number | null>(null);
  const tickRef = useRef(0);

  // Keep latest presence in ref so the RAF closure always sees it.
  useEffect(() => {
    stateRef.current = presence;
  }, [presence]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (canvas === null) return;

    const dpr = Math.min(window.devicePixelRatio, 2);
    canvas.width = SIZE * dpr;
    canvas.height = SIZE * dpr;
    const ctx = canvas.getContext('2d');
    if (ctx === null) return;
    ctx.scale(dpr, dpr);

    const cx = SIZE / 2;
    const cy = SIZE / 2;
    const baseRadius = 4;

    // ctx is narrowed to CanvasRenderingContext2D (non-null) above this point.
    // Capture it in a local alias so the inner draw function can use it safely.
    const g = ctx;

    function draw(t: number): void {
      tickRef.current = t;
      const state = stateRef.current;

      // Lerp colour toward target ~2% per frame
      const target = targetForState(state);
      colourRef.current = lerpRgb(colourRef.current, target, COLOUR_LERP_RATE);
      const col = colourRef.current;

      g.clearRect(0, 0, SIZE, SIZE);

      if (state === 'idle') {
        // Slow breathe — radius oscillates ±1px over ~4s (240 frames at 60fps)
        const phase = (t / 4000) * Math.PI * 2;
        const r = baseRadius + Math.sin(phase) * 1;
        g.beginPath();
        g.arc(cx, cy, r, 0, Math.PI * 2);
        g.fillStyle = rgbCss(col, 0.7 + Math.sin(phase) * 0.2);
        g.fill();

      } else if (state === 'thinking') {
        // Three particles drifting in a slow orbit
        for (let i = 0; i < 3; i++) {
          const angle = (t / 2000) * Math.PI * 2 + (i * Math.PI * 2) / 3;
          const orbit = 5;
          const px = cx + Math.cos(angle) * orbit;
          const py = cy + Math.sin(angle) * orbit;
          const phase = (t / 1200 + i * 0.33) * Math.PI * 2;
          const pr = 2 + Math.sin(phase) * 0.5;
          g.beginPath();
          g.arc(px, py, pr, 0, Math.PI * 2);
          g.fillStyle = rgbCss(col, 0.5 + (i * 0.15));
          g.fill();
        }

      } else if (state === 'speaking') {
        // Core + expanding ring pulse
        const pulse = (t / 600) % 1;
        const pr = baseRadius + pulse * 6;
        g.beginPath();
        g.arc(cx, cy, pr, 0, Math.PI * 2);
        g.strokeStyle = rgbCss(col, (1 - pulse) * 0.5);
        g.lineWidth = 1;
        g.stroke();
        g.beginPath();
        g.arc(cx, cy, baseRadius, 0, Math.PI * 2);
        g.fillStyle = rgbCss(col, 0.9);
        g.fill();

      } else if (state === 'awaiting') {
        // Steady dot, colour warming toward --signal-needs-you (handled by lerp)
        const phase = (t / 1800) * Math.PI * 2;
        const r = baseRadius + Math.sin(phase) * 0.5;
        g.beginPath();
        g.arc(cx, cy, r, 0, Math.PI * 2);
        g.fillStyle = rgbCss(col, 0.85);
        g.fill();
      }

      frameRef.current = requestAnimationFrame(draw);
    }

    frameRef.current = requestAnimationFrame(draw);

    return () => {
      if (frameRef.current !== null) {
        cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
      }
    };
  }, []);

  // Static fallback for prefers-reduced-motion — rendered as a CSS circle.
  // We always render the canvas but hide it via CSS; the static dot is
  // shown in its place.
  return (
    <span
      className={styles.root}
      aria-label={`Presence: ${presence}`}
      role="img"
      style={{ '--presence-state': presence } as CSSProperties}
    >
      <canvas
        ref={canvasRef}
        width={SIZE}
        height={SIZE}
        className={styles.canvas}
        aria-hidden="true"
      />
      {/* Static fallback — visible only under prefers-reduced-motion */}
      <span className={styles.static} aria-hidden="true" />
    </span>
  );
}
