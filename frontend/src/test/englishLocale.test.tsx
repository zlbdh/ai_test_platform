import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SUPPORTED_LOCALES, t, translateGroupName, type Locale } from '../i18n';
import AIReasoningPanel from '../components/AIReasoningPanel';
import { AgentType, type LogEntry } from '../types';

describe('English interface compatibility', () => {
    it('offers only US English and resolves legacy locales in English', () => {
        expect(SUPPORTED_LOCALES.map(item => item.code)).toEqual(['en-US']);
        expect(t('zh-CN' as Locale, 'nav.dashboard')).toBe('Control Center');
        expect(t('invalid' as Locale, 'nav.dashboard')).toBe('Control Center');
        expect(t('en-US', 'missing.message')).toBe('missing.message');
        expect(t('en-US', 'nav')).toBe('nav');
        expect(translateGroupName('主入口', 'zh-CN' as Locale)).toBe('Main Entry');
    });

    it('starts in English even when an older installation saved a different locale', async () => {
        localStorage.setItem('ai-test-locale', 'zh-CN');
        vi.resetModules();
        const { useAppStore } = await import('../stores/appStore');
        expect(useAppStore.getState().locale).toBe('en-US');
        useAppStore.getState().setLocale('en-US');
        expect(document.documentElement.lang).toBe('en-US');
        expect(localStorage.getItem('ai-test-locale')).toBe('en-US');
        localStorage.removeItem('ai-test-locale');
    });

    it.each(['Analysis: inspect the page', '分析页面'])('recognizes English and legacy reasoning logs: %s', message => {
        const logs: LogEntry[] = [{ timestamp: '10:00:00', level: 'INFO', agent: AgentType.PLANNER, message }];
        render(<AIReasoningPanel logs={logs} steps={[]} isExecuting={false} />);
        expect(screen.getByText('AI reasoning analysis')).toBeInTheDocument();
        expect(screen.queryByText('No AI decisions yet')).not.toBeInTheDocument();
    });
});
