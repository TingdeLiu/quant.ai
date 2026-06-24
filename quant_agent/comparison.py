from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def write_strategy_comparison(report_dirs: list[Path], output_dir: Path) -> pd.DataFrame:
    rows = [_report_row(report_dir) for report_dir in report_dirs]
    comparison = pd.DataFrame(rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_comparison_charts(report_dirs, output_dir)
    comparison.to_csv(output_dir / "strategy_comparison.csv", index=False)
    (output_dir / "strategy_comparison.md").write_text(_comparison_markdown(comparison), encoding="utf-8")
    (output_dir / "index.html").write_text(_comparison_html(comparison), encoding="utf-8")
    return comparison


def _report_row(report_dir: Path) -> dict[str, Any]:
    audit_path = report_dir / "audit.json"
    with audit_path.open("r", encoding="utf-8") as f:
        audit = json.load(f)
    metrics = audit.get("metrics", {})
    test = _period(audit.get("period_metrics", []), "test")
    return {
        "name": report_dir.name,
        "report_dir": str(report_dir),
        "overall_total_return": metrics.get("total_return"),
        "overall_cagr": metrics.get("cagr"),
        "overall_sharpe": metrics.get("sharpe"),
        "overall_sortino": metrics.get("sortino"),
        "overall_max_drawdown": metrics.get("max_drawdown"),
        "overall_alpha": metrics.get("alpha"),
        "overall_information_ratio": metrics.get("information_ratio"),
        "overall_excess_vs_equal_weight": metrics.get("excess_vs_equal_weight"),
        "test_total_return": test.get("total_return"),
        "test_cagr": test.get("cagr"),
        "test_sharpe": test.get("sharpe"),
        "test_sortino": test.get("sortino"),
        "test_max_drawdown": test.get("max_drawdown"),
        "test_alpha": test.get("alpha"),
        "test_information_ratio": test.get("information_ratio"),
    }


def _period(periods: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for period in periods:
        if period.get("period") == name:
            return period
    return {}


def _comparison_markdown(comparison: pd.DataFrame) -> str:
    columns = [
        "name",
        "overall_total_return",
        "overall_sharpe",
        "overall_max_drawdown",
        "overall_excess_vs_equal_weight",
        "test_total_return",
        "test_sharpe",
        "test_max_drawdown",
        "test_information_ratio",
    ]
    available = [column for column in columns if column in comparison.columns]
    lines = [
        "# Strategy Comparison",
        "",
        "![Equity comparison](equity_comparison.svg)",
        "",
        "![Drawdown comparison](drawdown_comparison.svg)",
        "",
        "| " + " | ".join(available) + " |",
        "| " + " | ".join(["---"] * len(available)) + " |",
    ]
    for _, row in comparison.iterrows():
        values = []
        for column in available:
            value = row[column]
            if column == "name":
                values.append(str(value))
            elif pd.isna(value):
                values.append("")
            else:
                values.append(f"{float(value):.4f}")
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def _comparison_html(comparison: pd.DataFrame) -> str:
    columns = [
        "name",
        "overall_total_return",
        "overall_sharpe",
        "overall_max_drawdown",
        "overall_excess_vs_equal_weight",
        "test_total_return",
        "test_sharpe",
        "test_max_drawdown",
        "test_information_ratio",
    ]
    available = [column for column in columns if column in comparison.columns]
    best_test = comparison.sort_values("test_sharpe", ascending=False).iloc[0] if "test_sharpe" in comparison else None
    rows = "\n".join(
        "<tr>"
        + "".join(
            f"<td>{_escape(row[column])}</td>" if column == "name" else f"<td>{_format_cell(row[column])}</td>"
            for column in available
        )
        + "</tr>"
        for _, row in comparison.iterrows()
    )
    headers = "".join(f"<th>{_escape(column)}</th>" for column in available)
    conclusion = ""
    if best_test is not None:
        conclusion = (
            f"Best test-period Sharpe is <strong>{_escape(best_test['name'])}</strong> "
            f"at <strong>{float(best_test['test_sharpe']):.2f}</strong>."
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Strategy Comparison</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #111827; background: #ffffff; }}
    main {{ max-width: 1180px; margin: 0 auto; }}
    h1 {{ font-size: 28px; margin-bottom: 8px; }}
    h2 {{ font-size: 20px; margin-top: 32px; }}
    .note {{ color: #4b5563; margin-bottom: 24px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px 10px; text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ background: #f3f4f6; }}
    img {{ width: 100%; max-width: 960px; border: 1px solid #e5e7eb; margin: 8px 0 20px; }}
    .callout {{ background: #f9fafb; border-left: 4px solid #2563eb; padding: 12px 14px; margin: 18px 0; }}
  </style>
</head>
<body>
<main>
  <h1>Strategy Comparison</h1>
  <p class="note">Generated from report audit files. Values are research/backtest diagnostics, not trading recommendations.</p>
  <div class="callout">{conclusion}</div>
  <h2>Summary Table</h2>
  <table>
    <thead><tr>{headers}</tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <h2>Equity Curve</h2>
  <img src="equity_comparison.svg" alt="Normalized equity comparison">
  <h2>Drawdown</h2>
  <img src="drawdown_comparison.svg" alt="Drawdown comparison">
</main>
</body>
</html>
"""


def _write_comparison_charts(report_dirs: list[Path], output_dir: Path) -> None:
    curves = []
    for report_dir in report_dirs:
        path = report_dir / "equity_curve.csv"
        if not path.exists():
            continue
        curve = pd.read_csv(path)
        if curve.empty or "date" not in curve.columns or "equity" not in curve.columns:
            continue
        curve["date"] = pd.to_datetime(curve["date"])
        curve["name"] = report_dir.name
        curve["normalized_equity"] = curve["equity"] / curve["equity"].iloc[0]
        curve["drawdown"] = curve["equity"] / curve["equity"].cummax() - 1
        curves.append(curve)
    if not curves:
        return
    all_curves = pd.concat(curves, ignore_index=True)
    _line_chart(
        all_curves,
        output_dir / "equity_comparison.svg",
        y_column="normalized_equity",
        title="Normalized Equity Comparison",
        y_label="Growth of $1",
    )
    _line_chart(
        all_curves,
        output_dir / "drawdown_comparison.svg",
        y_column="drawdown",
        title="Drawdown Comparison",
        y_label="Drawdown",
    )


def _line_chart(frame: pd.DataFrame, path: Path, y_column: str, title: str, y_label: str) -> None:
    width = 960
    height = 520
    left = 70
    right = 24
    top = 54
    bottom = 70
    plot_width = width - left - right
    plot_height = height - top - bottom
    dates = pd.to_datetime(frame["date"])
    min_date = dates.min()
    max_date = dates.max()
    min_y = float(frame[y_column].min())
    max_y = float(frame[y_column].max())
    if min_y == max_y:
        min_y -= 1.0
        max_y += 1.0
    colors = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf"]
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width / 2}" y="28" text-anchor="middle" font-family="Arial" font-size="20" font-weight="700">{_escape(title)}</text>',
        f'<text x="18" y="{height / 2}" transform="rotate(-90 18 {height / 2})" text-anchor="middle" font-family="Arial" font-size="13">{_escape(y_label)}</text>',
        f'<text x="{width / 2}" y="{height - 16}" text-anchor="middle" font-family="Arial" font-size="13">Date</text>',
    ]
    for i in range(5):
        y = top + plot_height * i / 4
        value = max_y - (max_y - min_y) * i / 4
        lines.append(f'<line x1="{left}" y1="{y:.2f}" x2="{width - right}" y2="{y:.2f}" stroke="#e5e7eb"/>')
        lines.append(f'<text x="{left - 8}" y="{y + 4:.2f}" text-anchor="end" font-family="Arial" font-size="11">{value:.2f}</text>')
    lines.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}" stroke="#111827"/>')
    lines.append(f'<line x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}" stroke="#111827"/>')
    for index, (name, group) in enumerate(frame.groupby("name", sort=False)):
        group = group.sort_values("date")
        points = " ".join(
            f"{_scale_date(row.date, min_date, max_date, left, plot_width):.2f},{_scale_y(float(getattr(row, y_column)), min_y, max_y, top, plot_height):.2f}"
            for row in group.itertuples(index=False)
        )
        color = colors[index % len(colors)]
        lines.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>')
        legend_y = top + 18 + index * 20
        legend_x = width - right - 210
        lines.append(f'<line x1="{legend_x}" y1="{legend_y}" x2="{legend_x + 24}" y2="{legend_y}" stroke="{color}" stroke-width="3"/>')
        lines.append(f'<text x="{legend_x + 32}" y="{legend_y + 4}" font-family="Arial" font-size="12">{_escape(name)}</text>')
    lines.append(f'<text x="{left}" y="{height - bottom + 24}" text-anchor="middle" font-family="Arial" font-size="11">{min_date.date()}</text>')
    lines.append(f'<text x="{width - right}" y="{height - bottom + 24}" text-anchor="middle" font-family="Arial" font-size="11">{max_date.date()}</text>')
    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def _scale_date(value: pd.Timestamp, min_date: pd.Timestamp, max_date: pd.Timestamp, left: int, plot_width: int) -> float:
    span = max((max_date - min_date).days, 1)
    return left + ((pd.Timestamp(value) - min_date).days / span) * plot_width


def _scale_y(value: float, min_y: float, max_y: float, top: int, plot_height: int) -> float:
    return top + (max_y - value) / (max_y - min_y) * plot_height


def _escape(value: object) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _format_cell(value: object) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.4f}"
