# Changelog

本项目的所有重要变更都会记录在此文件中。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增
- `init` 命令：首次使用交互式引导，问几个问题（感兴趣的板块、额外关注的公司、风险偏好）即可生成**个性化股票池**——2/3 来自用户自选（公司 + 板块的代表股），1/3 由系统在全市场候选目录里挑用户没选到的强势标的（按风险偏好对应的横截面信号打分）。输出 `configs/my_universe.csv` + `configs/my.yaml` + `configs/profile.json`；支持 `--non-interactive` / `--no-discovery`，无网络时优雅降级（只写自选部分并提示）。
- `refresh-universe` 命令：用已保存的偏好重算「发现池」1/3（市场会变），自选 2/3 不变。
- `analyze --watchlist`：直接分析个性化股票池 `configs/my_universe.csv`。
- `configs/catalog.csv`：~170 只流动美股的候选目录，按中文板块（科技 / 半导体 / 互联网与媒体 / 可选消费 / 必需消费 / 金融 / 医疗健康 / 能源 / 工业 / 材料 / 公用事业 / 房地产 / 宽基ETF）归类，作为 onboarding 选股与发现池打分的基础。
- `doctor` 命令：一键环境自检，检查 Python 版本、关键依赖与 Yahoo Finance 行情连通性，区分必需依赖（缺失即失败、退出码 1）和可选依赖（`pyarrow` / `matplotlib`，缺失仅提示），方便新用户和 CI 快速定位环境问题。
- `analyze` 命令：零配置、秒级分析一只或多只美股，输出中文评级（强烈看多 / 偏多 / 中性 / 偏空 / 强烈看空）、判断依据和参考关注位（支撑 / 止损）。
- `analyze --file`：从自选股文件读取股票代码（每行一个或逗号分隔，`#` 后为注释）。
- `analyze --chart`：配合 `--output-dir` 导出价格 + 均线 + RSI 的 PNG 图（自动适配中文字体）。
- `analyze --output-dir` / `--json`：导出 Markdown + JSON，或仅输出 JSON 供脚本调用。
- 网络/数据异常的友好降级：区分「网络不可用」「数据源无响应」「代码错误或退市」，给普通用户可读的中文提示，不再抛出原始堆栈。
- 开源工程基建：`pyproject.toml`（可 `pip install -e .`，提供 `quant-ai` 命令入口）、`LICENSE`（MIT）、`CONTRIBUTING.md`、GitHub Issue/PR 模板、CI（Python 3.11 / 3.12 自动跑测试）、`CHANGELOG.md`。

### 变更
- 工程基建：引入 `ruff`（lint，CI 强制门禁）；CI 测试矩阵新增 `windows-latest`，并加入覆盖率统计。
- 测试拆分：原 900+ 行单文件按主题拆为 `test_data` / `test_config` / `test_pipeline` / `test_market` / `test_server` / `test_analyze`，共享构造器收敛到 `tests/_helpers.py`。
- 控制台 HTML 生成从 `server.py` 抽离到 `quant_agent/web_templates.py`，`server.py` 体积减少约三分之一。

### 修复
- 参考止损位现在正确低于支撑位；价格跌破所有均线时支撑回退到 52 周低点。
- 均线显示统一保留两位小数。
- 受限 Windows 环境下系统临时目录被锁导致 `tmp_path` 测试 setup 失败的问题（`conftest.py` 自动探测并回退到项目内临时目录）。
- yfinance 缓存文件名由全量 ticker 拼接改为「数量 + 哈希」，避免大股票池超过 Windows 路径长度上限，并使 ticker 顺序不影响缓存命中。

### 性能
- yfinance 行情下载由逐只串行改为线程池并发（IO 密集、释放 GIL），大股票池下载耗时显著降低；保留单只指数退避重试与空数据跳过逻辑。

[Unreleased]: https://github.com/TingdeLiu/quant.ai/commits/main
