import React from 'react';
import type { CSSProperties, ReactNode } from 'react';
import type { Signal } from '@/kernel/types';
import './Kicker.css';

export interface KickerProps {
  children: ReactNode;
  tone?: Signal | 'muted';
  className?: string;
  style?: CSSProperties;
}

export function Kicker({
  children,
  tone = 'muted',
  className,
  style,
}: KickerProps): React.JSX.Element {
  const toneClass = `k-kicker--${tone}`;
  const classes = ['k-kicker', toneClass, className].filter(Boolean).join(' ');

  return (
    <span className={classes} style={style}>
      {children}
    </span>
  );
}
