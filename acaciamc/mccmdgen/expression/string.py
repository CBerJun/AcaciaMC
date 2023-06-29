"""Builtin string."""

__all__ = ['String']

from .base import *
from .types import StringType, DataType

class String(AcaciaExpr):
    def __init__(self, value: str, compiler):
        super().__init__(
            DataType.from_type_cls(StringType, compiler), compiler
        )
        self.value = value

    def __add__(self, other: "String"):
        """Adding strings will connect them."""
        return String(self.value + other.value, self.compiler)
