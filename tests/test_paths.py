"""配置解析链：源码树跑和 pip 装完跑，落点必须各自正确。

源码树里 TEMPLATE_DIR（quant_agent/templates）并不存在 —— 它是 setuptools 打包时
才从 configs/ 映射出来的。所以要验证安装后的行为，这里把 TEMPLATE_DIR 指到一个
临时目录来模拟已安装的布局。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from quant_agent import paths
from quant_agent.config import load_config


def _fake_install(monkeypatch, tmp_path: Path, extra: dict[str, str] | None = None) -> Path:
    """造一个假的包内模板目录，并把用户目录指向 tmp_path，模拟 pip 装完的状态。"""
    template_dir = tmp_path / "site-packages/quant_agent/templates"
    template_dir.mkdir(parents=True)
    (template_dir / "__init__.py").write_text("", encoding="utf-8")
    (template_dir / "default.yaml").write_text(
        yaml.safe_dump({"data": {"source": "csv", "universe": ["AAPL"]}}), encoding="utf-8"
    )
    for name, body in (extra or {}).items():
        (template_dir / name).write_text(body, encoding="utf-8")
    monkeypatch.setattr(paths, "TEMPLATE_DIR", template_dir)
    monkeypatch.setenv("QUANT_AI_HOME", str(tmp_path / "home"))
    return template_dir


def test_source_tree_config_wins_and_leaves_user_dir_alone(tmp_path, monkeypatch):
    """仓库里有 ./configs/my.yaml 时必须用它，且不能凭空生出 ~/.quant-ai。"""
    _fake_install(monkeypatch, tmp_path)
    workdir = tmp_path / "checkout"
    (workdir / "configs").mkdir(parents=True)
    (workdir / "configs/my.yaml").write_text("language: zh\n", encoding="utf-8")
    monkeypatch.chdir(workdir)

    assert paths.resolve_config() == workdir / "configs/my.yaml"
    assert not paths.home().exists(), "源码树里工作不该创建用户目录"


def test_installed_run_seeds_user_dir(tmp_path, monkeypatch):
    """装完第一次跑：工作目录没有 configs/，就从模板播种到用户目录。"""
    _fake_install(monkeypatch, tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    resolved = paths.resolve_config()
    assert resolved == paths.home() / "configs/default.yaml"
    assert resolved.is_file()


def test_seeding_never_copies_private_files(tmp_path, monkeypatch):
    """个人自选股/偏好绝不能被播种，也不该出现在安装包里（见 pyproject 的 exclude-package-data）。"""
    _fake_install(
        monkeypatch,
        tmp_path,
        extra={"my.yaml": "language: zh\n", "my_universe.csv": "symbol\nNVDA\n", "profile.json": "{}"},
    )
    seeded = paths.seed_user_config()

    names = {p.name for p in seeded.iterdir()}
    assert "default.yaml" in names
    assert names.isdisjoint(paths.PRIVATE_NAMES), f"私有文件被播种了：{names & paths.PRIVATE_NAMES}"
    assert "__init__.py" not in names, "打包用的 __init__.py 不该出现在用户配置目录里"


def test_user_dir_config_keeps_data_in_user_dir(tmp_path, monkeypatch):
    """用户目录下那层叫 configs，于是数据根是 ~/.quant-ai —— 不是当前工作目录。"""
    _fake_install(monkeypatch, tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    config = load_config(paths.resolve_config())

    assert config.data.cache_dir == paths.home() / "data/cache"
    assert config.portfolio_path == paths.home() / "data/portfolio.json"
    assert elsewhere not in config.report.output_dir.parents, "报告不该写进调用方的工作目录"


def test_template_config_never_becomes_a_data_root(tmp_path, monkeypatch):
    """直接加载包内模板时，数据必须改落用户目录，否则会往 site-packages 里写东西。"""
    template_dir = _fake_install(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path)

    config = load_config(template_dir / "default.yaml")

    assert config.data.cache_dir == paths.home() / "data/cache"
    assert template_dir not in config.data.cache_dir.parents
