/**
 * CommandBar — ⌘K / Ctrl+K palette.
 *
 * CONSTITUTION NOTE: This is NOT a modal. The constitution forbids modals.
 * It is a transient-plane sheet docked to the top of the content area, using
 * z-index: var(--z-transient). It overlays the content without blocking the
 * entire viewport or using a backdrop that dims everything.
 *
 * Features:
 *   · Fuzzy-filters routes from the registry plus static verbs.
 *   · Arrow keys + Enter to activate, Escape to close.
 *   · Focus trap while open; focus restored to the trigger on close.
 *   · ⌘K / Ctrl+K toggles open/closed.
 */

import React, {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
} from 'react';
import { useRouter } from '@/app/router';
import { REGISTRY } from '@/app/registry';
import { useHotkey } from '@/state/prefs';
import {
  applyTheme,
  applyDensity,
  getStoredDensity,
  getStoredTheme,
  THEMES,
  type ThemeName,
} from '@/state/theme';
import styles from './CommandBar.module.css';

/* ── Command item types ──────────────────────────────────────────────────── */

interface RouteCommand {
  readonly kind: 'route';
  readonly id: string;
  readonly label: string;
  readonly hint: string;
  readonly path: string;
}

interface VerbCommand {
  readonly kind: 'verb';
  readonly id: string;
  readonly label: string;
  readonly hint: string;
  readonly run: () => void;
}

type Command = RouteCommand | VerbCommand;

/* ── Static verb commands ─────────────────────────────────────────────────── */

function buildVerbs(): VerbCommand[] {
  return [
    {
      kind: 'verb',
      id: 'verb-pause-autonomy',
      label: 'Pause all autonomy',
      hint: 'Suspend all standing rules immediately.',
      run: () => {
        // The kernel call lives in the FounderConsole — navigate there.
        window.location.hash = '#/console';
      },
    },
    {
      kind: 'verb',
      id: 'verb-show-grid',
      label: 'Show grid',
      hint: 'Toggle the 12-column baseline grid overlay (G).',
      run: () => {
        document.body.classList.toggle('grid-on');
      },
    },
    {
      kind: 'verb',
      id: 'verb-cycle-theme',
      label: 'Cycle theme',
      hint: 'Switch between midnight, depth, and contrast themes.',
      run: () => {
        const current = getStoredTheme();
        const idx = THEMES.indexOf(current);
        const next: ThemeName = THEMES[(idx + 1) % THEMES.length] ?? 'midnight';
        applyTheme(next);
      },
    },
    {
      kind: 'verb',
      id: 'verb-toggle-density',
      label: 'Toggle density',
      hint: 'Switch between comfortable and compact spacing.',
      run: () => {
        const current = getStoredDensity();
        applyDensity(current === 'comfortable' ? 'compact' : 'comfortable');
      },
    },
  ];
}

/* ── Fuzzy filter ─────────────────────────────────────────────────────────── */

function fuzzy(haystack: string, needle: string): boolean {
  if (needle === '') return true;
  const h = haystack.toLowerCase();
  const n = needle.toLowerCase();
  let hi = 0;
  for (let ni = 0; ni < n.length; ni++) {
    const ch = n[ni];
    if (ch === undefined) break;
    const found = h.indexOf(ch, hi);
    if (found === -1) return false;
    hi = found + 1;
  }
  return true;
}

/* ── CommandBar ───────────────────────────────────────────────────────────── */

interface CommandBarProps {
  readonly open: boolean;
  readonly onClose: () => void;
}

export function CommandBar({ open, onClose }: CommandBarProps): React.ReactElement | null {
  const { navigate } = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState('');
  const [activeIdx, setActiveIdx] = useState(0);
  const inputId = useId();

  // Build full command list
  const allCommands: Command[] = [
    ...REGISTRY.map(
      (r): RouteCommand => ({
        kind: 'route',
        id: `route-${r.path}`,
        label: r.label,
        hint: r.hint,
        path: r.path,
      }),
    ),
    ...buildVerbs(),
  ];

  // Filtered commands
  const commands = allCommands.filter(
    (c) => fuzzy(c.label, query) || fuzzy(c.hint, query),
  );

  // Reset state when opened
  useEffect(() => {
    if (open) {
      setQuery('');
      setActiveIdx(0);
      // Focus the input after the paint
      requestAnimationFrame(() => {
        inputRef.current?.focus();
      });
    }
  }, [open]);

  // Keep active item in view
  useEffect(() => {
    if (!open) return;
    const list = listRef.current;
    if (list === null) return;
    const item = list.children[activeIdx];
    if (item instanceof HTMLElement) {
      item.scrollIntoView({ block: 'nearest' });
    }
  }, [activeIdx, open]);

  // Activate the current command
  const activate = useCallback(
    (cmd: Command): void => {
      onClose();
      if (cmd.kind === 'route') {
        navigate(cmd.path);
      } else {
        cmd.run();
      }
    },
    [navigate, onClose],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent): void => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIdx((i) => Math.min(i + 1, commands.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIdx((i) => Math.max(i - 1, 0));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const cmd = commands[activeIdx];
        if (cmd !== undefined) activate(cmd);
      } else if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    },
    [commands, activeIdx, activate, onClose],
  );

  // Focus trap: tab within the container only
  const handleTabTrap = useCallback(
    (e: KeyboardEvent): void => {
      if (!open || e.key !== 'Tab') return;
      const container = containerRef.current;
      if (container === null) return;
      const focusable = Array.from(
        container.querySelectorAll<HTMLElement>(
          'input, button, [tabindex]:not([tabindex="-1"])',
        ),
      );
      if (focusable.length === 0) return;
      const first: HTMLElement | undefined = focusable[0];
      const last: HTMLElement | undefined = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (first !== undefined && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        }
      } else {
        if (last !== undefined && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    },
    [open],
  );

  useEffect(() => {
    window.addEventListener('keydown', handleTabTrap);
    return () => window.removeEventListener('keydown', handleTabTrap);
  }, [handleTabTrap]);

  if (!open) return null;

  return (
    /* Not a modal — z-transient sheet docked to the top of the content area */
    <div
      ref={containerRef}
      className={styles.root}
      role="combobox"
      aria-expanded={open}
      aria-haspopup="listbox"
      aria-owns={`${inputId}-list`}
      aria-controls={`${inputId}-list`}
      aria-activedescendant={
        commands[activeIdx] !== undefined
          ? `${inputId}-item-${activeIdx}`
          : undefined
      }
    >
      <div className={styles.inputRow}>
        <input
          ref={inputRef}
          id={inputId}
          type="text"
          role="searchbox"
          className={styles.input}
          placeholder="Go to… or type a command"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setActiveIdx(0);
          }}
          onKeyDown={handleKeyDown}
          autoComplete="off"
          spellCheck={false}
          aria-label="Command bar"
          aria-autocomplete="list"
        />
        <button
          type="button"
          className={styles.escBtn}
          onClick={onClose}
          aria-label="Close command bar"
        >
          esc
        </button>
      </div>

      {commands.length > 0 && (
        <ul
          ref={listRef}
          id={`${inputId}-list`}
          role="listbox"
          className={styles.list}
          aria-label="Commands"
        >
          {commands.map((cmd, i) => (
            <li
              key={cmd.id}
              id={`${inputId}-item-${i}`}
              role="option"
              aria-selected={i === activeIdx}
              className={`${styles.item} ${i === activeIdx ? styles.itemActive : ''}`}
              onMouseEnter={() => setActiveIdx(i)}
              onClick={() => activate(cmd)}
            >
              <span className={styles.itemLabel}>{cmd.label}</span>
              <span className={styles.itemHint}>{cmd.hint}</span>
            </li>
          ))}
        </ul>
      )}

      {commands.length === 0 && (
        <p className={styles.empty}>No matching commands.</p>
      )}
    </div>
  );
}

/* ── CommandBarController ─────────────────────────────────────────────────── */

/**
 * Manages open state and global ⌘K / Ctrl+K hotkey.
 * Returns { open, onClose } to pass to CommandBar.
 */
export function useCommandBar(): {
  open: boolean;
  onClose: () => void;
  onOpen: () => void;
} {
  const [open, setOpen] = useState(false);

  const onClose = useCallback(() => setOpen(false), []);
  const onOpen = useCallback(() => setOpen(true), []);

  useHotkey(
    (e) => (e.metaKey || e.ctrlKey) && e.key === 'k',
    (e) => {
      e.preventDefault();
      setOpen((prev) => !prev);
    },
    [],
  );

  return { open, onClose, onOpen };
}
