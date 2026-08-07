import React from 'react';
import type { CSSProperties, ReactNode } from 'react';
import type { Signal } from '@/kernel/types';
import './Panel.css';

export interface PanelProps {
  children: ReactNode;
  pad?: 'a' | 'b' | 'none';
  tone?: 'default' | Signal;
  className?: string;
  style?: CSSProperties;
}

export function Panel({
  children,
  pad = 'a',
  tone = 'default',
  className,
  style,
}: PanelProps): React.JSX.Element {
  const padClass = `k-panel--pad-${pad}`;
  const toneClass = tone !== 'default' ? `k-panel--tone-${tone}` : '';
  const classes = ['k-panel', padClass, toneClass, className]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={classes} style={style}>
      {children}
    </div>
  );
}
