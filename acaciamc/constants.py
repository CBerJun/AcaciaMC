"""Constants for Acacia."""

INT_MIN = -2 ** 31
INT_MAX = 2 ** 31 - 1
DEFAULT_ANCHOR = "feet"
XYZ = ("x", "y", "z")

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

class Config:
    debug_comments = False  # generate debug comments in .mcfunction files
    function_folder = 'acacia'  # name of the folder of functions
    scoreboard = 'acacia'  # prefix of scoreboard that Acacia uses to hold data
    entity_name = 'acacia'  # prefix of entity names
    entity_type = 'armor_stand'  # default type of entity
    entity_pos = '~ ~ ~'  # which place to summon entity
    entity_tag = 'acacia'  # prefix of entity tags
    mc_version = (1, 20, 20)  # Mineraft version
    optimizer = True  # enable optimizer
    # Max size for a function that is called with /execute
    # condtions to be inlined:
    max_inline_file_size = 20
