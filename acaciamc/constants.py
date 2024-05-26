"""Constants for Acacia."""

__all__ = [
    "INT_MIN", "INT_MAX", "DEFAULT_ANCHOR", "XYZ",
    "TERMINATOR_CHARS", "FUNCTION_PATH_CHARS",
    "COLORS", "COLORS_NEW"
]

from string import ascii_letters, digits

INT_MIN = -2 ** 31
INT_MAX = 2 ** 31 - 1
DEFAULT_ANCHOR = "feet"
XYZ = ("x", "y", "z")

# These characters are not allowed in strings in commands, unless they
# are quoted.
TERMINATOR_CHARS = frozenset(" ,@~^/$&\"'!#%+*=[{]}\\|<>`\n")
# These are the only characters allowed in function paths.
FUNCTION_PATH_CHARS = frozenset(ascii_letters + digits + ".(-)_/")

COLORS = {
    "black": "0",
    "dark_blue": "1",
    "dark_green": "2",
    "dark_aqua": "3",
    "dark_red": "4",
    "dark_purple": "5",
    "gold": "6",
    "gray": "7",
    "dark_gray": "8",
    "blue": "9",
    "green": "a",
    "aqua": "b",
    "red": "c",
    "light_purple": "d",
    "yellow": "e",
    "white": "f",
    "minecoin_gold": "g",
}
# 1.19.80+ colors
COLORS_NEW = {
    "material_quartz": "h",
    "material_iron": "i",
    "material_netherite": "j",
    "material_redstone": "m",
    "material_copper": "n",
    "material_gold": "p",
    "material_emerald": "q",
    "material_diamond": "s",
    "material_lapis": "t",
    "material_amethyst": "u",
}
