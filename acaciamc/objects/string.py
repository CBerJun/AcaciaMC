"""Builtin string."""

__all__ = ['StringDataType', 'String']

from acaciamc.mccmdgen.ctexpr import CTDataType
from acaciamc.mccmdgen.datatype import DefaultDataType
from acaciamc.mccmdgen.expr import *
from acaciamc.mccmdgen.utils import InvalidOpError


class StringDataType(DefaultDataType):
    name = 'str'


ctdt_string = CTDataType("str")


class String(ConstExprCombined):
    cdata_type = ctdt_string

    def __init__(self, value: str):
        super().__init__(StringDataType())
        self.value = value

    def chash(self):
        return self.value

    def cstringify(self) -> str:
        return self.value

    def cadd(self, other):
        """Adding strings will connect them."""
        if isinstance(other, String):
            return String(self.value + other.value)
        raise InvalidOpError
