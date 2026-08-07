import React from 'react';
import type { CSSProperties } from 'react';
import './Rule.css';

export interface RuleProps {
  soft?: boolean;
  className?: string;
  style?: CSSProperties;
}

export function Rule({
  soft = false,
  className,
  style,
}: RuleProps): React.JSX.Element {
  const classes = ['k-rule', soft && 'k-rule--soft', className]
    .filter(Boolean)
    .join(' ');

  return <hr className={classes} style={style} />;
}
