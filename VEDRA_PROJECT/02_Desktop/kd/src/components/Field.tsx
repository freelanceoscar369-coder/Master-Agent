import React from 'react';
import type {
  CSSProperties,
  InputHTMLAttributes,
  SelectHTMLAttributes,
  ReactNode,
  ChangeEventHandler,
} from 'react';
import './Field.css';

/* ── TextField ──────────────────────────────────────────────────────── */

export interface TextFieldProps {
  label: string;
  value: string;
  onChange: ChangeEventHandler<HTMLInputElement>;
  id?: string;
  placeholder?: string;
  disabled?: boolean;
  hint?: string;
  error?: string;
  type?: InputHTMLAttributes<HTMLInputElement>['type'];
  className?: string;
  style?: CSSProperties;
}

export function TextField({
  label,
  value,
  onChange,
  id,
  placeholder,
  disabled,
  hint,
  error,
  type = 'text',
  className,
  style,
}: TextFieldProps): React.JSX.Element {
  const fieldId = id ?? `k-field-${label.toLowerCase().replace(/\s+/g, '-')}`;
  const hasError = error !== undefined;
  const classes = [
    'k-field',
    hasError ? 'k-field--error' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={classes} style={style}>
      <label className="k-field__label" htmlFor={fieldId}>
        {label}
      </label>
      <input
        id={fieldId}
        className="k-field__input"
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        disabled={disabled}
        aria-invalid={hasError}
        aria-describedby={
          hasError
            ? `${fieldId}-error`
            : hint !== undefined
            ? `${fieldId}-hint`
            : undefined
        }
      />
      {hasError && (
        <span id={`${fieldId}-error`} className="k-field__error" role="alert">
          {error}
        </span>
      )}
      {hint !== undefined && !hasError && (
        <span id={`${fieldId}-hint`} className="k-field__hint">
          {hint}
        </span>
      )}
    </div>
  );
}

/* ── SelectField ────────────────────────────────────────────────────── */

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectFieldProps {
  label: string;
  value: string;
  onChange: ChangeEventHandler<HTMLSelectElement>;
  options: readonly SelectOption[];
  id?: string;
  disabled?: boolean;
  hint?: string;
  error?: string;
  className?: string;
  style?: CSSProperties;
}

export function SelectField({
  label,
  value,
  onChange,
  options,
  id,
  disabled,
  hint,
  error,
  className,
  style,
}: SelectFieldProps): React.JSX.Element {
  const fieldId = id ?? `k-field-${label.toLowerCase().replace(/\s+/g, '-')}`;
  const hasError = error !== undefined;
  const classes = [
    'k-field',
    hasError ? 'k-field--error' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={classes} style={style}>
      <label className="k-field__label" htmlFor={fieldId}>
        {label}
      </label>
      <select
        id={fieldId}
        className="k-field__select"
        value={value}
        onChange={onChange}
        disabled={disabled}
        aria-invalid={hasError}
        aria-describedby={
          hasError
            ? `${fieldId}-error`
            : hint !== undefined
            ? `${fieldId}-hint`
            : undefined
        }
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {hasError && (
        <span id={`${fieldId}-error`} className="k-field__error" role="alert">
          {error}
        </span>
      )}
      {hint !== undefined && !hasError && (
        <span id={`${fieldId}-hint`} className="k-field__hint">
          {hint}
        </span>
      )}
    </div>
  );
}

/* ── SearchField ────────────────────────────────────────────────────── */

export interface SearchFieldProps {
  label: string;
  value: string;
  onChange: ChangeEventHandler<HTMLInputElement>;
  id?: string;
  placeholder?: string;
  disabled?: boolean;
  hint?: string;
  className?: string;
  style?: CSSProperties;
}

function SearchIcon(): React.JSX.Element {
  return (
    <svg
      className="k-field__search-icon"
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M10.5 10.5L14 14"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function SearchField({
  label,
  value,
  onChange,
  id,
  placeholder,
  disabled,
  hint,
  className,
  style,
}: SearchFieldProps): React.JSX.Element {
  const fieldId = id ?? `k-field-${label.toLowerCase().replace(/\s+/g, '-')}`;
  const classes = ['k-field', 'k-field--search', className]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={classes} style={style}>
      <label className="k-field__label" htmlFor={fieldId}>
        {label}
      </label>
      <div style={{ position: 'relative' }}>
        <SearchIcon />
        <input
          id={fieldId}
          className="k-field__input"
          type="search"
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          disabled={disabled}
          aria-describedby={
            hint !== undefined ? `${fieldId}-hint` : undefined
          }
        />
      </div>
      {hint !== undefined && (
        <span id={`${fieldId}-hint`} className="k-field__hint">
          {hint}
        </span>
      )}
    </div>
  );
}

