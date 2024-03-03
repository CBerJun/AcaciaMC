"""Builtin string."""

__all__ = ['StringDataType', 'String']

from .base import *
from acaciamc.mccmdgen.datatype import DefaultDataType

class StringDataType(DefaultDataType):
    name = 'str'

class String(ConstExpr):
    def __init__(self, value: str, compiler):
        super().__init__(StringDataType(compiler), compiler)
        self.value = value

    def map_hash(self):
        return self.value

    def cmdstr(self) -> str:
        return self.value

    def __add__(self, other):
        """Adding strings will connect them."""
        if isinstance(other, String):
            return String(self.value + other.value, self.compiler)
        return NotImplemented

    def ciadd(self, other: ConstExpr):
        if isinstance(other, String):
            return String(self.value + other.value, self.compiler)
        raise TypeError
