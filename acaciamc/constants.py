"""Constants for Acacia."""

INT_MIN = -2 ** 31
INT_MAX = 2 ** 31 - 1
DEFAULT_ANCHOR = "feet"
XYZ = ("x", "y", "z")

class Config:
    debug_comments = False  # generate debug comments in .mcfunction files
    function_folder = 'acacia'  # name of the folder of functions
    scoreboard = 'acacia'  # prefix of scoreboard that Acacia uses to hold data
    entity_name = 'acacia'  # prefix of entity names
    entity_type = 'armor_stand'  # default type of entity
    entity_pos = '~ ~ ~'  # which place to summon entity
    entity_tag = 'acacia'  # prefix of entity tags
    mc_version = (1, 20, 20)  # Mineraft version
