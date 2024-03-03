"""Builtin float point values."""

__all__ = ["FloatDataType", "Float"]

from functools import partialmethod

from acaciamc.mccmdgen.datatype import DefaultDataType
from acaciamc.error import Error, ErrorType
from .base import *
from .integer import IntLiteral

class FloatDataType(DefaultDataType):
    name = "float"

class Float(ConstExpr):
    def __init__(self, value: float, compiler):
        super().__init__(FloatDataType(compiler), compiler)
        self.value = value

    def cmdstr(self) -> str:
        return str(self)

    def map_hash(self):
        return self.value

    @classmethod
    def from_int(cls, integer: IntLiteral):
        return Float(float(integer.value), integer.compiler)

    def __str__(self) -> str:
        return str(self.value)

    def __pos__(self):
        return self

    def __neg__(self):
        return Float(-self.value, self.compiler)

    def _bin_op(self, other, method: str):
        """`method`: "__add__", "__sub__", etc."""
        if isinstance(other, (Float, IntLiteral)):
            try:
                v = getattr(self.value, method)(other.value)
            except ArithmeticError as err:
                raise Error(ErrorType.CONST_ARITHMETIC, message=str(err))
            return Float(v, self.compiler)
        return NotImplemented

    __add__ = partialmethod(_bin_op, method="__add__")
    __sub__ = partialmethod(_bin_op, method="__sub__")
    __mul__ = partialmethod(_bin_op, method="__mul__")
    __floordiv__ = partialmethod(_bin_op, method="__truediv__")
    __mod__ = partialmethod(_bin_op, method="__mod__")
    __radd__ = partialmethod(_bin_op, method="__radd__")
    __rsub__ = partialmethod(_bin_op, method="__rsub__")
    __rmul__ = partialmethod(_bin_op, method="__rmul__")
    __rfloordiv__ = partialmethod(_bin_op, method="__rtruediv__")
    __rmod__ = partialmethod(_bin_op, method="__rmod__")

    def _ciop(self, other, method: str):
        if isinstance(other, (Float, IntLiteral)):
            try:
                v = getattr(self.value, method)(other.value)
            except ArithmeticError as err:
                raise Error(ErrorType.CONST_ARITHMETIC, message=str(err))
            return Float(v, self.compiler)
        else:
            raise TypeError

    ciadd = partialmethod(_ciop, method="__add__")
    cisub = partialmethod(_ciop, method="__sub__")
    cimul = partialmethod(_ciop, method="__mul__")
    cidiv = partialmethod(_ciop, method="__truediv__")
    cimod = partialmethod(_ciop, method="__mod__")
