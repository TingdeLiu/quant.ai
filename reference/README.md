# AI Quant Trading Reference

整理日期: 2026-06-13

目标: 收集对「AI 量化交易美股 agent」有参考价值的 GitHub 项目和工程资料。这里优先保留能帮助我们设计研究、回测、风控、执行、LLM/RL agent 工作流的项目，而不是泛泛收藏交易脚本。

## 文件索引

- [01_github_projects.md](01_github_projects.md): 值得重点参考的 GitHub 项目，按用途分层。
- [02_agent_architecture_notes.md](02_agent_architecture_notes.md): 面向自研美股量化 agent 的架构拆解。
- [03_data_and_evaluation_checklist.md](03_data_and_evaluation_checklist.md): 数据、回测、评估和上线前检查表。
- [04_source_links.md](04_source_links.md): 官方项目链接和后续复核清单。

## 筛选原则

1. 与美股或通用多资产量化交易有直接关系。
2. 对 AI/RL/ML/LLM agent 有可迁移的设计价值。
3. 项目规模、文档、社区或工程结构值得参考。
4. 能帮助我们避免从零实现低层回测、事件驱动、数据管理或评估模块。
5. 明确标注不适合直接照搬的风险点。

## 推荐阅读顺序

1. 先看 Qlib、FinRL、LEAN，理解研究平台、RL 训练和生产级回测/执行的边界。
2. 再看 TradingAgents、FinGPT、RD-Agent，提炼 LLM agent、金融文本理解和自动研究工作流。
3. 最后看 vectorbt、PyBroker、Lumibot、NautilusTrader，决定我们自己的回测和实盘适配层如何拆分。

## 重要边界

这些资料只用于工程和研究参考，不构成投资建议。后续自研系统必须独立加入交易成本、滑点、停牌/退市、数据延迟、幸存者偏差、风险限额、审计日志和人工确认机制。
