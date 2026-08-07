/**
 * UndoToast — the ONLY transient surface allowed by the Design Constitution.
 * NOTIFICATIONS ARE FORBIDDEN. This component exists for the undo flow only.
 * Do not add notification variants or info/success/error toasts here.
 */
import React, { useEffect, useRef, useState } from 'react';
import { Button } from './Button';
import './Toast.css';

export interface UndoToastProps {
  message: string;
  /** Total countdown duration in seconds */
  seconds: number;
  onUndo: () => void;
  onExpire: () => void;
  className?: string;
}

export function UndoToast({
  message,
  seconds,
  onUndo,
  onExpire,
  className,
}: UndoToastProps): React.JSX.Element {
  const [remaining, setRemaining] = useState(seconds);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    // Tick every 100ms for smooth bar; use integer seconds for display
    const startTime = Date.now();
    const totalMs = seconds * 1000;

    intervalRef.current = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const left = Math.max(0, (totalMs - elapsed) / 1000);
      setRemaining(left);
      if (left === 0) {
        if (intervalRef.current !== null) {
          clearInterval(intervalRef.current);
        }
        onExpire();
      }
    }, 100);

    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
      }
    };
    // onExpire is called once; stable ref assumption
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seconds]);

  const fillPct = (remaining / seconds) * 100;
  const displaySeconds = Math.ceil(remaining);

  const classes = ['k-undo-toast', className].filter(Boolean).join(' ');

  return (
    <div className={classes} role="status" aria-live="polite">
      <div className="k-undo-toast__body">
        <span className="k-undo-toast__message">{message}</span>
        <span className="k-undo-toast__countdown">{displaySeconds}s</span>
      </div>
      <div className="k-undo-toast__actions">
        <Button variant="accent" size="sm" onClick={onUndo}>
          Undo
        </Button>
      </div>
      <div className="k-undo-toast__bar" aria-hidden="true">
        <div
          className="k-undo-toast__bar-fill"
          style={{ width: `${fillPct}%` }}
        />
      </div>
    </div>
  );
}
