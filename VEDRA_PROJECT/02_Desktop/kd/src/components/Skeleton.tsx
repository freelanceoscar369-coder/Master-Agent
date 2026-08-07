import React from 'react';
import type { CSSProperties } from 'react';
import './Skeleton.css';

export interface SkeletonProps {
  /** Number of text-line placeholders to render. Mutually exclusive with height. */
  lines?: number;
  /** Fixed pixel height for a block placeholder. Mutually exclusive with lines. */
  height?: number;
  className?: string;
  style?: CSSProperties;
}

export function Skeleton({
  lines,
  height,
  className,
  style,
}: SkeletonProps): React.JSX.Element {
  // Block mode: a single fixed-height placeholder
  if (height !== undefined) {
    const classes = ['k-skeleton--block', className]
      .filter(Boolean)
      .join(' ');
    return (
      <span
        className={classes}
        style={{ height: `${height}px`, ...style }}
        aria-hidden="true"
        role="presentation"
      />
    );
  }

  // Lines mode (default 3)
  const lineCount = lines ?? 3;
  const classes = ['k-skeleton', className].filter(Boolean).join(' ');
  // Line height from body scale = 24px
  const lineHeight = 16;

  return (
    <div
      className={classes}
      style={style}
      aria-hidden="true"
      role="presentation"
    >
      {Array.from({ length: lineCount }, (_, i) => (
        <span
          key={i}
          className="k-skeleton__line"
          style={{ height: `${lineHeight}px` }}
        />
      ))}
    </div>
  );
}
