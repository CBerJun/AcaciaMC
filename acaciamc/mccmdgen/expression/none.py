"""Builtin None value."""

__all__ = ['NoneVar', 'NoneLiteral', 'result_cmds']

from .base import *
from .types import NoneType, DataType

class NoneVar(VarValue):
    """Used when function's result is nothing."""
    def __init__(self, compiler):
        super().__init__(DataType.from_type_cls(NoneType, compiler), compiler)

    def export(self, var: "NoneVar"):
        return []

def result_cmds(dependencies: list, compiler):
    # API for `BinaryFunction`s, used to return None and just run
    # some commands.
    return NoneVar(compiler), dependencies

class NoneLiteral(AcaciaExpr):
    """Represents a literal None. Used by "None" keyword."""
    def __init__(self, compiler):
        super().__init__(DataType.from_type_cls(NoneType, compiler), compiler)

    def export(self, var: "NoneVar"):
        return []
