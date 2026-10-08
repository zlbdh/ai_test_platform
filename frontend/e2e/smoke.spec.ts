import { test, expect } from '@playwright/test';

test.describe('Smoke tests — basic page accessibility', () => {
    test('Home page loads successfully', async ({ page }) => {
        await page.goto('/');
        await expect(page).toHaveTitle(/AI/i);
        // The sidebar should render
        await expect(page.locator('nav, aside, [class*="sidebar"]').first()).toBeVisible();
    });

    test('Navigate to the orchestration test page', async ({ page }) => {
        await page.goto('/orchestrator');
        // The page should contain orchestration content
        await expect(page.locator('body')).toContainText(/Orchestrat|Test/i);
    });

    test('Navigate to the batch testing page', async ({ page }) => {
        await page.goto('/batch');
        await expect(page.locator('body')).toContainText(/Batch/i);
    });

    test('Navigate to the API workbench', async ({ page }) => {
        await page.goto('/api');
        await expect(page.locator('body')).toContainText(/API/i);
    });

    test('404 redirects to the home page', async ({ page }) => {
        await page.goto('/this-does-not-exist');
        // Should redirect to /
        await expect(page).toHaveURL('/');
    });
});

test.describe('Smoke tests — backend API connectivity', () => {
    test('Health check endpoint is reachable', async ({ request }) => {
        const response = await request.get('http://localhost:8020/');
        expect(response.ok()).toBeTruthy();
        const body = await response.json();
        expect(body.status).toBe('ok');
    });

    test('Status endpoint is reachable', async ({ request }) => {
        const response = await request.get('http://localhost:8020/api/status');
        expect(response.ok()).toBeTruthy();
        const body = await response.json();
        expect(body.status).toBeDefined();
    });
});
