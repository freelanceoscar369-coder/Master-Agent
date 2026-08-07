/**
 * ConfidenceMark — renders a Confidence union value.
 *
 * §10: Confidence is a three-level union — "recommend", "lean", "insufficient".
 * It is IMPOSSIBLE to render a percentage here by design.
 * Do not add a numeric or float display path to this component.
 */
import React from 'react';
import type { CSSProperties } from 'react';
import type { Confidence } from '@/kernel/types';
import './ConfidenceMark.css';

export interface ConfidenceMarkProps {
  confidence: Confidence;
  className?: string;
  style?: CSSProperties;
}

/** Map level to how many of the three marks are filled */
const FILLED_COUNT: Record<Confidence['level'], number> = {
  recommend: 3,
  lean: 2,
  insufficient: 1,
};

const LEVEL_LABEL: Record<Confidence['level'], string> = {
  recommend: 'Recommend',
  lean: 'Lean',
  insufficient: 'Insufficient',
};

export function ConfidenceMark({
  confidence,
  className,
  style,
}: ConfidenceMarkProps): React.JSX.Element {
  const filledCount = FILLED_COUNT[confidence.level];
  const levelClass = `k-confidence--${confidence.level}`;
  const classes = ['k-confidence', levelClass, className]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={classes} style={style}>
      <div className="k-confidence__marks" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className={[
              'k-confidence__mark',
              i < filledCount ? 'k-confidence__mark--filled' : '',
            ]
              .filter(Boolean)
              .join(' ')}
          />
        ))}
        <span className="k-confidence__level">
          {LEVEL_LABEL[confidence.level]}
        </span>
      </div>
      <p className="k-confidence__phrasing">{confidence.phrasing}</p>
      {confidence.level === 'insufficient' && (
        <p className="k-confidence__qualifier">
          {confidence.whatWouldRaiseIt}
        </p>
      )}
    </div>
  );
}
