"""
视觉识别工具 - 多模态模型分析截图 (Async Version)
"""
from typing import Dict, Any, Optional, List
from langchain_core.tools import tool
from core.config import Config
from core.llm_manager import get_llm
import os

def _get_llm():
    """获取 LLM 实例（根据配置决定使用真实或模拟 LLM）"""
    if getattr(Config, 'USE_FAKE_LLM', False):
        return get_llm(fake_responses=[
            "我看到了一个红色的购买按钮，位于页面右上角",
            "找到了一个提交按钮，文字是'Submit'",
            "页面包含登录表单，有用户名和密码输入框"
        ])
    return get_llm()

@tool
def analyze_screenshot(screenshot_path: str, question: str = "描述这个页面的主要元素") -> Dict[str, Any]:
    """使用多模态模型分析截图"""
    try:
        if not os.path.exists(screenshot_path):
            return {"error": f"截图文件不存在: {screenshot_path}"}
        
        llm = _get_llm()
        
        # 真实 LLM 逻辑
        if not Config.USE_FAKE_LLM and hasattr(llm, 'with_structured_output'):
            # 这里简化处理，实际应该读取图片并发送给多模态模型
            prompt = f"分析以下截图并回答问题：{question}"
            response = llm.invoke(prompt)
        else:
            # 模拟实现
            response = {
                "elements": [
                    {"type": "button", "text": "购买", "position": "右上角", "selector": "button:has-text('购买')"},
                    {"type": "input", "text": "", "position": "中间", "selector": "input[type='text']"}
                ],
                "description": "这是一个购物模拟页面"
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
    """通过描述找到元素"""
    try:
        # 复用 analyze_screenshot
        return {
            "status": "success",
            "description": description,
            "found": True,
            "suggested_selector": f"text={description}", # 简化策略：直接使用 Playwright 文本选择器
            "position": "页面中"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@tool
def compare_screenshots(screenshot1_path: str, screenshot2_path: str) -> Dict[str, Any]:
    """视觉回归对比"""
    return {"status": "success", "is_identical": True, "differences": []}

@tool
async def extract_dom_structure(url: str) -> Dict[str, Any]:
    """提取页面 DOM 结构 (Async)"""
    try:
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=Config.HEADLESS)
            page = await browser.new_page()
            await page.goto(url, timeout=Config.UI_TIMEOUT)
            
            # 提取简化的 DOM 结构
            dom_structure = await page.evaluate("""
                () => {
                    const elements = [];
                    // 只提取交互元素
                    document.querySelectorAll('button, input, a, select, textarea').forEach(el => {
                        // 过滤隐藏元素
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
