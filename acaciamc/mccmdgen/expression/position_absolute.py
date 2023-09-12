"""A convenience object that represents an absolute position.
Most important: it is compatible with both `Pos` and `Offset`.
"""

import acaciamc.mccmdgen.cmds as cmds
from acaciamc.tools import axe, method_of
from .base import *
from .types import Type
from .position import PosDataType, Position
from .position_offset import PosOffsetDataType, PosOffset, CoordinateType

class AbsPosDataType(PosDataType, PosOffsetDataType):
    name = "AbsPos"

class AbsPosType(Type):
    def do_init(self):
        @method_of(self, "__new__")
        @axe.chop
        @axe.arg("x", axe.LiteralFloat())
        @axe.arg("y", axe.LiteralFloat())
        @axe.arg("z", axe.LiteralFloat())
        def _new(compiler, x: float, y: float, z: float):
            return AbsPos(x, y, z, compiler)

    def datatype_hook(self):
        return AbsPosDataType()

class AbsPos(Position, PosOffset):
    # XXX As you can see the inheritance is a bit weird, we can't even
    # call __init__ properly.
    def __init__(self, x: float, y: float, z: float, compiler):
        AcaciaExpr.__init__(self, AbsPosDataType(), compiler)
        self._context = cmds.ExecuteEnv("positioned", "")
        self.context = [self._context]
        self.values = [x, y, z]
        self.value_types = [CoordinateType.ABSOLUTE for _ in range(3)]
        self.already_set = set()
        self._update_context()
        # for attr in ("dim", "local", "apply", "align"):
        #     self.attribute_table.delete(attr)

        @method_of(self, "abs")
        @axe.chop
        @axe.arg("x", axe.Nullable(axe.LiteralFloat()), default=None)
        @axe.arg("y", axe.Nullable(axe.LiteralFloat()), default=None)
        @axe.arg("z", axe.Nullable(axe.LiteralFloat()), default=None)
        @transform_immutable(self)
        def _abs(self: "AbsPos", compiler, x, y, z):
            for i, value in enumerate((x, y, z)):
                if value is not None:
                    self.set_abs(i, value)
            return self
        @method_of(self, "offset")
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
        return AbsPos(*self.values, self.compiler)

    def _update_context(self):
        self._context.args = str(self)

    def set_abs(self, i: int, value: float):
        self.values[i] = value
        self._update_context()

    def set_offset(self, i: int, value: float):
        self.values[i] += value
        self._update_context()
