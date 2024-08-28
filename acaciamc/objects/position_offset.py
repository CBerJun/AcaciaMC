"""Position offset.
Builtin type that represents a position, but without the context. (i.e
the /execute subcommands)
For instance, "~ ~5 ~" is a position offset, while
"~ ~5 ~ from xxx entity" is a position.
"""

__all__ = ["PosOffsetType", "PosOffsetDataType", "PosOffset", "CoordinateType"]

from enum import Enum
from typing import List

from acaciamc.error import *
from acaciamc.mccmdgen.ctexpr import CTDataType
from acaciamc.mccmdgen.datatype import DefaultDataType
from acaciamc.mccmdgen.expr import *
from acaciamc.tools import axe, cmethod_of, ImmutableMixin, transform_immutable
from .types import Type


class CoordinateType(Enum):
    ABSOLUTE = ""
    RELATIVE = "~"
    LOCAL = "^"


class PosOffsetDataType(DefaultDataType):
    name = "Offset"


ctdt_posoffset = CTDataType("Offset")


class PosOffsetType(Type):
    def do_init(self):
        @cmethod_of(self, "__new__")
        @axe.chop
        @axe.arg("x", axe.Nullable(axe.LiteralFloat()), default=None)
        @axe.arg("y", axe.Nullable(axe.LiteralFloat()), default=None)
        @axe.arg("z", axe.Nullable(axe.LiteralFloat()), default=None)
        @axe.star
        @axe.arg("x_abs", axe.Nullable(axe.LiteralFloat()), default=None)
        @axe.arg("y_abs", axe.Nullable(axe.LiteralFloat()), default=None)
        @axe.arg("z_abs", axe.Nullable(axe.LiteralFloat()), default=None)
        def _new(compiler, x, y, z, x_abs, y_abs, z_abs):
            """
            const def __new__(
                x = None, y = None, z = None,
                *,
                x_abs = None, y_abs = None, z_abs = None
            ) -> Offset
            Return a new Offset object. All the parameters are either
            None or float. At most one of * and *_abs should be float
            for each of x, y, z. The created object will use
            relative coordinate if * is used, absolute for *_abs, or
            relative with value 0.0 if neither is given.
            Consider AbsPos if all three of them are absolute.
            """
            res = PosOffset()
            if x is not None and x_abs is not None:
                raise Error(ErrorType.POS_OFFSET_CTOR_ARG, axis="x")
            if y is not None and y_abs is not None:
                raise Error(ErrorType.POS_OFFSET_CTOR_ARG, axis="y")
            if z is not None and z_abs is not None:
                raise Error(ErrorType.POS_OFFSET_CTOR_ARG, axis="z")
            if x is None:
                x = 0.0
            if y is None:
                y = 0.0
            if z is None:
                z = 0.0
            res._set(CoordinateType.RELATIVE, x, y, z)
            res._set(CoordinateType.ABSOLUTE, x_abs, y_abs, z_abs)
            return res

        @cmethod_of(self, "local")
        @axe.chop
        @axe.arg("left", axe.LiteralFloat(), default=0.0)
        @axe.arg("up", axe.LiteralFloat(), default=0.0)
        @axe.arg("front", axe.LiteralFloat(), default=0.0)
        def _local(compiler, left: float, up: float, front: float):
            """Offset.local(left, up, front)
            Return new object using local coordinate.
            """
            return PosOffset.local(left, up, front)

    def datatype_hook(self):
        return PosOffsetDataType()

    def cdatatype_hook(self):
        return ctdt_posoffset


class PosOffset(ConstExprCombined, ImmutableMixin):
    cdata_type = ctdt_posoffset

    def __init__(self):
        super().__init__(PosOffsetDataType())
        self.values: List[float] = [0.0, 0.0, 0.0]
        self.value_types: List[CoordinateType] = \
            [CoordinateType.RELATIVE for _ in range(3)]

        @cmethod_of(self, "abs")
        @axe.chop
        @axe.arg("x", axe.Nullable(axe.PosXZ()), default=None)
        @axe.arg("y", axe.Nullable(axe.LiteralFloat()), default=None)
        @axe.arg("z", axe.Nullable(axe.PosXZ()), default=None)
        @transform_immutable(self)
        def _abs(self: PosOffset, compiler, x, y, z):
            self._set(CoordinateType.ABSOLUTE, x, y, z)
            return self

        @cmethod_of(self, "offset")
        @axe.chop
        @axe.arg("x", axe.Nullable(axe.LiteralFloat()), default=None)
        @axe.arg("y", axe.Nullable(axe.LiteralFloat()), default=None)
        @axe.arg("z", axe.Nullable(axe.LiteralFloat()), default=None)
        @transform_immutable(self)
        def _offset(self: PosOffset, compiler, x, y, z):
            self._set(CoordinateType.RELATIVE, x, y, z)
            return self

        """
        .offset(x, y, z) .abs(x, y, z)
        "x", "y" and "z" are either "None" or int literal or float.
        "offset" sets given axes to use relative coordinate,
        while "abs" sets them to use absolute coordinate.
        "abs" rounds integer x and z value to block center.
        """

    def __str__(self) -> str:
        return " ".join(
            type_.value + str(value)
            for type_, value in zip(self.value_types, self.values)
        )

    def _set(self, coord_type: CoordinateType, x, y, z):
        if x is not None:
            self.set(0, x, coord_type)
        if y is not None:
            self.set(1, y, coord_type)
        if z is not None:
            self.set(2, z, coord_type)

    @classmethod
    def local(cls, left: float, up: float, front: float):
        inst = cls()
        inst.set(0, left, CoordinateType.LOCAL)
        inst.set(1, up, CoordinateType.LOCAL)
        inst.set(2, front, CoordinateType.LOCAL)
        return inst

    def set(self, index: int, value: float, type_: CoordinateType):
        assert 0 <= index <= 2
        self.values[index] = value
        self.value_types[index] = type_

    def copy(self) -> "PosOffset":
        res = PosOffset()
        res.values = self.values.copy()
        res.value_types = self.value_types.copy()
        return res
