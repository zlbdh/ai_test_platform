/** useHotkeys: global keyboard shortcuts (P2-1).
 * Ctrl+K: open the command palette.
 * Ctrl+.: open settings.
 * Ctrl+Enter: execute the current task.
 * /: focus search when outside an input field.
 * Escape: close the dialog.
 */
import { useEffect, useCallback, useRef } from 'react';

export interface HotkeyBinding {
  /** Shortcut combination, such as 'ctrl+k', 'ctrl+enter', 'escape', or '/'. */
  key: string;
  /** Trigger callback. */
  handler: (e: KeyboardEvent) => void;
  /** Whether the shortcut works inside input fields; defaults to false. */
  enableInInput?: boolean;
  /** Description displayed in the command palette. */
  description?: string;
}

function matchesKey(e: KeyboardEvent, hotkey: string): boolean {
  const parts = hotkey.toLowerCase().split('+');
  const needsCtrl = parts.includes('ctrl') || parts.includes('mod');
  const needsShift = parts.includes('shift');
  const needsAlt = parts.includes('alt');
  const key = parts.filter(p => !['ctrl', 'mod', 'shift', 'alt'].includes(p))[0];

  if (needsCtrl !== (e.ctrlKey || e.metaKey)) return false;
  if (needsShift !== e.shiftKey) return false;
  if (needsAlt !== e.altKey) return false;

  if (key === 'enter') return e.key === 'Enter';
  if (key === 'escape' || key === 'esc') return e.key === 'Escape';
  if (key === '/') return e.key === '/';
  if (key === '.') return e.key === '.';

  return e.key.toLowerCase() === key;
}

function isInputElement(el: EventTarget | null): boolean {
  if (!el || !(el instanceof HTMLElement)) return false;
  const tagName = el.tagName.toLowerCase();
  return (
    tagName === 'input' ||
    tagName === 'textarea' ||
    tagName === 'select' ||
    el.isContentEditable
  );
}

/** Register global keyboard shortcuts.
 */
export function useHotkeys(bindings: HotkeyBinding[]): void {
  const bindingsRef = useRef(bindings);
  useEffect(() => {
    bindingsRef.current = bindings;
  }, [bindings]);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    for (const binding of bindingsRef.current) {
      if (matchesKey(e, binding.key)) {
        // Skip input fields unless the binding allows them.
        if (!binding.enableInInput && isInputElement(e.target)) {
          continue;
        }
        e.preventDefault();
        e.stopPropagation();
        binding.handler(e);
        return;
      }
    }
  }, []);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}

export default useHotkeys;
