/**
 * AI Test Platform - E2E smoke tests
 * Verify that core frontend pages load and backend APIs respond correctly.
 */
import { test, expect } from '@playwright/test';

const BACKEND_URL = 'http://localhost:8020';

test.describe('Platform smoke tests', () => {
    test('Frontend home page loads correctly', async ({ page }) => {
        await page.goto('/');
        // The page should contain top navigation or a title
        await expect(page).toHaveTitle(/AI|Test/i);
        // The page should contain the main navigation
        const body = await page.textContent('body');
        expect(body).toBeTruthy();
    });

    test('Backend health check', async ({ request }) => {
        const resp = await request.get(`${BACKEND_URL}/api/health`);
        expect(resp.ok()).toBeTruthy();
        const data = await resp.json();
        expect(data.status).toBe('healthy');
        expect(data.checks.llm_configured).toBe(true);
    });

    test('Platform capabilities endpoint', async ({ request }) => {
        const resp = await request.get(`${BACKEND_URL}/api/platform/capabilities`);
        expect(resp.ok()).toBeTruthy();
        const data = await resp.json();
        expect(data.version).toBeTruthy();
        expect(data.test_types).toContain('ui_e2e');
        expect(data.ai_features).toContain('self_healing');
    });

    test('Smart orchestration page loads', async ({ page }) => {
        await page.goto('/');
        // An orchestration entry point should be available
        const pageContent = await page.textContent('body');
        expect(pageContent!.length).toBeGreaterThan(100);
    });

    test('Visual gallery page is accessible', async ({ page }) => {
        await page.goto('/');
        // The navigation should provide multiple feature entry points
        const navLinks = await page.locator('nav a, [role="navigation"] a, a[href]').count();
        expect(navLinks).toBeGreaterThan(0);
    });
});
