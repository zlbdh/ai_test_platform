import os
from playwright.sync_api import Page, expect
import logging

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = "artifacts/snapshots"

def assert_visual_snapshot(page: Page, snapshot_name: str, threshold: float = 0.2, full_page: bool = False):
    """
    视觉回归断言 (Synchronous)
    :param snapshot_name: 快照文件名 (e.g., "login_page.png")
    :param threshold: 允许的差异比例 (0.0 - 1.0)
    :param full_page: 是否全页截图
    """
    # 确保目录存在
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    
    # 确保文件名以 .png 结尾
    if not snapshot_name.endswith(".png"):
        snapshot_name += ".png"
        
    try:
        expect(page).to_have_screenshot(
            name=snapshot_name,
            threshold=threshold,
            full_page=full_page,
            timeout=5000,
        )
        return {
            "status": "success", 
            "message": f"✅ 视觉比对通过: {snapshot_name}",
            "details": {
                "baseline": f"/artifacts/snapshots/{snapshot_name}",
                "actual": f"/artifacts/snapshots/{snapshot_name}", 
                "diff": None
            }
        }
        
    except AttributeError:
        # Fallback for environments where to_have_screenshot is missing (e.g. some sync playwright contexts)
        try:
            from PIL import Image, ImageChops
            import math
            
            baseline_path = os.path.join(SNAPSHOT_DIR, snapshot_name)
            current_path = os.path.join(SNAPSHOT_DIR, f"current_{snapshot_name}")
            
            # 1. Take current screenshot
            page.screenshot(path=current_path, full_page=full_page)
            
            # 2. Check if baseline exists
            if not os.path.exists(baseline_path):
                # Save current as baseline
                page.screenshot(path=baseline_path, full_page=full_page)
                return {
                    "status": "success",
                    "message": f"⚠️ 首次运行，已保存基准截图: {snapshot_name}",
                    "details": {
                        "baseline": f"/artifacts/snapshots/{snapshot_name}",
                        "actual": f"/artifacts/snapshots/current_{snapshot_name}",
                        "diff": None
                    }
                }
            
            # 3. Compare
            im1 = Image.open(baseline_path).convert('RGB')
            im2 = Image.open(current_path).convert('RGB')
            
            # Resize to match if needed (simple approach)
            if im1.size != im2.size:
                im2 = im2.resize(im1.size)
            
            diff = ImageChops.difference(im1, im2)
            histogram = diff.histogram()
            
            # Calculate RMS diff
            sq = (value * ((idx % 256) ** 2) for idx, value in enumerate(histogram))
            sum_of_squares = sum(sq)
            rms = math.sqrt(sum_of_squares / float(im1.size[0] * im1.size[1]))
            
            # Threshold check (heuristic)
            if rms > (threshold * 100): # Scale threshold
                 return {
                    "status": "error",
                    "message": f"❌ 视觉比对失败 (RMS: {rms:.2f})",
                    "details": {
                        "baseline": f"/artifacts/snapshots/{snapshot_name}",
                        "actual": f"/artifacts/snapshots/current_{snapshot_name}",
                        "diff": f"RMS Diff: {rms:.2f}"
                    }
                }
            
            return {
                "status": "success",
                "message": f"✅ 视觉比对通过 (Manual RMS: {rms:.2f})",
                "details": {
                    "baseline": f"/artifacts/snapshots/{snapshot_name}",
                    "actual": f"/artifacts/snapshots/current_{snapshot_name}",
                    "diff": None
                }
            }
                
        except Exception as e:
            return {"status": "error", "message": f"Visual Check Fallback Error: {e}"}

    except AssertionError as e:
        # 捕获差异
        err_msg = str(e)
        return {
             "status": "error", 
             "message": f"❌ 视觉比对失败! 界面发生了变动。",
             "details": {"error": err_msg}
        }
        
    except Exception as e:
        return {"status": "error", "message": f"Visual Check Error: {e}"}
