"""Builtin support for positions."""

__all__ = ["PosType", "PosDataType", "Position"]

from typing import List, TYPE_CHECKING

import acaciamc.mccmdgen.cmds as cmds
from acaciamc.constants import DEFAULT_ANCHOR, XYZ
from acaciamc.error import *
from acaciamc.mccmdgen.ctexpr import CTDataType
from acaciamc.mccmdgen.datatype import DefaultDataType
from acaciamc.mccmdgen.expr import *
from acaciamc.tools import axe, cmethod_of, ImmutableMixin, transform_immutable
from . import entity as entity_module
from .functions import BinaryFunction
from .position_offset import PosOffsetDataType, PosOffset, CoordinateType
from .rotation import RotDataType
from .types import Type

if TYPE_CHECKING:
    from .rotation import Rotation
    from .entity import _EntityBase
    from acaciamc.mccmdgen.cmds import _ExecuteSubcmd


class PosDataType(DefaultDataType):
    name = "Pos"


ctdt_position = CTDataType("Pos")


class PosType(Type):
    def do_init(self):
        @cmethod_of(self, "__new__")
        class _new(metaclass=axe.OverloadChopped):
            """
            Pos(entity, literal["feet", "eyes"] = "feet"):
                position of entity.
                Second argument is the anchor.
            Pos(int-literal, int-literal, int-literal):
                absolute position.
                If integer is provided for x and z, they are increased
                by 0.5, so that the position is at block center.
            """

            @axe.overload
            @axe.arg("target", entity_module.EntityDataType)
            @axe.arg("anchor", axe.LiteralString())
            def from_entity(cls, compiler, target: "_EntityBase", anchor: str):
                inst = Position()
                inst.context.append(cmds.ExecuteEnv("at", target.to_str()))
                inst.context.append(cmds.ExecuteEnv("anchored", anchor))
                return inst

            @axe.overload
            @axe.arg("target", entity_module.EntityDataType)
            def from_entity_no_anchor(cls, compiler, target: "_EntityBase"):
                return cls.from_entity(compiler, target, DEFAULT_ANCHOR)

            @axe.overload
            @axe.arg("x", axe.PosXZ())
            @axe.arg("y", axe.LiteralFloat())
            @axe.arg("z", axe.PosXZ())
            def absolute(cls, compiler, x: float, y: float, z: float):
                offset = PosOffset()
                offset.set(0, x, CoordinateType.ABSOLUTE)
                offset.set(1, y, CoordinateType.ABSOLUTE)
                offset.set(2, z, CoordinateType.ABSOLUTE)
                inst = Position()
                new_inst, cmds = (inst.attribute_table.lookup("apply")
                                  .call([offset], {}, compiler))
                return new_inst, cmds

    def datatype_hook(self):
        return PosDataType()

    def cdatatype_hook(self):
        return ctdt_position


class Position(ConstExprCombined, ImmutableMixin):
    cdata_type = ctdt_position

    def __init__(self):
        super().__init__(PosDataType())
        self.context: List["_ExecuteSubcmd"] = []

        @cmethod_of(self, "dim")
        @axe.chop
        @axe.arg("id", axe.LiteralString(), rename="id_")
        @transform_immutable(self)
        def _dim(self: Position, compiler, id_: str):
            """.dim(id: str): change dimension of position."""
            self.context.append(cmds.ExecuteEnv("in", id_))
            return self

        _abs = self._create_offset_alias("abs")
        _offset = self._create_offset_alias("offset")
        """.abs(...) .offset(...)
        Alias of .apply(Offset().abs/offset(...)).
        """

        @cmethod_of(self, "local")
        @axe.chop
        @axe.arg("rot", RotDataType)
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
            offset = PosOffset.local(left, up, front)
            self.context.extend(rot.context)
            self.context.append(cmds.ExecuteEnv("positioned", str(offset)))
            return self

        @cmethod_of(self, "apply")
        @axe.chop
        @axe.arg("offset", PosOffsetDataType)
        @transform_immutable(self)
        def _apply(self: Position, compiler, offset: PosOffset):
            """.apply(offset: Offset): Apply offset to current position."""
            self.context.append(cmds.ExecuteEnv("positioned", str(offset)))
            return self

        @cmethod_of(self, "align")
        @axe.chop
        @axe.arg("axis", axe.LiteralString(), default="xyz")
        @transform_immutable(self)
        def _align(self: Position, compiler, axis: str):
            """
            .align(axis: str = "xyz"): round position on given axis down
            to the nearest integer. The axis must be a combination of
            "x", "y" and "z". For example,
            `Pos(10.5, 9.8, 10.5).align("xz")` gives `Pos(10, 9.8, 10)`.
            """
            axis_set = set(axis)
            if len(axis) != len(axis_set) or not axis_set.issubset(XYZ):
                raise Error(ErrorType.INVALID_POS_ALIGN, align=axis)
            self.context.append(cmds.ExecuteEnv("align", axis))
            return self

        self.attribute_table.set("abs", BinaryFunction(_abs))
        self.attribute_table.set("offset", BinaryFunction(_offset))

    def _create_offset_alias(self, method: str):
        @transform_immutable(self)
        def _offset_alias(self: Position, compiler, args, kwds):
            offset, cmds = (
                PosOffset().attribute_table.lookup(method)
                .call(args, kwds, compiler)
            )
            new_obj, _cmds = (self.attribute_table.lookup("apply")
                              .call([offset], {}, compiler))
            cmds.extend(_cmds)
            return new_obj, cmds

        return _offset_alias

    def copy(self) -> "Position":
        res = Position()
        res.context = self.context.copy()
        return res
