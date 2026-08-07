import React from 'react';
import type { CSSProperties } from 'react';
import type { Signal } from '@/kernel/types';
import './EmptyState.css';

export interface EmptyStateProps {
  headline: string;
  body: string;
  tone?: Signal;
  className?: string;
  style?: CSSProperties;
}

export function EmptyState({
  headline,
  body,
  tone,
  className,
  style,
}: EmptyStateProps): React.JSX.Element {
  const toneClass = tone !== undefined ? `k-empty-state--${tone}` : '';
  const classes = ['k-empty-state', toneClass, className]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={classes} style={style}>
      <p className="k-empty-state__headline">{headline}</p>
      <p className="k-empty-state__body">{body}</p>
    </div>
  );
}
