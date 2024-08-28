"""Builtin float point values."""

__all__ = ["FloatDataType", "Float", "FloatType"]

from functools import partialmethod

from acaciamc.error import Error, ErrorType
from acaciamc.mccmdgen.ctexpr import CTDataType
from acaciamc.mccmdgen.datatype import DefaultDataType
from acaciamc.mccmdgen.expr import *
from acaciamc.mccmdgen.utils import InvalidOpError
from acaciamc.tools import axe, cmethod_of
from .integer import IntLiteral
from .types import Type


class FloatDataType(DefaultDataType):
    name = "float"


ctdt_float = CTDataType("float")


class FloatType(Type):
    def do_init(self):
        @cmethod_of(self, "__new__")
        @axe.chop
        @axe.arg("i", axe.LiteralInt())
        @axe.slash
        def _new(compiler, i: int):
            return Float(float(i))

    def datatype_hook(self):
        return FloatDataType()

    def cdatatype_hook(self):
        return ctdt_float


class Float(ConstExprCombined):
    cdata_type = ctdt_float

    def __init__(self, value: float):
        super().__init__(FloatDataType())
        self.value = value

    def cstringify(self) -> str:
        return str(self)

    def chash(self):
        return self.value

    @classmethod
    def from_int(cls, integer: IntLiteral):
        return Float(float(integer.value))

    def __str__(self) -> str:
        return str(self.value)

    def cunarypos(self):
        return self

    def cunaryneg(self):
        return Float(-self.value)

    def _bin_op(self, other, method: str):
        """`method`: "__add__", "__sub__", etc."""
        if isinstance(other, (Float, IntLiteral)):
            try:
                v = getattr(self.value, method)(other.value)
            except ArithmeticError as err:
                raise Error(ErrorType.CONST_ARITHMETIC, message=str(err))
            return Float(v)
        raise InvalidOpError

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
