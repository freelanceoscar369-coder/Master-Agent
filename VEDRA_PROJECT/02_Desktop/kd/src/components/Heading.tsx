import React from 'react';
import type { CSSProperties, ReactNode } from 'react';
import './Heading.css';

interface HeadingBaseProps {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}

export function Speech({
  children,
  className,
  style,
}: HeadingBaseProps): React.JSX.Element {
  const classes = ['k-speech', className].filter(Boolean).join(' ');
  return (
    <p className={classes} style={style}>
      {children}
    </p>
  );
}

export function H1({
  children,
  className,
  style,
}: HeadingBaseProps): React.JSX.Element {
  const classes = ['k-h1', className].filter(Boolean).join(' ');
  return (
    <h1 className={classes} style={style}>
      {children}
    </h1>
  );
}

export function H2({
  children,
  className,
  style,
}: HeadingBaseProps): React.JSX.Element {
  const classes = ['k-h2', className].filter(Boolean).join(' ');
  return (
    <h2 className={classes} style={style}>
      {children}
    </h2>
  );
}

export function H3({
  children,
  className,
  style,
}: HeadingBaseProps): React.JSX.Element {
  const classes = ['k-h3', className].filter(Boolean).join(' ');
  return (
    <h3 className={classes} style={style}>
      {children}
    </h3>
  );
}
