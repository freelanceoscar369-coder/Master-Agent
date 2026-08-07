import React from 'react';
import type { CSSProperties } from 'react';
import './Tabs.css';

export interface TabDef {
  key: string;
  label: string;
  count?: number;
}

export interface TabsProps {
  tabs: readonly TabDef[];
  active: string;
  onChange: (key: string) => void;
  className?: string;
  style?: CSSProperties;
}

export function Tabs({
  tabs,
  active,
  onChange,
  className,
  style,
}: TabsProps): React.JSX.Element {
  const classes = ['k-tabs', className].filter(Boolean).join(' ');

  return (
    <nav className={classes} style={style} aria-label="Section tabs">
      {tabs.map((tab) => {
        const isActive = tab.key === active;
        const tabClasses = [
          'k-tabs__tab',
          isActive ? 'k-tabs__tab--active' : '',
        ]
          .filter(Boolean)
          .join(' ');

        return (
          <button
            key={tab.key}
            className={tabClasses}
            aria-current={isActive ? 'page' : undefined}
            onClick={() => onChange(tab.key)}
            type="button"
          >
            {tab.label}
            {tab.count !== undefined && (
              <span className="k-tabs__count" aria-label={`${tab.count} items`}>
                {tab.count}
              </span>
            )}
          </button>
        );
      })}
    </nav>
  );
}
