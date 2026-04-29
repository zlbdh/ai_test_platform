/**
 * useT — React hook，从 Zustand store 读取 locale 并返回绑定的翻译函数
 * 
 * 单独文件，以避免 i18n.ts ↔ stores 的循环依赖
 * 使用方式: const tt = useT(); tt('nav.dashboard') => '仪表盘' | 'Dashboard'
 */
import { useAppStore } from '../stores';
import { t, type Locale, translateGroupName } from '../i18n';

export function useT(): (key: string) => string {
    const locale = useAppStore((s) => s.locale) as Locale;
    return (key: string) => t(locale, key);
}

export function useGroupT(): (group: string) => string {
    const locale = useAppStore((s) => s.locale) as Locale;
    return (group: string) => translateGroupName(group, locale);
}

export { type Locale };
