# 贡献指南

感谢你愿意为 quant.ai 出一份力！

## 开始之前

本项目是**美股量化研究与回测工具**。所有输出仅供研究参考，**不构成投资建议**。
提交涉及"交易信号 / 评级 / 建议"的改动时，请保持这一边界：代码可以做研究分析，但不应给出确定性的下单指令。

## 开发环境

推荐 conda：

```powershell
conda env create -f environment.yml
conda activate quant-ai
```

或使用 pip：

```powershell
pip install -r requirements.txt
```

## 提交流程

1. Fork 并基于 `main` 创建特性分支（`feat/xxx`、`fix/xxx`）。
2. 编写代码，并为新逻辑补充测试。
3. 本地运行测试，确保全部通过：

   ```powershell
   python -m pytest -q
   ```

4. 提交 PR，按模板填写说明并关联 Issue。CI 会在 Python 3.11 / 3.12 上自动跑测试。

## 代码风格

- 与周围代码保持一致：命名、注释密度、惯用法。
- 面向用户的文案使用简体中文，技术标识符保持原文。
- 不要把网络/数据源异常直接抛给普通用户，应降级为可读的中文提示（参考 `quant_agent/analyze.py`）。

## 报告问题

请使用 [Issue 模板](.github/ISSUE_TEMPLATE/) 提交 Bug 或功能建议。
**请勿提交个股投资咨询类问题**——本项目不提供投资建议。
