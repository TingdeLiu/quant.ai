from __future__ import annotations

from typing import Any


class ResearchReviewAgent:
    """Template-based reviewer; it never emits broker/order instructions.

    这里刻意不接任何 LLM API：本项目通过 MCP 挂在 AI 客户端里用，综合与解读由宿主模型
    完成，服务端只负责产出可核对的结构化事实。
    """

    def review(self, metrics: dict[str, float], risk_checks: list[dict[str, object]]) -> str:
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

    def review_with_metadata(
        self,
        metrics: dict[str, float],
        risk_checks: list[dict[str, object]],
    ) -> tuple[str, dict[str, Any]]:
        return self.review(metrics, risk_checks), {"mode": "offline_template"}
