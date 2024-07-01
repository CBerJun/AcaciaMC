"""A convenience object that represents an absolute position.
Most important: it is compatible with both `Pos` and `Offset`.
"""

import acaciamc.mccmdgen.cmds as cmds
from acaciamc.constants import XYZ
from acaciamc.mccmdgen.ctexpr import CTDataType
from acaciamc.mccmdgen.expr import *
from acaciamc.tools import axe, cmethod_of, transform_immutable
from .float_ import Float
from .position import PosDataType, Position, ctdt_position
from .position_offset import (
    PosOffsetDataType, PosOffset, CoordinateType, ctdt_posoffset
)
from .types import Type


class AbsPosDataType(PosDataType, PosOffsetDataType):
    name = "AbsPos"


ctdt_abspos = CTDataType("AbsPos", (ctdt_posoffset, ctdt_position))


class AbsPosType(Type):
    def do_init(self):
        @cmethod_of(self, "__new__")
        @axe.chop
        @axe.arg("x", axe.PosXZ())
        @axe.arg("y", axe.LiteralFloat())
        @axe.arg("z", axe.PosXZ())
        def _new(compiler, x: float, y: float, z: float):
            return AbsPos(x, y, z)

    def datatype_hook(self):
        return AbsPosDataType()

    def cdatatype_hook(self):
        return ctdt_abspos


class AbsPos(Position, PosOffset):
    cdata_type = ctdt_abspos

    # XXX As you can see the inheritance is a bit weird, we can't even
    # call __init__ properly.
    def __init__(self, x: float, y: float, z: float):
        AcaciaExpr.__init__(self, AbsPosDataType())
        self._context = cmds.ExecuteEnv("positioned", "")
        self.context = [self._context]
        self.values = [x, y, z]
        self.value_types = [CoordinateType.ABSOLUTE for _ in range(3)]
        self.already_set = set()
        self._update()

        # for attr in ("dim", "local", "apply", "align"):
        #     self.attribute_table.delete(attr)

        @cmethod_of(self, "abs")
        @axe.chop
        @axe.arg("x", axe.Nullable(axe.PosXZ()), default=None)
        @axe.arg("y", axe.Nullable(axe.LiteralFloat()), default=None)
        @axe.arg("z", axe.Nullable(axe.PosXZ()), default=None)
        @transform_immutable(self)
        def _abs(self: "AbsPos", compiler, x, y, z):
            for i, value in enumerate((x, y, z)):
                if value is not None:
                    self.set_abs(i, value)
            return self

        @cmethod_of(self, "offset")
        @axe.chop
        @axe.arg("x", axe.Nullable(axe.LiteralFloat()), default=None)
        @axe.arg("y", axe.Nullable(axe.LiteralFloat()), default=None)
        @axe.arg("z", axe.Nullable(axe.LiteralFloat()), default=None)
        @transform_immutable(self)
        def _offset(self: "AbsPos", compiler, x, y, z):
            for i, value in enumerate((x, y, z)):
                if value is not None:
                    self.set_offset(i, value)
            return self

    def copy(self):
        return AbsPos(*self.values)

    def _update(self):
        self._context.args = str(self)
        for name, value in zip(XYZ, self.values):
            self.attribute_table.set(name, Float(value))

    def set_abs(self, i: int, value: float):
        self.values[i] = value
        self._update()

    def set_offset(self, i: int, value: float):
        self.values[i] += value
        self._update()
