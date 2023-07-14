"""Builtin support for positions."""

__all__ = ["Position"]

from typing import List, TYPE_CHECKING

from acaciamc.error import *
from acaciamc.tools import axe
from .base import *
from .types import DataType, PosType, PosOffsetType
from .position_offset import PosOffset, XYZ
from .callable import BinaryFunction
from .rotation import RotType

if TYPE_CHECKING:
    from .rotation import Rotation

class Position(AcaciaExpr):
    def __init__(self, compiler):
        super().__init__(DataType.from_type_cls(PosType, compiler), compiler)
        self.context: List[str] = []  # /execute subcommands

        @axe.chop
        @axe.arg("id", axe.LiteralString(), rename="id_")
        def _dim(compiler, id_: str):
            """.dim(id: str): change dimension of position."""
            self.context.append("in %s" % id_)
            return self
        _abs = self._create_offset_alia("abs")
        _offset = self._create_offset_alia("offset")
        """.abs(...) .offset(...)
        Alias of .apply(Offset().abs/offset(...)).
        """
        @axe.chop
        @axe.arg("rot", RotType)
        @axe.arg("left", axe.LiteralFloat(), default=0.0)
        @axe.arg("up", axe.LiteralFloat(), default=0.0)
        @axe.arg("front", axe.LiteralFloat(), default=0.0)
        def _local(compiler, rot: "Rotation", left: float,
                   up: float, front: float):
            """.local(rot: Rot, left: float = 0.0, up: float = 0.0,
                      front: float = 0.0)
            Apply local offset to current position, using given rotation.
            """
            offset = PosOffset.local(left, up, front, compiler)
            self.context.extend(rot.context)
            _, cmds = self.attribute_table.lookup("apply").call([offset], {})
            return self, cmds
        @axe.chop
        @axe.arg("offset", PosOffsetType)
        def _apply(compiler, offset: PosOffset):
            """.apply(offset: Offset): Apply offset to current position."""
            self.context.append("positioned %s" % offset)
            return self
        @axe.chop
        @axe.arg("axis", axe.LiteralString(), default="xyz")
        def _align(compiler, axis: str):
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

    def _create_offset_alia(self, method: str):
        def _offset_alia(compiler, args, kwds):
            offset = PosOffset(self.compiler)
            _, cmds = offset.attribute_table.lookup(method).call(args, kwds)
            _, _cmds = self.attribute_table.lookup("apply").call([offset], {})
            cmds.extend(_cmds)
            return self, cmds
        return _offset_alia

    def copy(self) -> "Position":
        res = Position(self.compiler)
        res.context = self.context.copy()
        return res
