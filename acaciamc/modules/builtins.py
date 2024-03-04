from typing import TYPE_CHECKING

from acaciamc.mccmdgen.expression import *
from acaciamc.mccmdgen.datatype import DataType
from acaciamc.tools import axe, resultlib

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler

class AnyDataType(DataType):
    def __str__(self) -> str:
        return 'Any'

    @classmethod
    def name_no_generic(cls) -> str:
        return 'Any'

    def matches(self, other: "DataType") -> bool:
        return True

class AnyType(Type):
    def datatype_hook(self):
        return AnyDataType(self.compiler)

@axe.chop
@axe.arg("x", axe.AnyValue())
@axe.arg("y", axe.AnyValue())
@axe.slash
def _swap(compiler: "Compiler", x: AcaciaExpr, y: AcaciaExpr):
    """
    swap(&x, &y, /)
    Swap values of two variables.
    """
    if not x.is_assignable():
        raise axe.ArgumentError("x", "must be a variable")
    if not y.is_assignable():
        raise axe.ArgumentError("y", "must be a variable")
    if not (x.data_type.is_type_of(y) and y.data_type.is_type_of(x)):
        raise axe.ArgumentError(
            "x", "must have the same type as the other variable"
            ' (got "%s" and "%s")' % (x.data_type, y.data_type)
        )
    return resultlib.commands(compiler.swap_exprs(x, y), compiler)

def acacia_build(compiler: "Compiler"):
    res = {}
    # builtin types
    for name, cls in (
        ('int', IntType),
        ('bool', BoolType),
        ('Pos', PosType),
        ('Rot', RotType),
        ('Offset', PosOffsetType),
        ('Engroup', EGroupGeneric),
        ('Enfilter', EFilterType),
        ('list', ListType),
        ('map', MapType),
        ('AbsPos', AbsPosType),
        ('ExternEngroup', ExternEGroupGeneric),
        ('Any', AnyType),
    ):
        res[name] = cls(compiler)
    # builtin names
    res['Entity'] = compiler.base_template
    res['swap'] = BinaryFunction(_swap, compiler)
    return res
