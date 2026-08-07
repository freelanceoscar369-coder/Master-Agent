import React from 'react';
import type { CSSProperties } from 'react';
import type { Signal } from '@/kernel/types';
import './Sparkline.css';

export interface SparklineProps {
  points: readonly number[];
  tone?: Signal | 'muted';
  /** Width in pixels */
  width?: number;
  /** Height in pixels */
  height?: number;
  className?: string;
  style?: CSSProperties;
}

export function Sparkline({
  points,
  tone = 'muted',
  width = 80,
  height = 24,
  className,
  style,
}: SparklineProps): React.JSX.Element {
  const toneClass = `k-sparkline--${tone}`;
  const classes = ['k-sparkline', toneClass, className]
    .filter(Boolean)
    .join(' ');

  // Need at least 2 points to draw a line
  if (points.length < 2) {
    return (
      <svg
        className={classes}
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        aria-hidden="true"
        style={style}
      />
    );
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min === 0 ? 1 : max - min;

  const pad = 2; // 2px padding to avoid clipping stroke
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;

  const pathData = points
    .map((p, i) => {
      const x = pad + (i / (points.length - 1)) * innerW;
      const y = pad + innerH - ((p - min) / range) * innerH;
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(' ');

  return (
    <svg
      className={classes}
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      aria-hidden="true"
      style={style}
      preserveAspectRatio="none"
    >
      <path className="k-sparkline__line" d={pathData} />
    </svg>
  );
}
