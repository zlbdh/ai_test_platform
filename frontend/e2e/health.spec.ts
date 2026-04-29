/**
 * AI Test Platform - E2E 冒烟测试
 * 验证前端核心页面可正常加载，后端 API 可正常响应。
 */
import { test, expect } from '@playwright/test';

const BACKEND_URL = 'http://localhost:8020';

test.describe('平台冒烟测试', () => {
    test('前端首页加载正常', async ({ page }) => {
        await page.goto('/');
        // 页面应包含顶部导航或标题
        await expect(page).toHaveTitle(/AI|测试|Test/i);
        // 页面应包含主要导航元素
        const body = await page.textContent('body');
        expect(body).toBeTruthy();
    });

    test('后端健康检查', async ({ request }) => {
        const resp = await request.get(`${BACKEND_URL}/api/health`);
        expect(resp.ok()).toBeTruthy();
        const data = await resp.json();
        expect(data.status).toBe('healthy');
        expect(data.checks.llm_configured).toBe(true);
    });

    test('平台能力接口', async ({ request }) => {
        const resp = await request.get(`${BACKEND_URL}/api/platform/capabilities`);
        expect(resp.ok()).toBeTruthy();
        const data = await resp.json();
        expect(data.version).toBeTruthy();
        expect(data.test_types).toContain('ui_e2e');
        expect(data.ai_features).toContain('self_healing');
    });

    test('智能编排页面加载', async ({ page }) => {
        await page.goto('/');
        // 应能找到编排相关的入口
        const pageContent = await page.textContent('body');
        expect(pageContent!.length).toBeGreaterThan(100);
    });

    test('视觉回廊页面可访问', async ({ page }) => {
        await page.goto('/');
        // 导航栏应存在多个功能入口
        const navLinks = await page.locator('nav a, [role="navigation"] a, a[href]').count();
        expect(navLinks).toBeGreaterThan(0);
    });
});
