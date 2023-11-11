"""Builtin support for rotations.
NOTE When generating /execute context for rotations, we do NOT
overwrite executing position, so "facing <position>" is not
implemented. Workaround: summon an entity and teleport it to
facing position. Then use "Rot.face_entity".
"""

__all__ = ["RotType", "RotDataType", "Rotation"]

from typing import List, TYPE_CHECKING

from acaciamc.tools import axe, method_of
from acaciamc.constants import DEFAULT_ANCHOR
from acaciamc.mccmdgen.datatype import DefaultDataType
import acaciamc.mccmdgen.cmds as cmds
from .base import *
from .types import Type
from .functions import BinaryFunction
from .entity import EntityDataType

if TYPE_CHECKING:
    from .entity import _EntityBase
    from acaciamc.mccmdgen.cmds import _ExecuteSubcmd

class RotDataType(DefaultDataType):
    name = "Rot"

class RotType(Type):
    def do_init(self):
        @method_of(self, "__new__")
        class _new(metaclass=axe.OverloadChopped):
            """
            Rot(entity): rotation of an entity.
            Rot(int-literal, int-literal): absolute rotation
            """
            @axe.overload
            @axe.arg("entity", EntityDataType)
            def from_entity(cls, compiler, entity: "_EntityBase"):
                inst = Rotation(compiler)
                inst.context.append(cmds.ExecuteEnv(
                    "rotated", "as " + entity.to_str()
                ))
                return inst

            @axe.overload
            @axe.arg("vertical", axe.LiteralFloat())
            @axe.arg("horizontal", axe.LiteralFloat())
            def absolute(cls, compiler, vertical: float, horizontal: float):
                inst = Rotation(compiler)
                inst.context.append(cmds.ExecuteEnv(
                    "rotated", "%s %s" % (vertical, horizontal)
                ))
                return inst
        @method_of(self, "face_entity")
        @axe.chop
        @axe.arg("target", EntityDataType)
        @axe.arg("anchor", axe.LiteralString(), default=DEFAULT_ANCHOR)
        def _face_entity(compiler, target: "_EntityBase", anchor: str):
            inst = Rotation(compiler)
            inst.context.append(cmds.ExecuteEnv(
                "facing", "entity %s %s" % (target, anchor)
            ))
            return inst

    def datatype_hook(self):
        return RotDataType()

class Rotation(AcaciaExpr, ImmutableMixin):
    def __init__(self, compiler):
        super().__init__(RotDataType(), compiler)
        self.context: List["_ExecuteSubcmd"] = []

        _abs = self._create_setter("")
        _offset = self._create_setter("~")
        """.abs(vertical, horizontal) .offset(vertical, horizontal)
        "vertical" & "horizontal" are either "None" or int literal or
        float, representing xrot and yrot values. "abs" directly sets
        rotation and "offset" rotates relatively.
        """
        self.attribute_table.set("abs", BinaryFunction(_abs, self.compiler))
        self.attribute_table.set(
            "offset", BinaryFunction(_offset, self.compiler))

    def copy(self):
        res = Rotation(self.compiler)
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
