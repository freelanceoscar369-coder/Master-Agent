import React from 'react';
import type { CSSProperties } from 'react';
import type { Signal } from '@/kernel/types';
import './Bar.css';

export interface BarProps {
  /** 0 to 1 */
  value: number;
  tone?: Signal | 'muted';
  className?: string;
  style?: CSSProperties;
}

export function Bar({
  value,
  tone = 'muted',
  className,
  style,
}: BarProps): React.JSX.Element {
  // Clamp to [0, 1]
  const clamped = Math.min(1, Math.max(0, value));
  const toneClass = `k-bar--${tone}`;
  const classes = ['k-bar', toneClass, className].filter(Boolean).join(' ');

  return (
    <div
      className={classes}
      style={style}
      role="progressbar"
      aria-valuenow={Math.round(clamped * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className="k-bar__fill"
        style={{ width: `${clamped * 100}%` }}
      />
    </div>
  );
}
