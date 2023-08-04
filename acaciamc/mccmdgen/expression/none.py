"""Builtin None value."""

__all__ = ['NoneDataType', 'NoneVar', 'NoneLiteral']

from .base import *
from acaciamc.mccmdgen.datatype import DefaultDataType

class NoneDataType(DefaultDataType):
    name = 'nonetype'

    def __init__(self, compiler):
        super().__init__()
        self.compiler = compiler

    def new_var(self, tmp=False) -> "NoneVar":
        return NoneVar(self.compiler)

class NoneVar(VarValue):
    """Used when function's result is nothing."""
    def __init__(self, compiler):
        super().__init__(NoneDataType(compiler), compiler)

    def export(self, var: "NoneVar"):
        return []

class NoneLiteral(AcaciaExpr):
    """Represents a literal None. Used by "None" keyword."""
    def __init__(self, compiler):
        super().__init__(NoneDataType(compiler), compiler)

    def export(self, var: "NoneVar"):
        return []
