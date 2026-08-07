import React from 'react';
import type { CSSProperties } from 'react';
import type { Signal } from '@/kernel/types';
import './Timeline.css';

export interface TimelineItem {
  id: string;
  at: string;
  line: string;
  tone?: Signal;
  active?: boolean;
}

export interface TimelineProps {
  items: readonly TimelineItem[];
  className?: string;
  style?: CSSProperties;
}

export function Timeline({
  items,
  className,
  style,
}: TimelineProps): React.JSX.Element {
  const classes = ['k-timeline', className].filter(Boolean).join(' ');

  return (
    <ol className={classes} style={style}>
      {items.map((item) => {
        const toneClass =
          item.tone !== undefined ? `k-timeline__item--tone-${item.tone}` : '';
        const activeClass = item.active === true ? 'k-timeline__item--active' : '';
        const itemClasses = [
          'k-timeline__item',
          toneClass,
          activeClass,
        ]
          .filter(Boolean)
          .join(' ');

        return (
          <li key={item.id} className={itemClasses}>
            <div className="k-timeline__track">
              <div className="k-timeline__node" aria-hidden="true" />
            </div>
            <div className="k-timeline__content">
              <span className="k-timeline__at">{item.at}</span>
              <span className="k-timeline__line">{item.line}</span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
