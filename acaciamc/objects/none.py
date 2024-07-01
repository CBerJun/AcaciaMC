"""Builtin None value."""

__all__ = ['NoneDataType', 'NoneLiteral']

from acaciamc.mccmdgen.ctexpr import CTDataType
from acaciamc.mccmdgen.datatype import (
    DefaultDataType, Storable, SupportsEntityField
)
from acaciamc.mccmdgen.expr import *


class NoneDataType(DefaultDataType, Storable, SupportsEntityField):
    name = 'None'

    def new_var(self, compiler) -> "NoneLiteral":
        return NoneLiteral()

    def new_entity_field(self, compiler) -> dict:
        return {}

    def new_var_as_field(self, entity) -> VarValue:
        return NoneLiteral()


ctdt_none = CTDataType("None")


class NoneLiteral(ConstExprCombined, VarValue):
    """Represents a literal None."""
    cdata_type = ctdt_none

    def __init__(self):
        super().__init__(NoneDataType())

    def export(self, var: "NoneLiteral", compiler):
        return []

    def swap(self, other: "NoneLiteral", compiler):
        return []

    def datatype_hook(self):
        """None as a type specifier represents the None type."""
        return NoneDataType()

    def cdatatype_hook(self) -> CTDataType:
        return ctdt_none

    def stringify(self) -> str:
        return 'None'
