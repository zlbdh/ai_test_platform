"""
Visual Regression Testing - 视觉回归测试

支持：
- 截图对比
- 像素级差异检测
- 阈值控制
- 基线管理
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import os
import hashlib
import base64
import json


class ComparisonResult(Enum):
    MATCH = "match"
    MISMATCH = "mismatch"
    NEW_BASELINE = "new_baseline"
    ERROR = "error"


@dataclass
class ScreenshotData:
    """截图数据"""
    name: str
    filepath: str
    width: int
    height: int
    timestamp: str
    hash: str


@dataclass
class DiffResult:
    """差异结果"""
    baseline: ScreenshotData
    current: ScreenshotData
    result: ComparisonResult
    diff_percentage: float
    diff_filepath: Optional[str]
    threshold: float


class VisualRegressionTester:
    """视觉回归测试器"""
    
    def __init__(self, baseline_dir: str = "./data/baselines"):
        self.baseline_dir = baseline_dir
        self.results_dir = os.path.join(baseline_dir, "results")
        os.makedirs(self.baseline_dir, exist_ok=True)
        os.makedirs(self.results_dir, exist_ok=True)
        
        self._pillow_available = self._check_pillow()
    
    def _check_pillow(self) -> bool:
        """检查 Pillow 是否可用"""
        try:
            from PIL import Image
            return True
        except ImportError:
            return False
    
    def _compute_hash(self, filepath: str) -> str:
        """计算文件哈希"""
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def save_baseline(
        self,
        name: str,
        image_data: bytes,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ScreenshotData:
        """保存基线图片"""
        filepath = os.path.join(self.baseline_dir, f"{name}.png")
        
        with open(filepath, 'wb') as f:
            f.write(image_data)
        
        # 获取图片尺寸
        width, height = 0, 0
        if self._pillow_available:
            from PIL import Image
            img = Image.open(filepath)
            width, height = img.size
        
        screenshot = ScreenshotData(
            name=name,
            filepath=filepath,
            width=width,
            height=height,
            timestamp=datetime.now().isoformat(),
            hash=self._compute_hash(filepath)
        )
        
        # 保存元数据
        meta_filepath = os.path.join(self.baseline_dir, f"{name}.json")
        with open(meta_filepath, 'w') as f:
            json.dump({
                "name": screenshot.name,
                "width": screenshot.width,
                "height": screenshot.height,
                "timestamp": screenshot.timestamp,
                "hash": screenshot.hash,
                "custom": metadata
            }, f)
        
        return screenshot
    
    def compare(
        self,
        name: str,
        current_image: bytes,
        threshold: float = 0.01
    ) -> DiffResult:
        """比较图片"""
        baseline_path = os.path.join(self.baseline_dir, f"{name}.png")
        current_path = os.path.join(self.results_dir, f"{name}_current.png")
        
        # 保存当前图片
        with open(current_path, 'wb') as f:
            f.write(current_image)
        
        # 检查基线是否存在
        if not os.path.exists(baseline_path):
            # 新基线
            self.save_baseline(name, current_image)
            return DiffResult(
                baseline=ScreenshotData(name, baseline_path, 0, 0, "", ""),
                current=ScreenshotData(name, current_path, 0, 0, datetime.now().isoformat(), ""),
                result=ComparisonResult.NEW_BASELINE,
                diff_percentage=0,
                diff_filepath=None,
                threshold=threshold
            )
        
        # 比较
        if not self._pillow_available:
            # 简单哈希比较
            baseline_hash = self._compute_hash(baseline_path)
            current_hash = self._compute_hash(current_path)
            
            match = baseline_hash == current_hash
            return DiffResult(
                baseline=ScreenshotData(name, baseline_path, 0, 0, "", baseline_hash),
                current=ScreenshotData(name, current_path, 0, 0, datetime.now().isoformat(), current_hash),
                result=ComparisonResult.MATCH if match else ComparisonResult.MISMATCH,
                diff_percentage=0 if match else 100,
                diff_filepath=None,
                threshold=threshold
            )
        
        # Pillow 像素级比较
        from PIL import Image, ImageChops
        
        baseline_img = Image.open(baseline_path).convert('RGBA')
        current_img = Image.open(current_path).convert('RGBA')
        
        # 尺寸调整
        if baseline_img.size != current_img.size:
            current_img = current_img.resize(baseline_img.size)
        
        # 计算差异
        diff = ImageChops.difference(baseline_img, current_img)
        
        # 计算差异百分比
        diff_data = list(diff.getdata())
        total_pixels = len(diff_data)
        diff_pixels = sum(1 for pixel in diff_data if any(c > 10 for c in pixel[:3]))
        diff_percentage = (diff_pixels / total_pixels) * 100 if total_pixels > 0 else 0
        
        # 保存差异图
        diff_filepath = os.path.join(self.results_dir, f"{name}_diff.png")
        diff.save(diff_filepath)
        
        # 判断结果
        result = ComparisonResult.MATCH if diff_percentage <= threshold * 100 else ComparisonResult.MISMATCH
        
        return DiffResult(
            baseline=ScreenshotData(name, baseline_path, baseline_img.width, baseline_img.height, "", ""),
            current=ScreenshotData(name, current_path, current_img.width, current_img.height, datetime.now().isoformat(), ""),
            result=result,
            diff_percentage=round(diff_percentage, 4),
            diff_filepath=diff_filepath if result == ComparisonResult.MISMATCH else None,
            threshold=threshold
        )
    
    def update_baseline(self, name: str, current_image: bytes) -> bool:
        """更新基线"""
        try:
            self.save_baseline(name, current_image)
            return True
        except Exception:
            return False
    
    def list_baselines(self) -> List[Dict[str, Any]]:
        """列出所有基线"""
        baselines = []
        
        for filename in os.listdir(self.baseline_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.baseline_dir, filename)
                with open(filepath) as f:
                    baselines.append(json.load(f))
        
        return baselines
    
    def delete_baseline(self, name: str) -> bool:
        """删除基线"""
        png_path = os.path.join(self.baseline_dir, f"{name}.png")
        json_path = os.path.join(self.baseline_dir, f"{name}.json")
        
        try:
            if os.path.exists(png_path):
                os.remove(png_path)
            if os.path.exists(json_path):
                os.remove(json_path)
            return True
        except Exception:
            return False
    
    def generate_report(self, results: List[DiffResult]) -> Dict[str, Any]:
        """生成报告"""
        total = len(results)
        matches = sum(1 for r in results if r.result == ComparisonResult.MATCH)
        mismatches = sum(1 for r in results if r.result == ComparisonResult.MISMATCH)
        new_baselines = sum(1 for r in results if r.result == ComparisonResult.NEW_BASELINE)
        
        return {
            "summary": {
                "total": total,
                "passed": matches,
                "failed": mismatches,
                "new_baselines": new_baselines,
                "pass_rate": round(matches / total * 100, 2) if total > 0 else 0
            },
            "results": [
                {
                    "name": r.baseline.name,
                    "result": r.result.value,
                    "diff_percentage": r.diff_percentage,
                    "threshold": r.threshold,
                    "diff_image": r.diff_filepath
                }
                for r in results
            ]
        }


# 单例
_visual_tester: Optional[VisualRegressionTester] = None

def get_visual_tester() -> VisualRegressionTester:
    """获取视觉测试器"""
    global _visual_tester
    if _visual_tester is None:
        _visual_tester = VisualRegressionTester()
    return _visual_tester
