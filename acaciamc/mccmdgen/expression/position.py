"""Builtin support for positions."""

__all__ = ["PosType", "Position"]

from typing import List, TYPE_CHECKING

from acaciamc.error import *
from acaciamc.tools import axe
from acaciamc.constants import DEFAULT_ANCHOR, XYZ
from .base import *
from .types import Type, DataType
from .position_offset import PosOffsetType, PosOffset, CoordinateType
from .callable import BinaryFunction
from .rotation import RotType
from .string import String
from .entity import EntityType

if TYPE_CHECKING:
    from .rotation import Rotation
    from .entity import _EntityBase

class PosType(Type):
    name = "Pos"

    def do_init(self):
        self.attribute_table.set(
            "OVERWORLD", String("overworld", self.compiler)
        )
        self.attribute_table.set("NETHER", String("nether", self.compiler))
        self.attribute_table.set("THE_END", String("the_end", self.compiler))
        self.attribute_table.set("FEET", String("feet", self.compiler))
        self.attribute_table.set("EYES", String("eyes", self.compiler))
        self.attribute_table.set("X", String("x", self.compiler))
        self.attribute_table.set("Y", String("y", self.compiler))
        self.attribute_table.set("Z", String("z", self.compiler))
        class _new(metaclass=axe.OverloadChopped):
            """
            Pos(entity, [str]):
                position of entity. `str` is anchor (`Pos.EYES` or
                `Pos.FEET`).
            Pos(int-literal, int-literal, int-literal):
                absolute position.
            """
            @axe.overload
            @axe.arg("target", EntityType)
            @axe.arg("anchor", axe.LiteralString())
            def from_entity(cls, compiler, target: "_EntityBase", anchor: str):
                inst = Position(compiler)
                inst.context.append("at %s" % target)
                inst.context.append("anchored %s" % anchor)
                return inst

            @axe.overload
            @axe.arg("target", EntityType)
            def from_entity_no_anchor(cls, compiler, target: "_EntityBase"):
                return cls.from_entity(compiler, target, DEFAULT_ANCHOR)

            @axe.overload
            @axe.arg("x", axe.LiteralFloat())
            @axe.arg("y", axe.LiteralFloat())
            @axe.arg("z", axe.LiteralFloat())
            def absolute(cls, compiler, x: float, y: float, z: float):
                offset = PosOffset(compiler)
                offset.set(0, x, CoordinateType.ABSOLUTE)
                offset.set(1, y, CoordinateType.ABSOLUTE)
                offset.set(2, z, CoordinateType.ABSOLUTE)
                inst = Position(compiler)
                new_inst, cmds = (inst.attribute_table.lookup("apply")
                                  .call([offset], {}))
                return new_inst, cmds
        self.attribute_table.set(
            '__new__', BinaryFunction(_new, self.compiler)
        )

class Position(AcaciaExpr, ImmutableMixin):
    def __init__(self, compiler):
        super().__init__(DataType.from_type_cls(PosType, compiler), compiler)
        self.context: List[str] = []  # /execute subcommands

        @axe.chop
        @axe.arg("id", axe.LiteralString(), rename="id_")
        @transform_immutable(self)
        def _dim(self: Position, compiler, id_: str):
            """.dim(id: str): change dimension of position."""
            self.context.append("in %s" % id_)
            return self
        _abs = self._create_offset_alias("abs")
        _offset = self._create_offset_alias("offset")
        """.abs(...) .offset(...)
        Alias of .apply(Offset().abs/offset(...)).
        """
        @axe.chop
        @axe.arg("rot", RotType)
        @axe.arg("left", axe.LiteralFloat(), default=0.0)
        @axe.arg("up", axe.LiteralFloat(), default=0.0)
        @axe.arg("front", axe.LiteralFloat(), default=0.0)
        @transform_immutable(self)
        def _local(self: Position, compiler, rot: "Rotation", left: float,
                   up: float, front: float):
            """.local(rot: Rot, left: float = 0.0, up: float = 0.0,
                      front: float = 0.0)
            Apply local offset to current position, using given rotation.
            """
            offset = PosOffset.local(left, up, front, compiler)
            self.context.extend(rot.context)
            new_obj, cmds = (self.attribute_table.lookup("apply")
                             .call([offset], {}))
            return new_obj, cmds
        @axe.chop
        @axe.arg("offset", PosOffsetType)
        @transform_immutable(self)
        def _apply(self: Position, compiler, offset: PosOffset):
            """.apply(offset: Offset): Apply offset to current position."""
            self.context.append("positioned %s" % offset)
            return self
        @axe.chop
        @axe.arg("axis", axe.LiteralString(), default="xyz")
        @transform_immutable(self)
        def _align(self: Position, compiler, axis: str):
            """.align(axis: str = "xyz"): round position on given axis
            using floor method. The axis must be a combination of "x", "y",
            and "z". For example,
            `Pos(10.5, 9.8, 10.5).align(Pos.X + Pos.Z)` gives
            `Pos(10, 9.8, 10)`.
            """
            axis_set = set(axis)
            if len(axis) != len(axis_set) or not axis_set.issubset(XYZ):
                raise Error(ErrorType.INVALID_POS_ALIGN, align=axis)
            self.context.append("align %s" % axis)
            return self
        @axe.chop
        def _context(compiler):
            """.context(): print current context (debug only)."""
            print(self.context)
            return self
        self.attribute_table.set("dim", BinaryFunction(_dim, self.compiler))
        self.attribute_table.set("abs", BinaryFunction(_abs, self.compiler))
        self.attribute_table.set(
            "offset", BinaryFunction(_offset, self.compiler))
        self.attribute_table.set(
            "local", BinaryFunction(_local, self.compiler))
        self.attribute_table.set(
            "apply", BinaryFunction(_apply, self.compiler))
        self.attribute_table.set(
            "align", BinaryFunction(_align, self.compiler))
        self.attribute_table.set(
            "context", BinaryFunction(_context, self.compiler))

    def _create_offset_alias(self, method: str):
        @transform_immutable(self)
        def _offset_alias(self: Position, compiler, args, kwds):
            offset = PosOffset(compiler)
            _, cmds = (offset.attribute_table.lookup(method)
                       .call(args, kwds))
            new_obj, _cmds = (self.attribute_table.lookup("apply")
                              .call([offset], {}))
            cmds.extend(_cmds)
            return new_obj, cmds
        return _offset_alias

    def copy(self) -> "Position":
        res = Position(self.compiler)
        res.context = self.context.copy()
        return res
