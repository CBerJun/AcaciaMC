"""Builtin support for rotations.
NOTE When generating /execute context for rotations, we do NOT
overwrite executing position, so "facing <position>" is not
implemented. Workaround: summon an entity and teleport it to
facing position. Then use "Rot.face_entity".
"""

__all__ = ["RotType", "Rotation"]

from typing import List, TYPE_CHECKING

from acaciamc.tools import axe
from acaciamc.constants import DEFAULT_ANCHOR
from .base import *
from .types import Type, DataType
from .callable import BinaryFunction
from .entity import EntityType

if TYPE_CHECKING:
    from .entity import _EntityBase

class RotType(Type):
    name = "Rot"

    def do_init(self):
        class _new(metaclass=axe.OverloadChopped):
            """
            Rot(entity): rotation of an entity.
            Rot(int-literal, int-literal): absolute rotation
            """
            @axe.overload
            @axe.arg("target", EntityType)
            def from_entity(cls, compiler, entity: "_EntityBase"):
                inst = Rotation(compiler)
                inst.context.append("rotated as %s" % entity)
                return inst

            @axe.overload
            @axe.arg("vertical", axe.LiteralFloat())
            @axe.arg("horizontal", axe.LiteralFloat())
            def absolute(cls, compiler, vertical: float, horizontal: float):
                inst = Rotation(compiler)
                inst.context.append("rotated %s %s" % (vertical, horizontal))
                return inst
        self.attribute_table.set(
            "__new__", BinaryFunction(_new, self.compiler)
        )
        @axe.chop
        @axe.arg("target", EntityType)
        @axe.arg("anchor", axe.LiteralString(), default=DEFAULT_ANCHOR)
        def _face_entity(compiler, target: "_EntityBase", anchor: str):
            inst = Rotation(compiler)
            inst.context.append("facing entity %s %s" % (target, anchor))
            return inst
        self.attribute_table.set(
            "face_entity", BinaryFunction(_face_entity, self.compiler)
        )

class Rotation(AcaciaExpr, ImmutableMixin):
    def __init__(self, compiler):
        super().__init__(DataType.from_type_cls(RotType, compiler), compiler)
        self.context: List[str] = []

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
            self.context.append("rotated " + " ".join(vh))
            return self
        return _setter
