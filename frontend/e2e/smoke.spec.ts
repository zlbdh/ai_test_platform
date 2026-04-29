import { test, expect } from '@playwright/test';

test.describe('冒烟测试 — 基础页面可访问性', () => {
    test('首页加载成功', async ({ page }) => {
        await page.goto('/');
        await expect(page).toHaveTitle(/AI/i);
        // 侧边栏应渲染
        await expect(page.locator('nav, aside, [class*="sidebar"]').first()).toBeVisible();
    });

    test('导航到编排测试页面', async ({ page }) => {
        await page.goto('/orchestrator');
        // 页面应包含编排相关内容
        await expect(page.locator('body')).toContainText(/编排|测试|Orchestrator/i);
    });

    test('导航到批量测试页面', async ({ page }) => {
        await page.goto('/batch');
        await expect(page.locator('body')).toContainText(/批量|Batch/i);
    });

    test('导航到 API 工作台页面', async ({ page }) => {
        await page.goto('/api');
        await expect(page.locator('body')).toContainText(/API/i);
    });

    test('404 重定向到首页', async ({ page }) => {
        await page.goto('/this-does-not-exist');
        // 应该重定向到 /
        await expect(page).toHaveURL('/');
    });
});

test.describe('冒烟测试 — 后端 API 连通', () => {
    test('健康检查端点可达', async ({ request }) => {
        const response = await request.get('http://localhost:8020/');
        expect(response.ok()).toBeTruthy();
        const body = await response.json();
        expect(body.status).toBe('ok');
    });

    test('状态端点可达', async ({ request }) => {
        const response = await request.get('http://localhost:8020/api/status');
        expect(response.ok()).toBeTruthy();
        const body = await response.json();
        expect(body.status).toBeDefined();
    });
});
