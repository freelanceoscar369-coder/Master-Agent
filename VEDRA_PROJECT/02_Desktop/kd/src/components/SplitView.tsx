import React from 'react';
import type { CSSProperties, ReactNode } from 'react';
import './SplitView.css';

export interface SplitViewProps {
  left: ReactNode;
  right: ReactNode;
  /** Column ratio as a fraction string, e.g. "1fr 2fr". Defaults to "5fr 7fr" (5/12 + 7/12). */
  ratio?: string;
  className?: string;
  style?: CSSProperties;
}

export function SplitView({
  left,
  right,
  ratio = '5fr 7fr',
  className,
  style,
}: SplitViewProps): React.JSX.Element {
  const classes = ['k-split-view', className].filter(Boolean).join(' ');

  return (
    <div
      className={classes}
      style={{ gridTemplateColumns: ratio, ...style }}
    >
      <div className="k-split-view__left">{left}</div>
      <div className="k-split-view__right">{right}</div>
    </div>
  );
}
