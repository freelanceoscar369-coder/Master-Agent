import React from 'react';
import type { CSSProperties, ReactNode, MouseEventHandler } from 'react';
import './Button.css';

export interface ButtonProps {
  children: ReactNode;
  variant?: 'default' | 'primary' | 'accent' | 'ghost';
  size?: 'sm' | 'md';
  disabled?: boolean;
  onClick?: MouseEventHandler<HTMLButtonElement>;
  type?: 'button' | 'submit' | 'reset';
  className?: string;
  style?: CSSProperties;
}

export function Button({
  children,
  variant = 'default',
  size = 'md',
  disabled = false,
  onClick,
  type = 'button',
  className,
  style,
}: ButtonProps): React.JSX.Element {
  const classes = [
    'k-button',
    `k-button--${variant}`,
    `k-button--${size}`,
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <button
      className={classes}
      style={style}
      disabled={disabled}
      onClick={onClick}
      type={type}
    >
      {children}
    </button>
  );
}
