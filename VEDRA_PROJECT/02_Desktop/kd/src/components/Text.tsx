import React from 'react';
import type { CSSProperties, ReactNode } from 'react';
import './Text.css';

interface TextBaseProps {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}

export function Body({
  children,
  className,
  style,
}: TextBaseProps): React.JSX.Element {
  const classes = ['k-body', className].filter(Boolean).join(' ');
  return (
    <p className={classes} style={style}>
      {children}
    </p>
  );
}

export function Lede({
  children,
  className,
  style,
}: TextBaseProps): React.JSX.Element {
  const classes = ['k-lede', className].filter(Boolean).join(' ');
  return (
    <p className={classes} style={style}>
      {children}
    </p>
  );
}

export function Dim({
  children,
  className,
  style,
}: TextBaseProps): React.JSX.Element {
  const classes = ['k-dim', className].filter(Boolean).join(' ');
  return (
    <p className={classes} style={style}>
      {children}
    </p>
  );
}

export function Mono({
  children,
  className,
  style,
}: TextBaseProps): React.JSX.Element {
  const classes = ['k-mono', className].filter(Boolean).join(' ');
  return (
    <span className={classes} style={style}>
      {children}
    </span>
  );
}
