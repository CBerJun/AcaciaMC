"""Builtin None value."""

__all__ = ['NoneDataType', 'NoneVar', 'NoneLiteral']

from .base import *
from acaciamc.mccmdgen.datatype import DefaultDataType, Storable

class NoneDataType(DefaultDataType, Storable):
    name = 'nonetype'

    def new_var(self) -> "NoneVar":
        return NoneVar(self.compiler)

class NoneVar(VarValue):
    """Used when function's result is nothing."""
    def __init__(self, compiler):
        super().__init__(NoneDataType(compiler), compiler)

    def swap(self, other: "NoneVar"):
        return []

    def export(self, var: "NoneVar"):
        return []

class NoneLiteral(ConstExpr):
    """Represents a literal None. Used by "None" keyword."""
    def __init__(self, compiler):
        super().__init__(NoneDataType(compiler), compiler)

    def export(self, var: "NoneVar"):
        return []

    def datatype_hook(self):
        """None as a type specifier represents nonetype."""
        return NoneDataType(self.compiler)
