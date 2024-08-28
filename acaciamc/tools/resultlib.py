"""Tools about return value of binary functions."""

__all__ = ["Result", "commands", "literal", "nothing"]

from typing import NamedTuple, Union, TYPE_CHECKING

# `import acaciamc.objects as objects` won't work in 3.6
# because of a Python bug (see https://bugs.python.org/issue23203)
from acaciamc import objects
from acaciamc.mccmdgen.utils import unreachable

if TYPE_CHECKING:
    from acaciamc.mccmdgen.expr import AcaciaExpr, CMDLIST_T


class Result(NamedTuple):
    """Return value of a binary function implementation."""
    value: "AcaciaExpr"
    commands: "CMDLIST_T"


def commands(cmds: "CMDLIST_T") -> Result:
    return Result(objects.NoneLiteral(), cmds)


def literal(value: Union[bool, int, str, float, None]) -> "AcaciaExpr":
    if isinstance(value, bool):  # `bool` in front of `int`
        return objects.BoolLiteral(value)
    elif isinstance(value, int):
        return objects.IntLiteral(value)
    elif isinstance(value, str):
        return objects.String(value)
    elif isinstance(value, float):
        return objects.Float(value)
    elif value is None:
        return objects.NoneLiteral()
    unreachable(f"unexpected value {value!r}")
