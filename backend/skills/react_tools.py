from core.browser import get_clean_html, find_selector, analyze_with_som
from core.visual_tools import assert_visual_snapshot
from core.api_tools import http_request
from core.db_tools import execute_sql
import asyncio
import json
import re

def resolve_variables(text: str, context: dict) -> str:
    """Resolve ${var} placeholders"""
    if not isinstance(text, str): return text
    matches = re.findall(r"\$\{(.*?)\}", text)
    for var in matches:
        if var in context:
            text = text.replace(f"${{{var}}}", str(context[var]))
    return text

async def tool_goto(page, url, context=None):
    if context: url = resolve_variables(url, context)
    await page.goto(url, wait_until="networkidle")
    await asyncio.sleep(2)
    return f"Navigated to {url}"

async def tool_db_query(sql, context=None):
    if context: sql = resolve_variables(sql, context)
    # Generic SQL is fast enough to run valid sync, or could use run_in_executor
    res = execute_sql(sql)
    if res['status'] == 'error':
        return f"SQL Error: {res['error']}"
    if 'affected_rows' in res:
        return f"Executed. Affected rows: {res['affected_rows']}"
    return str(res['data'])

async def tool_fill(page, target, value, context=None):
    if context: value = resolve_variables(value, context)

    # Simple check if target is selector
    selector = target if target.startswith(("#", ".", "//")) else None

    if not selector:
         html = await get_clean_html(page)
         selector = await find_selector(html, target)

    try:
        # A. Preferred approach (text-based)
        # Try standard Playwright selectors for the fastest interaction.
        await page.locator(selector).fill(str(value))
        return f"Filled '{value}' into {target} ({selector})"
    except Exception as e:
        # B. Fallback approach (visual self-healing)
        # Trigger visual healing if the standard action fails (element not found or timeout).
        # print("Standard fill failed; calling AI visual recognition...")
        try:
             # 1. Call SoM analysis to get the element's visual ID
             som_id = await analyze_with_som(page, target)
             if som_id:
                 # 2. Use the visual ID to locate and interact with the element
                 await page.fill(f'[data-som-id="{som_id}"]', str(value))
                 return f"Visual Fill Success (SoM ID: {som_id})"
        except Exception:
            pass  # SoM fallback failed
        # C. All attempts failed
        return f"Failed to fill {target}: {str(e)[:100]}"

async def tool_click(page, target):
    selector = target if target.startswith(("#", ".", "//")) else None

    if not selector:
         html = await get_clean_html(page)
         selector = await find_selector(html, target)

         # Fallback check immediately if selector is empty (meaning pure text search failed)
         if not selector:
             try:
                 som_id = await analyze_with_som(page, target)
                 if som_id:
                     await page.click(f'[data-som-id="{som_id}"]')
                     return f"Visual Click Success (SoM ID: {som_id})"
             except Exception:
                 pass  # SoM click fallback failed

    # Special fix for Baidu search button if applicable
    if selector == "#kw" and "百度" in target: selector = "#su"

    try:
        await page.locator(selector).click(timeout=3000)
        return f"Clicked {target} ({selector})"
    except Exception as e:
        # Fallback: Visual SOM
        try:
             som_id = await analyze_with_som(page, target)
             if som_id:
                 await page.click(f'[data-som-id="{som_id}"]')
                 return f"Visual Click Success (SoM ID: {som_id})"
        except Exception:
            pass  # SoM fallback failed
        return f"Failed to click {target}: {str(e)[:100]}"

async def tool_assert(page, target):
    await asyncio.sleep(1)
    if target.lower() == 'title':
        return f"Page Title is: {await page.title()}"

    page_text = await page.inner_text("body")
    if target.lower() in page_text.lower():
        return f"Assertion Passed: Found '{target}' in page."
    else:
        return f"Assertion Failed: '{target}' NOT found."

async def tool_extract(page, var_name, selector, context):
    try:
        if await page.is_visible(selector):
            val = await page.locator(selector).first.input_value()
            if not val: val = await page.locator(selector).first.inner_text()
        else:
            val = "Not Found"

        context[var_name] = val
        return f"Extracted {var_name} = {val}"
    except Exception as e:
        return f"Extraction error: {e}"

async def tool_api_call(method, url, value=None, context=None):
    if context:
        url = resolve_variables(url, context)
        if value: value = resolve_variables(value, context)

    json_body = None
    if method in ['POST', 'PUT'] and value and value.strip().startswith('{'):
        try:
            json_body = json.loads(value)
        except json.JSONDecodeError:
            pass  # Not valid JSON, will use as raw value

    res = http_request(method, url, json_body=json_body)
    return str(res)

async def tool_visual_check(page, snapshot_name):
    """
    Perform a visual regression check against a baseline snapshot.
    """
    if not snapshot_name:
        return "Error: Snapshot name is required for visual check."

    result = await assert_visual_snapshot(page, snapshot_name)
    # Return full dict to be handled by agent
    return result

async def tool_ask_human(reason):
    from core.shared import SharedBrowserState

    SharedBrowserState.set_signal("PAUSED", reason=reason)

    # Return a message that will be logged
    return f"🚨 Requesting Human Help: {reason}. System PAUSED_FOR_USER."

async def tool_verify_db(table, condition, expected_count=None):
    from core.db_tools import snapshot_db
    res = snapshot_db(table, condition)
    if res['status'] == 'error':
        return f"DB Verification Error: {res['error']}"

    count = res.get('count', 0)
    data = res.get('data', [])

    if expected_count is not None:
        if count == int(expected_count):
             return f"DB Verification PASSED. Found {count} records in {table} where {condition}."
        else:
             return f"DB Verification FAILED. Expected {expected_count}, found {count}. Data: {data[:3]}"

    return f"DB Query Result: Found {count} records. Data: {data[:3]}..."

async def tool_backup_db(table_name="all"):
    from core.db_tools import backup_db
    res = backup_db(table_name if table_name and table_name.lower() != 'all' else None)
    if res['status'] == 'error':
        return f"Backup Error: {res['message']}"
    return f"✅ {res['message']}"

async def tool_snapshot_db(table_name, snapshot_name):
    from core.db_tools import snapshot_db
    res = snapshot_db(table_name, snapshot_name)
    if res['status'] == 'error':
        return f"Snapshot Error: {res['message']}"
    return f"Snapshot '{snapshot_name}' created for table '{table_name}'"

# Alias for compatibility
tool_assert_db = tool_verify_db
