"""Verify built distributions before they go to PyPI.

A PyPI version number can never be reused, so a bad upload burns that version
for good. These two checks are the ones that would hurt most:

1. the default config must ship, or `pip install quant-ai` lands unusable;
2. no personal file (watchlist, holdings, preferences) may be inside.

Run locally before tagging, or let the release workflow call it:

    python scripts/check_dist.py dist/*
"""

from __future__ import annotations

import sys
import tarfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quant_agent.paths import PRIVATE_NAMES  # noqa: E402  仓库根加入 sys.path 之后才能导入

# 装完之后必须能找到的默认配置。wheel 里它已经是包内的 quant_agent/templates，
# sdist 里还是仓库布局下的 configs —— 两种布局都要盯。
REQUIRED_MEMBER = {"wheel": "quant_agent/templates/default.yaml", "sdist": "configs/default.yaml"}


def _kind(archive: Path) -> str:
    if archive.name.endswith(".whl"):
        return "wheel"
    if archive.name.endswith(".tar.gz"):
        return "sdist"
    raise ValueError(f"not a distribution: {archive}")


def _members(archive: Path) -> list[str]:
    if _kind(archive) == "wheel":
        with zipfile.ZipFile(archive) as zf:
            return zf.namelist()
    with tarfile.open(archive) as tf:
        return tf.getnames()


def check(archive: Path) -> list[str]:
    """返回这份产物的问题列表；空列表表示通过。"""
    problems: list[str] = []
    names = _members(archive)

    required = REQUIRED_MEMBER[_kind(archive)]
    if not any(name.endswith(required) for name in names):
        problems.append(f"missing {required} - an install would have no default config")

    for name in names:
        if Path(name).name in PRIVATE_NAMES:
            problems.append(f"personal file bundled: {name}")

    return problems


def main(argv: list[str]) -> int:
    archives = [Path(a) for a in argv] or sorted(Path("dist").glob("*"))
    archives = [a for a in archives if a.name.endswith((".whl", ".tar.gz"))]
    if not archives:
        print("No distributions found. Run `python -m build` first.", file=sys.stderr)
        return 1

    failed = False
    for archive in archives:
        problems = check(archive)
        if problems:
            failed = True
            print(f"FAIL {archive.name}")
            for problem in problems:
                print(f"       {problem}")
        else:
            print(f"ok   {archive.name}")

    if failed:
        print("\nRefusing to publish. Fix pyproject packaging and rebuild.", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
