"""Builtin float point values."""

__all__ = ["FloatDataType", "Float"]

from functools import partialmethod

from acaciamc.mccmdgen.datatype import DefaultDataType
from acaciamc.error import Error, ErrorType
from acaciamc.mccmdgen.ctexpr import CTDataType
from acaciamc.mccmdgen.expr import *
from .integer import IntLiteral

class FloatDataType(DefaultDataType):
    name = "float"

ctdt_float = CTDataType("float")

class Float(ConstExprCombined):
    cdata_type = ctdt_float

    def __init__(self, value: float, compiler):
        super().__init__(FloatDataType(compiler), compiler)
        self.value = value

    def cstringify(self) -> str:
        return str(self)

    def chash(self):
        return self.value

    @classmethod
    def from_int(cls, integer: IntLiteral):
        return Float(float(integer.value), integer.compiler)

    def __str__(self) -> str:
        return str(self.value)

    def cunarypos(self):
        return self

    def cunaryneg(self):
        return Float(-self.value, self.compiler)

    def _bin_op(self, other, method: str):
        """`method`: "__add__", "__sub__", etc."""
        if isinstance(other, (Float, IntLiteral)):
            try:
                v = getattr(self.value, method)(other.value)
            except ArithmeticError as err:
                raise Error(ErrorType.CONST_ARITHMETIC, message=str(err))
            return Float(v, self.compiler)
        raise TypeError

    cadd = partialmethod(_bin_op, method="__add__")
    csub = partialmethod(_bin_op, method="__sub__")
    cmul = partialmethod(_bin_op, method="__mul__")
    cdiv = partialmethod(_bin_op, method="__truediv__")
    cmod = partialmethod(_bin_op, method="__mod__")
    cradd = partialmethod(_bin_op, method="__radd__")
    crsub = partialmethod(_bin_op, method="__rsub__")
    crmul = partialmethod(_bin_op, method="__rmul__")
    crdiv = partialmethod(_bin_op, method="__rtruediv__")
    crmod = partialmethod(_bin_op, method="__rmod__")
