"""Builtin None value."""

__all__ = ['NoneDataType', 'NoneLiteral']

from acaciamc.mccmdgen.expr import *
from acaciamc.mccmdgen.datatype import DefaultDataType, Storable
from acaciamc.mccmdgen.ctexpr import CTDataType

class NoneDataType(DefaultDataType, Storable):
    name = 'None'

    def new_var(self) -> "NoneLiteral":
        return NoneLiteral(self.compiler)

ctdt_none = CTDataType("None")

class NoneLiteral(ConstExprCombined, VarValue):
    """Represents a literal None."""
    cdata_type = ctdt_none

    def __init__(self, compiler):
        super().__init__(NoneDataType(compiler), compiler)
        self.is_temporary = True  # Assignment to None is always disallowed

    def export(self, var: "NoneLiteral"):
        return []

    def swap(self, other: "NoneLiteral"):
        return []

    def datatype_hook(self):
        """None as a type specifier represents the None type."""
        return NoneDataType(self.compiler)

    def cdatatype_hook(self) -> CTDataType:
        return ctdt_none
