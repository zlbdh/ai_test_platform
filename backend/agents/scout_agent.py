import logging
import asyncio
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

class ScoutAgent:
    """
    侦察兵 (The Scout): 负责在规划前快速访问页面，获取真实上下文。
    实现 "Crawl-First" 架构的核心组件。
    """
    
    @staticmethod
    async def scout(url: str) -> dict:
        """
        快速侦察指定 URL
        返回: {title, url, visible_text, interactive_summary, status}
        """
        logger.info(f"[Scout] 🕵️ Starting reconnaissance for: {url}")
        
        try:
            async with async_playwright() as p:
                # 使用轻量级无头模式
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={'width': 1280, 'height': 800},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                
                # 防检测脚本
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                """)
                
                page = await context.new_page()
                
                # 1. 访问页面 (设置较短超时，避免卡死)
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                    # 稍作等待以加载动态内容
                    await page.wait_for_load_state('networkidle', timeout=5000)
                except Exception as naval_e:
                    logger.warning(f"[Scout] Navigation timeout/warning: {naval_e}")
                    # 继续尝试提取，可能只是部分资源慢
                
                # 2. 获取基本信息
                title = await page.title()
                current_url = page.url
                
                # 3. 提取可见文本摘要
                visible_text = await page.evaluate("""() => {
                    // 获取主要文本，过滤脚本和样式
                    const clone = document.body.cloneNode(true);
                    const treeWalker = document.createTreeWalker(
                        clone,
                        NodeFilter.SHOW_ELEMENT,
                        {
                            acceptNode: (node) => {
                                const tag = node.tagName.toLowerCase();
                                if (['script', 'style', 'noscript', 'svg'].includes(tag)) return NodeFilter.FILTER_REJECT;
                                return NodeFilter.FILTER_ACCEPT;
                            }
                        }
                    );
                    
                    // 简单粗暴清理
                    let text = clone.innerText || '';
                    return text.substring(0, 1500)
                        .replace(/\\s+/g, ' ')
                        .trim();
                }""")
                
                # 4. 提取关键交互元素 (用于辅助 LLM 认知页面功能)
                interactive_summary = await page.evaluate("""() => {
                    const els = document.querySelectorAll('button, a, input, select, textarea');
                    let results = [];
                    let seen = new Set();
                    
                    els.forEach(el => {
                        // 忽略不可见元素
                        if (el.offsetParent === null) return;
                        
                        let text = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim();
                        text = text.replace(/\\s+/g, ' ').substring(0, 20);
                        
                        if (!text) return; // 忽略无文本元素
                        
                        let tag = el.tagName.toLowerCase();
                        if (tag === 'input') tag = el.type || 'input';
                        
                        let entry = `[${tag}] ${text}`;
                        if (!seen.has(entry)) {
                            results.push(entry);
                            seen.add(entry);
                        }
                    });
                    
                    // 优先返回前 50 个关键元素
                    return results.slice(0, 50).join(', ');
                }""")
                
                logger.info(f"[Scout] Report: Title='{title}', Elements={len(interactive_summary)} chars")
                
                await browser.close()
                
                return {
                    "status": "success",
                    "title": title,
                    "url": current_url,
                    "visible_text": visible_text,
                    "interactive_summary": interactive_summary
                }
                
        except Exception as e:
            logger.error(f"[Scout] Failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "title": "Error",
                "visible_text": "",
                "interactive_summary": ""
            }
