"""Builtin support for rotations.
NOTE When generating /execute context for rotations, we do NOT
overwrite executing position, so "facing <position>" is not
implemented. Workaround: summon an entity and teleport it to
facing position. Then use "Rot.face_entity".
"""

__all__ = ["RotType", "RotDataType", "Rotation"]

from typing import List, TYPE_CHECKING

import acaciamc.mccmdgen.cmds as cmds
from acaciamc.constants import DEFAULT_ANCHOR
from acaciamc.mccmdgen.ctexpr import CTDataType
from acaciamc.mccmdgen.datatype import DefaultDataType
from acaciamc.mccmdgen.expr import *
from acaciamc.tools import axe, cmethod_of, ImmutableMixin, transform_immutable
from . import entity as entity_module
from .functions import BinaryCTFunction
from .types import Type

if TYPE_CHECKING:
    from .entity import _EntityBase
    from acaciamc.mccmdgen.cmds import _ExecuteSubcmd


class RotDataType(DefaultDataType):
    name = "Rot"


ctdt_rotation = CTDataType("Rot")


class RotType(Type):
    def do_init(self):
        @cmethod_of(self, "__new__")
        class _new(metaclass=axe.OverloadChopped):
            """
            Rot(entity): rotation of an entity.
            Rot(int-literal, int-literal): absolute rotation
            """

            @axe.overload
            @axe.arg("entity", entity_module.EntityDataType)
            def from_entity(cls, compiler, entity: "_EntityBase"):
                inst = Rotation()
                inst.context.append(cmds.ExecuteEnv(
                    "rotated", "as " + entity.to_str()
                ))
                return inst

            @axe.overload
            @axe.arg("vertical", axe.LiteralFloat())
            @axe.arg("horizontal", axe.LiteralFloat())
            def absolute(cls, compiler, vertical: float, horizontal: float):
                inst = Rotation()
                inst.context.append(cmds.ExecuteEnv(
                    "rotated", "%s %s" % (vertical, horizontal)
                ))
                return inst

        @cmethod_of(self, "face_entity")
        @axe.chop
        @axe.arg("target", entity_module.EntityDataType)
        @axe.arg("anchor", axe.LiteralString(), default=DEFAULT_ANCHOR)
        def _face_entity(compiler, target: "_EntityBase", anchor: str):
            inst = Rotation()
            inst.context.append(cmds.ExecuteEnv(
                "facing", "entity %s %s" % (target, anchor)
            ))
            return inst

    def datatype_hook(self):
        return RotDataType()

    def cdatatype_hook(self):
        return ctdt_rotation


class Rotation(ConstExprCombined, ImmutableMixin):
    cdata_type = ctdt_rotation

    def __init__(self):
        super().__init__(RotDataType())
        self.context: List["_ExecuteSubcmd"] = []

        _abs = self._create_setter("")
        _offset = self._create_setter("~")
        """.abs(vertical, horizontal) .offset(vertical, horizontal)
        "vertical" & "horizontal" are either "None" or int literal or
        float, representing xrot and yrot values. "abs" directly sets
        rotation and "offset" rotates relatively.
        """
        self.attribute_table.set("abs", BinaryCTFunction(_abs))
        self.attribute_table.set("offset", BinaryCTFunction(_offset))

    def copy(self):
        res = Rotation()
        res.context.extend(self.context)
        return res

    def _create_setter(self, type_prefix: str):
        @axe.chop
        @axe.arg("vertical", axe.Nullable(axe.LiteralFloat()), default=None)
        @axe.arg("horizontal", axe.Nullable(axe.LiteralFloat()), default=None)
        @transform_immutable(self)
        def _setter(self: Rotation, compiler, vertical, horizontal):
            vh: List[str] = []
            for arg in (vertical, horizontal):
                if arg is None:
                    vh.append("~")
                else:
                    vh.append(type_prefix + str(arg))
            self.context.append(cmds.ExecuteEnv("rotated", " ".join(vh)))
            return self

        return _setter
