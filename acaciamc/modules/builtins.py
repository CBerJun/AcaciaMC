from typing import Union, TYPE_CHECKING

import acaciamc.mccmdgen.cmds as cmds
from acaciamc.error import Error, ErrorType
from acaciamc.localization import localize
from acaciamc.mccmdgen.ctexpr import CTDataType
from acaciamc.mccmdgen.datatype import DataType
from acaciamc.mccmdgen.expr import *
from acaciamc.objects import *
from acaciamc.tools import axe, resultlib

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from acaciamc.objects.entity import _EntityBase


class AnyDataType(DataType):
    def __str__(self) -> str:
        return 'Any'

    @classmethod
    def name_no_generic(cls) -> str:
        return 'Any'

    def matches(self, other: "DataType") -> bool:
        return True


class _AnyCTDataType(CTDataType):
    def is_baseof(self, other: CTDataType) -> bool:
        return True


any_ctdt = _AnyCTDataType("Any")


class AnyType(Type):
    def datatype_hook(self):
        return AnyDataType()

    def cdatatype_hook(self):
        return any_ctdt


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
        raise axe.ArgumentError(
            "x", localize("modules.builtins.swap.assignable")
        )
    if not y.is_assignable():
        raise axe.ArgumentError(
            "y", localize("modules.builtins.swap.assignable")
        )
    if not (x.data_type.is_type_of(y) and y.data_type.is_type_of(x)):
        raise axe.ArgumentError(
            "x",
            localize("modules.builtins.swap.differenttype")
            % (x.data_type, y.data_type)
        )
    return resultlib.commands(swap_exprs(x, y, compiler))


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
    return IntVar(cmds.ScbSlot(tg, objective))


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
            ('Any', AnyType),
            ('float', FloatType),
    ):
        res[name] = cls()
    res['ExternEngroup'] = ExternEGroupType(compiler)
    # builtin names
    res['Entity'] = compiler.base_template
    res['swap'] = BinaryFunction(swap)
    res['scb'] = BinaryFunction(scb)
    res['upcast'] = BinaryFunction(upcast)
    return res
