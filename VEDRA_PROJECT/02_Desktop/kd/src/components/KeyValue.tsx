import React from 'react';
import type { CSSProperties, ReactNode } from 'react';
import './KeyValue.css';

export interface KeyValueRow {
  k: string;
  v: ReactNode;
  mono?: boolean;
}

export interface KeyValueProps {
  rows: readonly KeyValueRow[];
  className?: string;
  style?: CSSProperties;
}

export function KeyValue({
  rows,
  className,
  style,
}: KeyValueProps): React.JSX.Element {
  const classes = ['k-key-value', className].filter(Boolean).join(' ');

  return (
    <dl className={classes} style={style}>
      {rows.map((row, i) => (
        <div key={i} className="k-key-value__row">
          <dt className="k-key-value__key">{row.k}</dt>
          <dd
            className={[
              'k-key-value__value',
              row.mono === true ? 'k-key-value__value--mono' : '',
            ]
              .filter(Boolean)
              .join(' ')}
          >
            {row.v}
          </dd>
        </div>
      ))}
    </dl>
  );
}
