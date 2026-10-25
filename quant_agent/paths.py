"""配置与数据的落地位置：源码树跑和 pip 装完跑，用同一套解析链。

源码树里一切照旧（`./configs/my.yaml` 永远优先）；pip 装完则首次运行时把包内模板
播种到 `~/.quant-ai/configs/`，之后那个目录就等价于一个源码树。用户目录下那层
刻意叫 `configs` —— `config.py` 对该名字取祖父目录当数据根，于是数据自动落在
`~/.quant-ai/data`，不必为安装场景新增任何 base 规则，也永远不会写进 site-packages。
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

# 打包进 wheel 的模板配置。pyproject 把仓库里的 configs/ 映射成包内 quant_agent/templates，
# 所以仓库只有一份源文件，不存在两份要同步的副本。
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

# 播种时跳过的条目：setuptools 要求 configs/ 是个包才能映射，__init__.py 是为此存在的。
_SEED_SKIP = {"__init__.py", "__pycache__"}

# 不随 wheel 分发、也不播种的个人文件（和 .gitignore 对齐）。模板目录里本就不该有它们，
# 这里再挡一道，避免打包配置写错时把谁的自选股带进安装包。
PRIVATE_NAMES = frozenset({"my.yaml", "my_universe.csv", "profile.json"})

_DEFAULT_NAMES = ("my.yaml", "default.yaml")


def home() -> Path:
    """用户数据根目录：`$QUANT_AI_HOME`，默认 `~/.quant-ai`。"""
    override = os.environ.get("QUANT_AI_HOME")
    return Path(override).expanduser() if override else Path.home() / ".quant-ai"


def user_config_dir() -> Path:
    """`~/.quant-ai/configs`。名字必须是 configs，见模块文档。"""
    return home() / "configs"


def source_config_dir() -> Path:
    """源码树（或任何以仓库根为工作目录的调用）里的 `./configs`。"""
    return Path.cwd() / "configs"


def is_template(path: Path) -> bool:
    """`path` 是否落在包内模板目录——它只读，不能当数据根。"""
    try:
        return TEMPLATE_DIR in Path(path).resolve().parents
    except OSError:  # 路径解析失败就当作不是模板
        return False


def seed_user_config() -> Path:
    """把包内模板复制进 `~/.quant-ai/configs`，已存在的文件不覆盖。"""
    target = user_config_dir()
    target.mkdir(parents=True, exist_ok=True)
    if not TEMPLATE_DIR.is_dir():
        return target
    for item in sorted(TEMPLATE_DIR.iterdir()):
        if item.name in _SEED_SKIP or item.name in PRIVATE_NAMES or not item.is_file():
            continue
        destination = target / item.name
        if not destination.exists():
            shutil.copyfile(item, destination)
    return target


def resolve_config(explicit: str | Path | None = None, *, names: tuple[str, ...] = _DEFAULT_NAMES) -> Path:
    """定位要用的配置文件。

    顺序：显式 `--config` > `./configs/{my,default}.yaml` > `~/.quant-ai/configs/...`。
    三处都没有（即刚 pip 装完第一次跑）才播种模板，所以在源码树里工作永远不会
    凭空生出 `~/.quant-ai`。
    """
    if explicit is not None:
        return _resolve_explicit(explicit)
    source = source_config_dir()
    for name in names:
        candidate = source / name
        if candidate.is_file():
            return candidate
    user = user_config_dir()
    for name in names:
        candidate = user / name
        if candidate.is_file():
            return candidate
    seed_user_config()
    for name in names:
        candidate = user / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"No config found. Looked for {' / '.join(names)} in {source} and {user}. "
        f"Pass --config <path>, or run `quant-ai init` to create one."
    )


def config_write_dir() -> Path:
    """`quant-ai init` 这类命令生成文件的去处：源码树里写 `./configs`，否则写用户目录。"""
    source = source_config_dir()
    if source.is_dir():
        return source
    return seed_user_config()


def resolve_data_file(relative: str | Path, *, seed: bool = True) -> Path:
    """定位 `configs/catalog.csv` 这类随附数据文件，顺序与 `resolve_config` 一致。

    返回第一个存在的候选；全都不存在时返回用户目录下的那个，让报错信息指向
    用户真正能去放文件的地方。
    """
    relative = Path(relative)
    if relative.is_absolute():
        return relative
    name = relative.name
    direct = Path.cwd() / relative
    if direct.is_file():
        return direct
    if seed and name not in PRIVATE_NAMES:
        seed_user_config()
    user = user_config_dir() / name
    if user.is_file():
        return user
    template = TEMPLATE_DIR / name
    if template.is_file():
        return template
    return user


def _resolve_explicit(explicit: str | Path) -> Path:
    """显式给定的路径：绝对路径照用；相对路径按工作目录 → 用户目录依次试。"""
    path = Path(explicit)
    if path.is_absolute():
        return path
    direct = Path.cwd() / path
    if direct.is_file():
        return direct
    in_home = home() / path
    if in_home.is_file():
        return in_home
    # 都不存在：返回工作目录下那个，报错信息才符合用户的预期。
    return direct
