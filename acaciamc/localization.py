"""
为acaciaMC添加本地化支持

  "代码可读性的一小步, 消除屎山的一大步" - 鲁迅 (其实是creepebucket说的)
"""

import json
def get_lang(lang = None):
    """
    获取指定语言的本地化文件
    """

    if lang == None:  # 未指定语言, 尝试从配置文件中获取
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
            lang = config["global"]["lang"]

    try:  # 尝试读取语言文件
        with open(f"acaciamc/lang/{lang}.lang", "r", encoding="utf-8") as f:
            lang_file_dict = {}  # 语言映射列表

            for line in f.read().split("\n"):  # 读取每行
                line = line.strip()

                if line.startswith("#"):  # 注释行
                    continue

                if line == "":  # 空行
                    continue

                split_line = line.split(" = ")  # 按等号分割语言映射
                lang_file_dict[split_line[0]] =  split_line[1] # 按等号分割语言映射

            return lang_file_dict

    except FileNotFoundError:
        raise ValueError(f"语言文件 {lang} 不存在")  # 语言文件不存在

def get_text(key, lang):
    """
    获取指定语言的本地化文本
    """
    try:
        return lang[key]
    except KeyError:
        return get_lang('en_US')[key]  # 找不到对应语言的键值, 尝试获取英文语言的键值


"""


import acaciamc.localization
from acaciamc.localization import get_text

lang = acaciamc.localization.get_lang()

def localize(text):
    return get_text(text, lang)



"""