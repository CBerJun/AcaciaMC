"""Builtin string."""

__all__ = ['StringType', 'String']

from .base import *
from .types import Type, DataType

class StringType(Type):
    name = 'str'

class String(AcaciaExpr):
    def __init__(self, value: str, compiler):
        super().__init__(
            DataType.from_type_cls(StringType, compiler), compiler
        )
        self.value = value

    def cmdstr(self) -> str:
        return self.value

    def __add__(self, other):
        """Adding strings will connect them."""
        if isinstance(other, String):
            return String(self.value + other.value, self.compiler)
        return NotImplemented
