from typing import TYPE_CHECKING

from acaciamc.mccmdgen.expression import *
from acaciamc.mccmdgen.datatype import DataType

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
    return res
