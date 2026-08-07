import React from 'react';
import type { CSSProperties } from 'react';
import type { Consequence, Reversibility } from '@/kernel/types';
import { formatMoney, formatReversibility } from '@/lib/format';
import './ConsequenceGrid.css';

export interface ConsequenceGridProps {
  consequence: Consequence;
  className?: string;
  style?: CSSProperties;
}

function RevTag({ r }: { r: Reversibility }): React.JSX.Element {
  const tagClass = `k-consequence-grid__rev-tag k-consequence-grid__rev-tag--${r.kind}`;
  const label =
    r.kind === 'reversible'
      ? 'Reversible'
      : r.kind === 'reversible-until'
      ? 'Reversible until'
      : 'Irreversible';

  return (
    <span className={tagClass}>{label}</span>
  );
}

export function ConsequenceGrid({
  consequence,
  className,
  style,
}: ConsequenceGridProps): React.JSX.Element {
  const classes = ['k-consequence-grid', className]
    .filter(Boolean)
    .join(' ');

  const { cost, reversibility } = consequence;

  // Discriminate cost: Money has `currency` + `minor`; non-monetary has `kind`
  const isNonMonetary = 'kind' in cost;
  const costText = isNonMonetary
    ? (cost as { kind: 'non-monetary'; description: string }).description
    : formatMoney(cost as import('@/kernel/types').Money);

  const costIsMoney = !isNonMonetary;

  const revText = formatReversibility(reversibility);

  return (
    <div className={classes} style={style}>
      {/* Top-left: What changes */}
      <div className="k-consequence-grid__cell">
        <span className="k-consequence-grid__cell-label">What changes</span>
        <p className="k-consequence-grid__cell-value">
          {consequence.whatChanges}
        </p>
      </div>

      {/* Top-right: Cost */}
      <div className="k-consequence-grid__cell">
        <span className="k-consequence-grid__cell-label">Cost</span>
        <p
          className={[
            'k-consequence-grid__cell-value',
            costIsMoney ? 'k-consequence-grid__cell-value--mono' : '',
          ]
            .filter(Boolean)
            .join(' ')}
        >
          {costText}
        </p>
      </div>

      {/* Bottom-left: If you do nothing */}
      <div className="k-consequence-grid__cell">
        <span className="k-consequence-grid__cell-label">
          If you do nothing
        </span>
        <p className="k-consequence-grid__cell-value">
          {consequence.ifYouDoNothing}
        </p>
      </div>

      {/* Bottom-right: Reversible */}
      <div className="k-consequence-grid__cell">
        <span className="k-consequence-grid__cell-label">Reversible</span>
        <div className="k-consequence-grid__rev">
          <RevTag r={reversibility} />
        </div>
        <p className="k-consequence-grid__rev-detail">{revText}</p>
      </div>
    </div>
  );
}
