import React from 'react';
import type { CSSProperties, ReactNode } from 'react';
import type { Signal } from '@/kernel/types';
import './Stat.css';

export interface StatProps {
  value: ReactNode;
  label: ReactNode;
  tone?: Signal | 'muted';
  className?: string;
  style?: CSSProperties;
}

export function Stat({
  value,
  label,
  tone = 'muted',
  className,
  style,
}: StatProps): React.JSX.Element {
  const toneClass = `k-stat--${tone}`;
  const classes = ['k-stat', toneClass, className].filter(Boolean).join(' ');

  return (
    <div className={classes} style={style}>
      <span className="k-stat__value">{value}</span>
      <span className="k-stat__label">{label}</span>
    </div>
  );
}
