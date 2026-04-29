/**
 * useHotkeys — 全局快捷键 Hook (P2-1)
 * 
 * 支持:
 *   Ctrl+K  →  打开命令面板
 *   Ctrl+.  →  打开设置
 *   Ctrl+Enter → 执行当前任务
 *   /   → 聚焦搜索栏 (非输入框时)
 *   Escape → 关闭弹窗
 */
import { useEffect, useCallback, useRef } from 'react';

export interface HotkeyBinding {
  /** 快捷键组合，如 'ctrl+k', 'ctrl+enter', 'escape', '/' */
  key: string;
  /** 触发回调 */
  handler: (e: KeyboardEvent) => void;
  /** 是否在输入框中也生效，默认 false */
  enableInInput?: boolean;
  /** 描述（用于命令面板显示） */
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

/**
 * 注册全局快捷键
 */
export function useHotkeys(bindings: HotkeyBinding[]): void {
  const bindingsRef = useRef(bindings);
  useEffect(() => {
    bindingsRef.current = bindings;
  }, [bindings]);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    for (const binding of bindingsRef.current) {
      if (matchesKey(e, binding.key)) {
        // 如果在输入框中且 binding 不允许，跳过
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
