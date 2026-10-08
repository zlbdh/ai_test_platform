import os
from playwright.sync_api import Page, expect
import logging

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = "artifacts/snapshots"

def assert_visual_snapshot(page: Page, snapshot_name: str, threshold: float = 0.2, full_page: bool = False):
    """
    Visual regression assertion (Synchronous)
    :param snapshot_name: Snapshot filename (e.g., "login_page.png")
    :param threshold: Allowed difference ratio (0.0 - 1.0)
    :param full_page: Whether to capture the full page
    """
    # Ensure the directory exists
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)

    # Ensure the filename ends in .png
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
            "message": f"✅ Visual comparison passed: {snapshot_name}",
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
                    "message": f"⚠️ First run: baseline screenshot saved: {snapshot_name}",
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
                    "message": f"❌ Visual comparison failed (RMS: {rms:.2f})",
                    "details": {
                        "baseline": f"/artifacts/snapshots/{snapshot_name}",
                        "actual": f"/artifacts/snapshots/current_{snapshot_name}",
                        "diff": f"RMS Diff: {rms:.2f}"
                    }
                }

            return {
                "status": "success",
                "message": f"✅ Visual comparison passed (Manual RMS: {rms:.2f})",
                "details": {
                    "baseline": f"/artifacts/snapshots/{snapshot_name}",
                    "actual": f"/artifacts/snapshots/current_{snapshot_name}",
                    "diff": None
                }
            }

        except Exception as e:
            return {"status": "error", "message": f"Visual Check Fallback Error: {e}"}

    except AssertionError as e:
        # Capture the difference
        err_msg = str(e)
        return {
             "status": "error",
             "message": f"❌ Visual comparison failed: the interface changed.",
             "details": {"error": err_msg}
        }

    except Exception as e:
        return {"status": "error", "message": f"Visual Check Error: {e}"}
