"""
为 AcaciaMC 添加本地化支持 (Localization Support)

  "代码可读性的一小步, 消除屎山的一大步" - 鲁迅 (其实是creepebucket说的)
"""

__all__ = ["DEFAULT_LANG", "get_lang", "localize", "LocalizedEnum"]

from typing import Dict
from enum import Enum
import json

lang_cache: Dict[str, Dict[str, str]] = {}

def load_default_lang():
    """加载默认语言"""
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
        return config["lang"]

DEFAULT_LANG = load_default_lang()

def get_lang(lang: str = DEFAULT_LANG) -> Dict[str, str]:
    """获取指定语言的本地化映射表"""
    if lang in lang_cache:
        return lang_cache[lang]
    lang_cache[lang] = lang_file_dict = {}  # 语言映射列表
    with open(f"acaciamc/lang/{lang}.lang", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#"):  # 注释行
                continue
            if not line:  # 空行
                continue
            key, text = line.split(" = ", maxsplit=1)  # 按等号分割语言映射
            lang_file_dict[key] = text
        return lang_file_dict

def localize(key: str, lang: str = DEFAULT_LANG) -> str:
    """
    Get localized text.
    获取指定语言的本地化文本
    """
    return get_lang(lang)[key]

class LocalizedEnum(Enum):
    """
    An Enum whose values are localization keys.
    An attribute `localized` is added to each enum member which is the
    localized value using default language.
    """

    def __init__(self, key: str):
        self._localized = localize(key)

    @property
    def localized(self) -> str:
        return self._localized
