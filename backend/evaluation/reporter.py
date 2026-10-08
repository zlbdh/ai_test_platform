# -*- coding: utf-8 -*-
"""
Evaluation Reporter — Evaluation report generator

Generate JSON/HTML evaluation reports with comparisons and trend analysis.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import json
import time
import os
import logging

logger = logging.getLogger(__name__)


class EvaluationReporter:
    """Evaluation report generator"""

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
        """Generate a summary of one evaluation"""
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

        # Process metric results
        for name, result in metric_results.items():
            if hasattr(result, "to_dict"):
                report["metrics"][name] = result.to_dict()
            elif isinstance(result, dict):
                report["metrics"][name] = result

        # Add LLM Judge results
        if judge_result:
            report["judge"] = judge_result if isinstance(judge_result, dict) else judge_result.to_dict() if hasattr(judge_result, 'to_dict') else {}

        # Generate recommendations
        report["recommendations"] = self._generate_recommendations(metric_results, overall_score)

        return report

    def generate_comparison(
        self,
        run_results: List[Dict],
    ) -> Dict[str, Any]:
        """Generate a model/configuration comparison report"""
        if not run_results:
            return {"report_type": "comparison", "message": "No data"}

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

        # Find the best model
        if model_scores:
            avg_scores = {m: sum(s) / len(s) for m, s in model_scores.items()}
            best = max(avg_scores, key=avg_scores.get)
            report["best_model"] = best
            report["model_averages"] = {m: round(s, 4) for m, s in avg_scores.items()}
            report["summary"] = f"Best model: {best} (average score: {avg_scores[best]:.4f})"

        return report

    def generate_trend(self, run_results: List[Dict]) -> Dict[str, Any]:
        """Generate a trend analysis report"""
        if not run_results:
            return {"report_type": "trend", "message": "No data"}

        # Sort chronologically
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

        # Determine the basic trend
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
        """Save the report to a file"""
        if not name:
            name = f"eval_{report.get('report_type', 'report')}_{int(time.time())}"
        filepath = os.path.join(self._report_dir, f"{name}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"Evaluation report saved: {filepath}")
        return filepath

    @staticmethod
    def _score_to_grade(score: float) -> str:
        """Convert a score to a grade"""
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
        """Generate improvement recommendations from evaluation results"""
        recs = []

        for name, result in metric_results.items():
            score = result.score if hasattr(result, 'score') else result.get("score", 1.0)
            if score < 0.5:
                if name == "plan_completeness":
                    recs.append("🔴 The planned steps are incomplete. Check whether the prompt clearly describes task decomposition")
                elif name == "execution_fidelity":
                    recs.append("🔴 Execution deviated substantially from the plan. Check the agent's step tracking")
                elif name == "healing_success_rate":
                    recs.append("🔴 Healing success is low. Improve the visual localization model or tune SoM parameters")
                elif name == "hallucination_score":
                    recs.append("🔴 Agent hallucinations were detected. Add output verification")
                elif name == "token_efficiency":
                    recs.append("🟡 Token efficiency is low. Shorten the prompt or consider a more economical model")
                elif name == "step_accuracy":
                    recs.append("🔴 First-attempt success is low. Improve the element location strategy")
                elif name == "goal_achievement":
                    recs.append("🔴 The goal was not achieved. Investigate the root cause")
            elif score < 0.7:
                if name == "token_efficiency":
                    recs.append("🟡 Token consumption can be improved. Consider caching or snapshot compression")

        if overall_score >= 0.9:
            recs.append("✅ Excellent overall performance!")
        elif not recs:
            recs.append("🟢 Good overall performance; no urgent improvements needed")

        return recs
