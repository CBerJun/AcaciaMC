"""
Localization Support (本地化支持)

To make sure that `set_language` works well, strings returned by
`localize` should not be stored. Instead, get a new localized string
every time. Calling `localize` on module level should be avoided, too.

"代码可读性的一小步, 消除屎山的一大步" - 鲁迅 (其实是creepebucket说的)
"""

__all__ = [
    "DEFAULT_LANGUAGE", "current_language", "set_language",
    "get_mapping", "localize", "LocalizedEnum"
]

from enum import Enum
from pkgutil import get_data
from typing import Dict

lang_cache: Dict[str, Dict[str, str]] = {}
DEFAULT_LANGUAGE = _language = 'en_US'


def current_language() -> str:
    """Get current language code."""
    return _language


def set_language(lang: str) -> None:
    """Change the language."""
    global _language
    _language = lang


def get_mapping(lang: str) -> Dict[str, str]:
    """
    Get the mapping that maps from localization key to the text of the
    specified language.
    获取指定语言的本地化映射表
    """
    if lang in lang_cache:
        return lang_cache[lang]
    lang_cache[lang] = lang_file_dict = {}  # 语言映射列表
    raw = get_data(__name__, f"lang/{lang}.lang")
    for line in raw.decode("utf-8").splitlines():
        line = line.strip()
        if line.startswith("#"):  # 注释行
            continue
        if not line:  # 空行
            continue
        key, text = line.split(" = ", maxsplit=1)  # 按等号分割语言映射
        lang_file_dict[key] = text
    return lang_file_dict


def localize(key: str) -> str:
    """Get localized text under current language."""
    mapping = get_mapping(_language)
    if key in mapping:
        return mapping[key]
    return get_mapping(DEFAULT_LANGUAGE)[key]


class LocalizedEnum(Enum):
    """
    An Enum whose values are localization keys.
    An attribute `localized` is added to each enum member which is the
    localized value using default language.
    """

    @property
    def localized(self) -> str:
        return localize(self.value)
