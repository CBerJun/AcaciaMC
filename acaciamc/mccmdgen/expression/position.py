"""Builtin support for positions."""

__all__ = ["Position"]

from typing import List
from functools import partialmethod

from acaciamc.error import *
from .base import *
from .types import (
    DataType, PosType, StringType, PosOffsetType, FloatType, IntType
)
from .position_offset import PosOffset, XYZ
from .callable import BinaryFunction
from .rotation import RotType
from .string import String
from .integer import IntLiteral
from .float_ import Float

class Position(AcaciaExpr):
    def __init__(self, compiler):
        super().__init__(DataType.from_type_cls(PosType, compiler), compiler)
        self.context: List[str] = []  # /execute subcommands
        self.attribute_table.set(
            "dim", BinaryFunction(self._dim, self.compiler))
        self.attribute_table.set(
            "abs", BinaryFunction(self._abs, self.compiler))
        self.attribute_table.set(
            "offset", BinaryFunction(self._offset, self.compiler))
        self.attribute_table.set(
            "local", BinaryFunction(self._local, self.compiler))
        self.attribute_table.set(
            "apply", BinaryFunction(self._apply, self.compiler))
        self.attribute_table.set(
            "align", BinaryFunction(self._align, self.compiler))
        # For debug, define a function to print the context
        self.attribute_table.set(
            "context", BinaryFunction(self._context, self.compiler)
        )

    def _dim(self, func: BinaryFunction):
        """.dim(id: str): change dimension of position."""
        arg_id = func.arg_require("id", StringType)
        func.assert_no_arg()
        self.context.append("in %s" % arg_id.value)
        return self

    def _offset_alia(self, func: BinaryFunction, method: str):
        offset = PosOffset(self.compiler)
        _, cmds = offset.attribute_table.lookup(method).call(*func.arg_raw())
        _, _cmds = self.attribute_table.lookup("apply").call([offset], {})
        cmds.extend(_cmds)
        return self, cmds

    _abs = partialmethod(_offset_alia, method="abs")
    _offset = partialmethod(_offset_alia, method="offset")
    """.abs(...) .offset(...)
    Alias of .apply(Offset().abs/offset(...)).
    """

    def _local(self, func: BinaryFunction):
        """.local(rot: Rot, left: float = 0.0, up: float = 0.0,
                  front: float = 0.0)
        Apply local offset to current position, using given rotation.
        """
        arg_rot = func.arg_require("rot", RotType)
        args_xyz: List[AcaciaExpr] = []
        for name in ("left", "up", "front"):
            arg = func.arg_optional(
                name, Float(0.0, self.compiler), (FloatType, IntType)
            )
            if arg.data_type.raw_matches(IntType):
                if not isinstance(arg, IntLiteral):
                    func.arg_error(name, "integer must be literal")
                arg = Float.from_int(arg)
            args_xyz.append(arg)
        func.assert_no_arg()
        offset = PosOffset.local(*args_xyz, self.compiler)
        self.context.extend(arg_rot.context)
        _, cmds = self.attribute_table.lookup("apply").call([offset], {})
        return self, cmds

    def _apply(self, func: BinaryFunction):
        """.apply(offset: Offset): Apply offset to current position."""
        offset = func.arg_require("offset", PosOffsetType)
        func.assert_no_arg()
        self.context.append("positioned %s" % offset)
        return self

    def _align(self, func: BinaryFunction):
        """.align(axis: str = "xyz"): round position on given axis
        using floor method. The axis must be a combination of "x", "y",
        and "z". For example,
        `Pos(10.5, 9.8, 10.5).align(Pos.X + Pos.Z)` gives
        `Pos(10, 9.8, 10)`.
        """
        arg_axis = func.arg_optional(
            "axis", String("xyz", func.compiler), StringType
        )
        func.assert_no_arg()
        axis = arg_axis.value
        axis_set = set(axis)
        if len(axis) != len(axis_set) or not axis_set.issubset(XYZ):
            raise Error(ErrorType.INVALID_POS_ALIGN, align=axis)
        self.context.append("align %s" % axis)
        return self

    def _context(self, func: BinaryFunction):
        func.assert_no_arg()
        print(self.context)
        return self

    def copy(self) -> "Position":
        res = Position(self.compiler)
        res.context = self.context.copy()
        return res
