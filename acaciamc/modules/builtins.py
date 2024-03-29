from typing import Union, TYPE_CHECKING

from acaciamc.mccmdgen.expression import *
from acaciamc.mccmdgen.datatype import DataType
from acaciamc.tools import axe, resultlib
from acaciamc.error import Error, ErrorType
import acaciamc.mccmdgen.cmds as cmds

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from acaciamc.mccmdgen.expression.entity import _EntityBase

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
def swap(compiler: "Compiler", x: AcaciaExpr, y: AcaciaExpr):
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

@axe.chop
@axe.arg("target", axe.AnyOf(axe.LiteralString(), axe.Typed(EntityDataType)))
@axe.arg("objective", axe.LiteralString())
def scb(compiler, target: Union["_EntityBase", str], objective: str):
    """
    scb(target: str | entity, objective: str) -> &int
    Return a reference to the score of `target` on `objective`. This is
    used to interact with scores on scoreboard.
    """
    tg = target if isinstance(target, str) else target.to_str()
    return IntVar(cmds.ScbSlot(tg, objective), compiler)

@axe.chop
@axe.arg("object", EntityDataType, rename="obj")
@axe.arg("template", ETemplateDataType)
@axe.slash
def upcast(compiler, obj: "_EntityBase", template: EntityTemplate):
    """
    upcast(object: entity, template: entity_template) -> entity
    Up-cast entity `object` to `template`.
    """
    if not obj.template.is_subtemplate_of(template):
        raise Error(ErrorType.INVALID_UPCAST,
                    t1=obj.template.name, t2=template.name)
    return obj.cast_to(template)

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
    res['swap'] = BinaryFunction(swap, compiler)
    res['scb'] = BinaryFunction(scb, compiler)
    res['upcast'] = BinaryFunction(upcast, compiler)
    return res
