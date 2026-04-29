# -*- coding: utf-8 -*-
"""
Evaluation Reporter — 评估报告生成器

生成 JSON/HTML 格式的评估报告，支持对比和趋势分析。
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import json
import time
import os
import logging

logger = logging.getLogger(__name__)


class EvaluationReporter:
    """评估报告生成器"""

    def __init__(self):
        self._report_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "evaluation_reports"
        )
        os.makedirs(self._report_dir, exist_ok=True)

    def generate_summary(
        self,
        metric_results: Dict[str, Any],
        judge_result: Optional[Dict] = None,
        overall_score: float = 0.0,
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """生成单次评估摘要"""
        report = {
            "report_type": "evaluation_summary",
            "generated_at": time.time(),
            "overall_score": round(overall_score, 4),
            "grade": self._score_to_grade(overall_score),
            "metrics": {},
            "recommendations": [],
        }

        if context:
            report["context"] = {
                "agent": context.get("agent_name", ""),
                "goal": context.get("goal", ""),
                "session_id": context.get("session_id", ""),
                "model": context.get("model", ""),
            }

        # 处理指标结果
        for name, result in metric_results.items():
            if hasattr(result, "to_dict"):
                report["metrics"][name] = result.to_dict()
            elif isinstance(result, dict):
                report["metrics"][name] = result

        # 添加 LLM Judge 结果
        if judge_result:
            report["judge"] = judge_result if isinstance(judge_result, dict) else judge_result.to_dict() if hasattr(judge_result, 'to_dict') else {}

        # 生成建议
        report["recommendations"] = self._generate_recommendations(metric_results, overall_score)

        return report

    def generate_comparison(
        self,
        run_results: List[Dict],
    ) -> Dict[str, Any]:
        """生成模型/配置对比报告"""
        if not run_results:
            return {"report_type": "comparison", "message": "无数据"}

        report = {
            "report_type": "comparison",
            "generated_at": time.time(),
            "total_runs": len(run_results),
            "entries": [],
            "best_model": "",
            "summary": "",
        }

        model_scores = {}
        for r in run_results:
            model = r.get("model", "unknown")
            score = r.get("overall_score", 0)
            if model not in model_scores:
                model_scores[model] = []
            model_scores[model].append(score)

            report["entries"].append({
                "run_id": r.get("run_id", ""),
                "model": model,
                "scenario_id": r.get("scenario_id", ""),
                "success": r.get("success", False),
                "overall_score": round(score, 4),
                "duration_ms": r.get("duration_ms", 0),
                "total_tokens": r.get("total_tokens", 0),
            })

        # 找最佳模型
        if model_scores:
            avg_scores = {m: sum(s) / len(s) for m, s in model_scores.items()}
            best = max(avg_scores, key=avg_scores.get)
            report["best_model"] = best
            report["model_averages"] = {m: round(s, 4) for m, s in avg_scores.items()}
            report["summary"] = f"最佳模型: {best} (平均分: {avg_scores[best]:.4f})"

        return report

    def generate_trend(self, run_results: List[Dict]) -> Dict[str, Any]:
        """生成趋势分析报告"""
        if not run_results:
            return {"report_type": "trend", "message": "无数据"}

        # 按时间排序
        sorted_results = sorted(run_results, key=lambda r: r.get("timestamp", 0))

        report = {
            "report_type": "trend",
            "generated_at": time.time(),
            "total_runs": len(sorted_results),
            "data_points": [],
            "trend_direction": "",
        }

        scores = []
        for r in sorted_results:
            score = r.get("overall_score", 0)
            scores.append(score)
            report["data_points"].append({
                "timestamp": r.get("timestamp", 0),
                "score": round(score, 4),
                "model": r.get("model", ""),
                "success": r.get("success", False),
            })

        # 简易趋势判断
        if len(scores) >= 3:
            first_half = sum(scores[:len(scores)//2]) / (len(scores)//2)
            second_half = sum(scores[len(scores)//2:]) / (len(scores) - len(scores)//2)
            if second_half > first_half + 0.05:
                report["trend_direction"] = "improving"
            elif second_half < first_half - 0.05:
                report["trend_direction"] = "declining"
            else:
                report["trend_direction"] = "stable"

        return report

    def save_report(self, report: Dict, name: str = "") -> str:
        """保存报告到文件"""
        if not name:
            name = f"eval_{report.get('report_type', 'report')}_{int(time.time())}"
        filepath = os.path.join(self._report_dir, f"{name}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"评估报告已保存: {filepath}")
        return filepath

    @staticmethod
    def _score_to_grade(score: float) -> str:
        """分数转等级"""
        if score >= 0.9:
            return "A+"
        elif score >= 0.8:
            return "A"
        elif score >= 0.7:
            return "B"
        elif score >= 0.6:
            return "C"
        elif score >= 0.5:
            return "D"
        else:
            return "F"

    @staticmethod
    def _generate_recommendations(
        metric_results: Dict[str, Any],
        overall_score: float,
    ) -> List[str]:
        """根据评估结果生成改进建议"""
        recs = []

        for name, result in metric_results.items():
            score = result.score if hasattr(result, 'score') else result.get("score", 1.0)
            if score < 0.5:
                if name == "plan_completeness":
                    recs.append("🔴 规划步骤不够完整，建议检查 Prompt 是否明确描述了任务分解")
                elif name == "execution_fidelity":
                    recs.append("🔴 实际执行偏离计划较大，建议检查 Agent 的步骤跟踪机制")
                elif name == "healing_success_rate":
                    recs.append("🔴 自愈成功率偏低，建议增强视觉定位模型或调优 SoM 参数")
                elif name == "hallucination_score":
                    recs.append("🔴 检测到 Agent 幻觉行为，建议增加输出验证环节")
                elif name == "token_efficiency":
                    recs.append("🟡 Token 效率偏低，考虑优化 Prompt 长度或切换更经济的模型")
                elif name == "step_accuracy":
                    recs.append("🔴 首次尝试成功率不高，建议优化元素定位策略")
                elif name == "goal_achievement":
                    recs.append("🔴 目标未达成，需要排查根本原因")
            elif score < 0.7:
                if name == "token_efficiency":
                    recs.append("🟡 Token 消耗可优化，考虑使用缓存或 Snapshot 压缩")

        if overall_score >= 0.9:
            recs.append("✅ 整体表现优秀！")
        elif not recs:
            recs.append("🟢 整体表现良好，无紧急改进项")

        return recs
