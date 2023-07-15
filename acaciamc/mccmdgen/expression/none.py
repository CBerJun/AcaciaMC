"""Builtin None value."""

__all__ = ['NoneType', 'NoneVar', 'NoneLiteral']

from .base import *
from .types import Type, DataType

class NoneType(Type):
    name = 'nonetype'

    def new_var(self, tmp=False) -> "NoneVar":
        return NoneVar(self.compiler)

class NoneVar(VarValue):
    """Used when function's result is nothing."""
    def __init__(self, compiler):
        super().__init__(DataType.from_type_cls(NoneType, compiler), compiler)

    def export(self, var: "NoneVar"):
        return []

class NoneLiteral(AcaciaExpr):
    """Represents a literal None. Used by "None" keyword."""
    def __init__(self, compiler):
        super().__init__(DataType.from_type_cls(NoneType, compiler), compiler)

    def export(self, var: "NoneVar"):
        return []
