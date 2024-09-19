"""
ANSI escape sequence color and style codes.
See https://en.wikipedia.org/wiki/ANSI_escape_code
"""

from typing import Union, Iterable, TextIO, Tuple
from enum import Enum
from contextlib import contextmanager

class AnsiColor(Enum):
    """ANSI color codes."""

    BLACK = 30
    RED = 31
    GREEN = 32
    YELLOW = 33
    BLUE = 34
    MAGENTA = 35
    CYAN = 36
    WHITE = 37
    DEFAULT = 39

    def begin(self) -> int:
        return self.value

    def end(self) -> int:
        return AnsiColor.DEFAULT.begin()

class AnsiStyle(Enum):
    """ANSI style codes, including opening and resetting sequences."""

    BOLD = 1, 22
    DIM = 2, 22
    ITALIC = 3, 23
    UNDERLINE = 4, 24
    BLINKING = 5, 25
    INVERSE = 7, 27
    HIDDEN = 8, 28
    STRIKETHROUGH = 9, 29

    def begin(self) -> int:
        """Get opening code."""
        return self.value[0]

    def end(self) -> int:
        """Get resetting code."""
        return self.value[1]

def ansi_codes_to_str(codes: Iterable[int]) -> str:
    """Convert one or more integer codes into an ANSI sequence."""
    return '\x1b[%sm' % ';'.join(map(str, codes))

def ansi_styles_to_str(*insns: Union[AnsiColor, AnsiStyle]) -> Tuple[str, str]:
    """
    Convert one or more styles into two ANSI sequences, used for
    applying and clearing the given style(s), correspondingly.
    """
    return (ansi_codes_to_str(insn.begin() for insn in insns),
            ansi_codes_to_str(insn.end() for insn in insns))

@contextmanager
def ansi(file: TextIO, *insns: Union[AnsiColor, AnsiStyle]):
    """
    Apply ANSI styles in `insns` temporarily to output of `file`.
    Used as a context manager.
    """
    begin, end = ansi_styles_to_str(*insns)
    file.write(begin)
    try:
        yield
    finally:
        file.write(end)
