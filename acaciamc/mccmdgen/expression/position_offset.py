"""Position offset.
Builtin type that represents a position, but without the context. (i.e
the /execute subcommands)
For instance, "~ ~5 ~" is a position offset, while
"~ ~5 ~ from xxx entity" is a position.
"""

__all__ = ["PosOffsetType", "PosOffsetDataType", "PosOffset", "CoordinateType"]

from typing import Set, List
from enum import Enum

from acaciamc.error import *
from acaciamc.tools import axe, method_of
from acaciamc.constants import XYZ
from acaciamc.mccmdgen.datatype import DefaultDataType
from .base import *
from .types import Type
from .callable import BinaryFunction

class CoordinateType(Enum):
    ABSOLUTE = ""
    RELATIVE = "~"
    LOCAL = "^"

class PosOffsetDataType(DefaultDataType):
    name = "Offset"

class PosOffsetType(Type):
    def do_init(self):
        @method_of(self, "__new__")
        @axe.chop
        def _new(compiler):
            """Offset(): New object with no offset (~ ~ ~)."""
            return PosOffset(compiler)
        @method_of(self, "local")
        @axe.chop
        @axe.arg("left", axe.LiteralFloat(), default=0.0)
        @axe.arg("up", axe.LiteralFloat(), default=0.0)
        @axe.arg("front", axe.LiteralFloat(), default=0.0)
        def _local(compiler, left: float, up: float, front: float):
            """Offset.local(left, up, front)
            Return new object using local coordinate.
            """
            return PosOffset.local(left, up, front, compiler)

    def datatype_hook(self):
        return PosOffsetDataType()

class PosOffset(AcaciaExpr):
    def __init__(self, compiler):
        super().__init__(PosOffsetDataType(), compiler)
        self.values: List[float] = [0.0, 0.0, 0.0]
        self.value_types: List[CoordinateType] = \
            [CoordinateType.RELATIVE for _ in range(3)]
        self.already_set: Set[int] = set()
        _abs = self._create_setter(CoordinateType.ABSOLUTE)
        _offset = self._create_setter(CoordinateType.RELATIVE)
        """.offset(x, y, z) .abs(x, y, z)
        "x", "y" and "z" are either "None" or int literal or float.
        "offset" sets given axes to use relative coordinate,
        while "abs" sets them to use absolute coordinate.
        """
        self.attribute_table.set(
            "offset", BinaryFunction(_offset, self.compiler))
        self.attribute_table.set(
            "abs", BinaryFunction(_abs, self.compiler))

    def __str__(self) -> str:
        return " ".join(
            type_.value + str(value)
            for type_, value in zip(self.value_types, self.values)
        )

    def _create_setter(self, offset_type: CoordinateType):
        @axe.chop
        @axe.arg("x", axe.Nullable(axe.LiteralFloat()), default=None)
        @axe.arg("y", axe.Nullable(axe.LiteralFloat()), default=None)
        @axe.arg("z", axe.Nullable(axe.LiteralFloat()), default=None)
        def _setter(compiler, x, y, z):
            for i, arg in enumerate((x, y, z)):
                if arg is not None:
                    if i in self.already_set:
                        raise Error(ErrorType.POS_OFFSET_ALREADY_SET,
                                    axis=XYZ[i])
                    self.already_set.add(i)
                    self.set(i, arg, offset_type)
            return self
        return _setter

    @classmethod
    def local(cls, left: float, up: float, front: float, compiler):
        inst = cls(compiler)
        inst.set(0, left, CoordinateType.LOCAL)
        inst.set(1, up, CoordinateType.LOCAL)
        inst.set(2, front, CoordinateType.LOCAL)
        inst.already_set.update((0, 1, 2))
        return inst

    def set(self, index: int, value: float, type_: CoordinateType):
        assert 0 <= index <= 2
        self.values[index] = value
        self.value_types[index] = type_

    def copy(self) -> "PosOffset":
        res = PosOffset(self.compiler)
        res.values = self.values.copy()
        res.value_types = self.value_types.copy()
        return res
