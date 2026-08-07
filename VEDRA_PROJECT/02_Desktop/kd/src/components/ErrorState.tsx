import React from 'react';
import type { CSSProperties } from 'react';
import type { KernelError } from '@/kernel/client';
import { Button } from './Button';
import './ErrorState.css';

export interface ErrorStateProps {
  error: KernelError;
  onRetry?: () => void;
  className?: string;
  style?: CSSProperties;
}

export function ErrorState({
  error,
  onRetry,
  className,
  style,
}: ErrorStateProps): React.JSX.Element {
  const classes = ['k-error-state', className].filter(Boolean).join(' ');

  return (
    <div className={classes} style={style} role="alert">
      <span className="k-error-state__kicker">Error · {error.code}</span>
      {/* message is required to read as a sentence, not a stack trace (KernelError contract) */}
      <p className="k-error-state__message">{error.message}</p>
      {error.detail !== undefined && (
        <p className="k-error-state__detail">{error.detail}</p>
      )}
      {/* Show retry only when the error is retryable */}
      {error.retryable && onRetry !== undefined && (
        <div className="k-error-state__actions">
          <Button variant="accent" size="sm" onClick={onRetry}>
            Try again
          </Button>
        </div>
      )}
    </div>
  );
}
