"""让 setuptools 能把这个目录打包成 `quant_agent.templates`（见 pyproject 的 package-dir）。

仓库里配置就放在 `configs/`，安装后以 `quant_agent/templates/` 随 wheel 分发，
首次运行由 `quant_agent.paths.seed_user_config()` 播种到 `~/.quant-ai/configs/`。
一份源文件，没有副本要同步。不要删这个文件，否则 wheel 里不会带默认配置。
"""
