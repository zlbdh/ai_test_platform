import logging
import asyncio
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

class ScoutAgent:
    """
    The Scout: quickly visits pages before planning to obtain real context.
    Core component of the crawl-first architecture.
    """

    @staticmethod
    async def scout(url: str) -> dict:
        """
        Quickly inspect the specified URL
        Returns: {title, url, visible_text, interactive_summary, status}
        """
        logger.info(f"[Scout] 🕵️ Starting reconnaissance for: {url}")

        try:
            async with async_playwright() as p:
                # Use lightweight headless mode
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={'width': 1280, 'height': 800},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )

                # Detection prevention script
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                """)

                page = await context.new_page()

                # 1. Visit the page with a short timeout to avoid hanging
                try:
                    await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                    # Wait briefly for dynamic content to load
                    await page.wait_for_load_state('networkidle', timeout=5000)
                except Exception as naval_e:
                    logger.warning(f"[Scout] Navigation timeout/warning: {naval_e}")
                    # Continue extraction; only some resources may be slow

                # 2. Get basic information
                title = await page.title()
                current_url = page.url

                # 3. Extract a summary of visible text
                visible_text = await page.evaluate("""() => {
                    // Get the main text, excluding scripts and styles
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

                    // Basic cleanup
                    let text = clone.innerText || '';
                    return text.substring(0, 1500)
                        .replace(/\\s+/g, ' ')
                        .trim();
                }""")

                # 4. Extract key interactive elements to help the LLM understand page functions
                interactive_summary = await page.evaluate("""() => {
                    const els = document.querySelectorAll('button, a, input, select, textarea');
                    let results = [];
                    let seen = new Set();

                    els.forEach(el => {
                        // Ignore invisible elements
                        if (el.offsetParent === null) return;

                        let text = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim();
                        text = text.replace(/\\s+/g, ' ').substring(0, 20);

                        if (!text) return; // Ignore elements without text

                        let tag = el.tagName.toLowerCase();
                        if (tag === 'input') tag = el.type || 'input';

                        let entry = `[${tag}] ${text}`;
                        if (!seen.has(entry)) {
                            results.push(entry);
                            seen.add(entry);
                        }
                    });

                    // Prioritize returning the first 50 key elements
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
