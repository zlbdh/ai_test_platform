/** useT reads the locale from Zustand and returns a bound translation function.
 * Kept separate to avoid circular dependencies between i18n.ts and stores.
 * Usage: const tt = useT(); tt('nav.dashboard') => 'Control Center'.
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
