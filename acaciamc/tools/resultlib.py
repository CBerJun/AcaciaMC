"""Tools about return value of binary functions."""

__all__ = ["Result", "commands", "literal", "nothing"]

from typing import List, NamedTuple, Union, TYPE_CHECKING

import acaciamc.mccmdgen.expression as acacia

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler

class Result(NamedTuple):
    """Return value of a binary function implementation."""
    value: acacia.AcaciaExpr
    commands: acacia.CMDLIST_T

def commands(cmds: acacia.CMDLIST_T, compiler: "Compiler") -> Result:
    return Result(acacia.NoneVar(compiler), cmds)

def literal(value: Union[bool, int, str, float, None],
            compiler: "Compiler") -> acacia.AcaciaExpr:
    if isinstance(value, bool):  # `bool` in front of `int`
        return acacia.BoolLiteral(value, compiler)
    elif isinstance(value, int):
        return acacia.IntLiteral(value, compiler)
    elif isinstance(value, str):
        return acacia.String(value, compiler)
    elif isinstance(value, float):
        return acacia.Float(value, compiler)
    elif value is None:
        return acacia.NoneVar(compiler)
    raise TypeError("unexpected value %r" % value)
