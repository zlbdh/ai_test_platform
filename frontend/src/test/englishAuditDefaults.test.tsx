import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import I18nA11yPage from '../pages/I18nA11yPage';
import QualityAudit from '../components/QualityAudit';

const fetchMock = vi.fn();
beforeEach(() => {
    localStorage.clear();
    fetchMock.mockReset().mockResolvedValue({ ok: true, json: async () => ({ issues: [], score: 100, total_issues: 0, total: 0 }) });
    vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function latestBody() {
    return JSON.parse(fetchMock.mock.lastCall![1].body);
}

describe('English audit locale defaults', () => {
    it('uses en-US by default and for an empty quick-check locale while allowing explicit locales', async () => {
        render(<MemoryRouter><I18nA11yPage /></MemoryRouter>);
        fireEvent.change(screen.getByPlaceholderText('https://example.com'), { target: { value: 'https://example.com' } });
        const locales = screen.getByPlaceholderText('en-US, es-US, fr-CA');
        expect(locales).toHaveValue('en-US');
        for (const [input, expected] of [['en-US', 'en-US'], ['fr-CA', 'fr-CA'], ['', 'en-US']]) {
            fireEvent.change(locales, { target: { value: input } });
            fireEvent.click(screen.getByRole('button', { name: 'i18n' }));
            await waitFor(() => expect(latestBody().locale).toBe(expected));
            await waitFor(() => expect(screen.getByRole('button', { name: 'i18n' })).not.toBeDisabled());
        }
    });

    it('keeps explicit full-audit locale lists and defaults quick checks to en-US', async () => {
        render(<MemoryRouter><QualityAudit /></MemoryRouter>);
        fireEvent.click(screen.getByRole('button', { name: 'Internationalization' }));
        fireEvent.change(screen.getByPlaceholderText('Enter a URL to audit (for example, https://example.com)'), { target: { value: 'https://example.com' } });
        const locales = screen.getByPlaceholderText('en-US, es-US, fr-CA');
        expect(locales).toHaveValue('en-US');
        fireEvent.click(screen.getByRole('button', { name: 'Full audit' }));
        await waitFor(() => expect(latestBody().locales).toEqual(['en-US']));
        await waitFor(() => expect(screen.getByRole('button', { name: 'Full audit' })).not.toBeDisabled());
        fireEvent.change(locales, { target: { value: 'fr-CA, es-US' } });
        fireEvent.click(screen.getByRole('button', { name: 'Full audit' }));
        await waitFor(() => expect(latestBody().locales).toEqual(['fr-CA', 'es-US']));
        await waitFor(() => expect(screen.getByRole('button', { name: 'Quick check' })).not.toBeDisabled());
        fireEvent.change(locales, { target: { value: '' } });
        fireEvent.click(screen.getByRole('button', { name: 'Quick check' }));
        await waitFor(() => expect(latestBody().locale).toBe('en-US'));
    });
});
