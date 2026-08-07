import React from 'react';
import type { CSSProperties, ReactNode } from 'react';
import type { Signal } from '@/kernel/types';
import './Tag.css';

export interface TagProps {
  children: ReactNode;
  tone?: Signal | 'muted';
  className?: string;
  style?: CSSProperties;
}

export function Tag({
  children,
  tone = 'muted',
  className,
  style,
}: TagProps): React.JSX.Element {
  const toneClass = `k-tag--${tone}`;
  const classes = ['k-tag', toneClass, className].filter(Boolean).join(' ');

  return (
    <span className={classes} style={style}>
      {children}
    </span>
  );
}
