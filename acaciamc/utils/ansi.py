"""
ANSI escape sequence color and style codes.
See https://en.wikipedia.org/wiki/ANSI_escape_code
"""

from typing import Union, Iterable, TextIO
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

def ansi_write(file: TextIO, codes: Iterable[int]):
    """Write given ANSI code to `file`."""
    file.write('\x1b[%sm' % ';'.join(map(str, codes)))

@contextmanager
def ansi(file: TextIO, *insns: Union[AnsiColor, AnsiStyle]):
    """
    Apply ANSI styles in `insns` temporarily to output of `file`.
    Used as a context manager.
    """
    ansi_write(file, (insn.begin() for insn in insns))
    try:
        yield
    finally:
        ansi_write(file, (insn.end() for insn in insns))
