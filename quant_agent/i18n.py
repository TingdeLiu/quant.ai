"""极简双语支持：英文为默认语言，中文可选。

设计刻意保持简单——只提供 `tr(en, zh, lang)` 选择器和语言归一化，不引入
gettext / 资源文件等重型机制。各模块把英文/中文写在一起，就近维护。
"""

from __future__ import annotations

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = ("en", "zh")

_ZH_ALIASES = {"zh", "cn", "zh-cn", "zh_cn", "chinese", "中文", "中"}
_EN_ALIASES = {"en", "en-us", "english", "英文", "英语"}


def normalize_language(value: str | None) -> str:
    """把各种写法归一到 'en' / 'zh'，无法识别时回退到默认（英文）。"""
    v = (value or "").strip().lower()
    if v in _ZH_ALIASES:
        return "zh"
    if v in _EN_ALIASES:
        return "en"
    return DEFAULT_LANGUAGE


def tr(en: str, zh: str, lang: str = DEFAULT_LANGUAGE) -> str:
    """选择语言：默认英文，lang 归一为中文时返回中文。"""
    return zh if normalize_language(lang) == "zh" else en
