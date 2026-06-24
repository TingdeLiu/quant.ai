from __future__ import annotations

import json
from typing import Any

from quant_agent.config import LLMConfig
from quant_agent.llm import generate_llm_review


class ResearchReviewAgent:
    """Template-based reviewer; it never emits broker/order instructions."""

    def review(self, metrics: dict[str, float], risk_checks: list[dict[str, object]]) -> str:
        review, _ = self.review_with_metadata(metrics, risk_checks, None)
        return review

    def review_with_metadata(
        self,
        metrics: dict[str, float],
        risk_checks: list[dict[str, object]],
        llm_config: LLMConfig | None,
        context: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        offline_review = self._offline_review(metrics, risk_checks)
        prompt = _review_prompt(metrics, risk_checks, context or {})
        llm_text, llm_metadata = generate_llm_review(llm_config, prompt) if llm_config else (None, {"enabled": False})
        if not llm_text:
            return offline_review, {"mode": "offline_template", "llm": llm_metadata}
        return (
            offline_review
            + "\n"
            + "## LLM Research Commentary\n\n"
            + llm_text.strip()
            + "\n\n"
            + "This LLM commentary is explanatory only and does not authorize paper or live trading.\n",
            {"mode": "llm_augmented", "llm": llm_metadata},
        )

    def _offline_review(self, metrics: dict[str, float], risk_checks: list[dict[str, object]]) -> str:
        passed = all(bool(check["passed"]) for check in risk_checks)
        risk_lines = "\n".join(
            f"- [{'x' if check['passed'] else ' '}] {check['code']}: {check['message']}" for check in risk_checks
        )
        verdict = "PASS" if passed and metrics.get("max_drawdown", 0.0) > -0.5 else "REVIEW_REQUIRED"
        return (
            "## Research Review\n\n"
            f"Verdict: **{verdict}**\n\n"
            "This review is explanatory only. It does not authorize live or paper trading.\n\n"
            "### Key Metrics\n\n"
            f"- Total return: {metrics.get('total_return', 0.0):.2%}\n"
            f"- CAGR: {metrics.get('cagr', 0.0):.2%}\n"
            f"- Sharpe: {metrics.get('sharpe', 0.0):.2f}\n"
            f"- Sortino: {metrics.get('sortino', 0.0):.2f}\n"
            f"- Calmar: {metrics.get('calmar', 0.0):.2f}\n"
            f"- Max drawdown: {metrics.get('max_drawdown', 0.0):.2%}\n"
            f"- Beta: {metrics.get('beta', 0.0):.2f}\n"
            f"- Alpha: {metrics.get('alpha', 0.0):.2%}\n"
            f"- Information ratio: {metrics.get('information_ratio', 0.0):.2f}\n"
            f"- Average turnover: {metrics.get('average_turnover', 0.0):.2%}\n"
            f"- Average holding days: {metrics.get('average_holding_days', 0.0):.1f}\n\n"
            "### Risk Checks\n\n"
            f"{risk_lines}\n\n"
            "### Notes\n\n"
            "- Treat yfinance data as prototype-grade, not production point-in-time data.\n"
            "- Promote a strategy only after walk-forward testing and paper trading infrastructure exist.\n"
        )


def _review_prompt(metrics: dict[str, float], risk_checks: list[dict[str, object]], context: dict[str, Any]) -> str:
    payload = {
        "metrics": metrics,
        "risk_checks": risk_checks,
        "context": context,
        "constraints": [
            "Research commentary only.",
            "Do not produce broker orders or trading instructions.",
            "Focus on risks, anomalies, and validation gaps.",
        ],
    }
    return json.dumps(payload, indent=2, default=str)
