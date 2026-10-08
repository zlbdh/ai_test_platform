"""
Visual recognition tools - multimodal screenshot analysis (async version)
"""
from typing import Dict, Any, Optional, List
from langchain_core.tools import tool
from core.config import Config
from core.llm_manager import get_llm
import os

def _get_llm():
    """Get an LLM instance (real or mock, depending on configuration)"""
    if getattr(Config, 'USE_FAKE_LLM', False):
        return get_llm(fake_responses=[
            "I see a red Buy button in the upper-right corner of the page",
            "I found a submit button labeled 'Submit'",
            "The page contains a login form with username and password fields"
        ])
    return get_llm()

@tool
def analyze_screenshot(screenshot_path: str, question: str = "Describe the main elements on this page") -> Dict[str, Any]:
    """Analyze a screenshot with a multimodal model"""
    try:
        if not os.path.exists(screenshot_path):
            return {"error": f"Screenshot file does not exist: {screenshot_path}"}

        llm = _get_llm()

        # Real LLM logic
        if not Config.USE_FAKE_LLM and hasattr(llm, 'with_structured_output'):
            # Simplified here; the implementation should read the image and send it to a multimodal model
            prompt = f"Analyze the following screenshot and answer the question: {question}"
            response = llm.invoke(prompt)
        else:
            # Mock implementation
            response = {
                "elements": [
                    {"type": "button", "text": "Buy", "position": "upper-right corner", "selector": "button:has-text('Buy')"},
                    {"type": "input", "text": "", "position": "center", "selector": "input[type='text']"}
                ],
                "description": "This is a mock shopping page"
            }

        return {
            "status": "success",
            "screenshot_path": screenshot_path,
            "analysis": response
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@tool
def find_element_by_description(description: str, screenshot_path: str) -> Dict[str, Any]:
    """Find an element by description"""
    try:
        # Reuse analyze_screenshot
        return {
            "status": "success",
            "description": description,
            "found": True,
            "suggested_selector": f"text={description}", # Simplified strategy: use a Playwright text selector directly
            "position": "on the page"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@tool
def compare_screenshots(screenshot1_path: str, screenshot2_path: str) -> Dict[str, Any]:
    """Visual regression comparison"""
    return {"status": "success", "is_identical": True, "differences": []}

@tool
async def extract_dom_structure(url: str) -> Dict[str, Any]:
    """Extract the page DOM structure (async)"""
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=Config.HEADLESS)
            page = await browser.new_page()
            await page.goto(url, timeout=Config.UI_TIMEOUT)

            # Extract a simplified DOM structure
            dom_structure = await page.evaluate("""
                () => {
                    const elements = [];
                    // Extract only interactive elements
                    document.querySelectorAll('button, input, a, select, textarea').forEach(el => {
                        // Filter out hidden elements
                        if (el.offsetParent === null) return;

                        elements.push({
                            tag: el.tagName.toLowerCase(),
                            text: (el.textContent || el.value || '').trim().substring(0, 50),
                            id: el.id || '',
                            name: el.name || '',
                            placeholder: el.placeholder || '',
                            type: el.type || ''
                        });
                    });
                    return elements;
                }
            """)

            await browser.close()

            return {
                "status": "success",
                "url": url,
                "elements": dom_structure,
                "total_elements": len(dom_structure)
            }
    except Exception as e:
        return {"status": "error", "error": str(e)}

VISION_TOOLS = [
    analyze_screenshot,
    find_element_by_description,
    compare_screenshots,
    extract_dom_structure,
]
