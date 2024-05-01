"""Builtin None value."""

__all__ = ['NoneDataType', 'NoneLiteral']

from acaciamc.mccmdgen.expr import *
from acaciamc.mccmdgen.datatype import DefaultDataType, Storable
from acaciamc.mccmdgen.ctexpr import CTDataType

class NoneDataType(DefaultDataType, Storable):
    name = 'None'

    def new_var(self, compiler) -> "NoneLiteral":
        return NoneLiteral()

ctdt_none = CTDataType("None")

class NoneLiteral(ConstExprCombined, VarValue):
    """Represents a literal None."""
    cdata_type = ctdt_none

    def __init__(self):
        super().__init__(NoneDataType())
        self.is_temporary = True  # Assignment to None is always disallowed

    def export(self, var: "NoneLiteral", compiler):
        return []

    def swap(self, other: "NoneLiteral", compiler):
        return []

    def datatype_hook(self):
        """None as a type specifier represents the None type."""
        return NoneDataType()

    def cdatatype_hook(self) -> CTDataType:
        return ctdt_none
