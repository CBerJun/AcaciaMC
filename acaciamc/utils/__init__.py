"""
Miscellaneous utilities.

These are code that could be standalone with very few or no
modifications.

Ideally write a new submodule and everything related to that topic goes
there. If the utility really does not have a topic, put it here at
package level.
"""

def is_int32(x: int) -> bool:
    """
    Return if the given integer is in the range of 32-bit signed
    integers.
    """
    return -2147483648 <= x <= 2147483647
