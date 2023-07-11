"""Position offset.
Builtin type that represents a position, but without the context. (i.e
the /execute subcommands)
For instance, "~ ~5 ~" is a position offset, while
"~ ~5 ~ from xxx entity" is a position.
"""

__all__ = ["PosOffset", "CoordinateType"]

from typing import Set, List
from enum import Enum
from functools import partialmethod

from acaciamc.error import *
from .base import *
from .types import DataType, PosOffsetType, FloatType, NoneType, IntType
from .float_ import Float
from .callable import BinaryFunction
from .none import NoneLiteral
from .integer import IntLiteral

XYZ = ("x", "y", "z")

class CoordinateType(Enum):
    ABSOLUTE = ""
    RELATIVE = "~"
    LOCAL = "^"

class PosOffset(AcaciaExpr):
    def __init__(self, compiler):
        super().__init__(DataType.from_type_cls(PosOffsetType, compiler),
                         compiler)
        self.values: List[float] = [0.0, 0.0, 0.0]
        self.value_types: List[CoordinateType] = \
            [CoordinateType.RELATIVE for _ in range(3)]
        self.already_set: Set[int] = set()
        self.attribute_table.set(
            "offset", BinaryFunction(self._offset, self.compiler))
        self.attribute_table.set(
            "abs", BinaryFunction(self._abs, self.compiler))

    def __str__(self) -> str:
        return " ".join(
            type_.value + str(value)
            for type_, value in zip(self.value_types, self.values)
        )

    def _setter(self, func: BinaryFunction, offset_type: CoordinateType):
        args_xyz: List[AcaciaExpr] = []
        for name in XYZ:
            arg = func.arg_optional(
                name, NoneLiteral(self.compiler),
                (FloatType, NoneType, IntType)
            )
            if arg.data_type.raw_matches(IntType):
                if not isinstance(arg, IntLiteral):
                    func.arg_error(name, "integer must be literal")
                arg = Float.from_int(arg)
            args_xyz.append(arg)
        func.assert_no_arg()
        for i, arg in enumerate(args_xyz):
            if not arg.data_type.raw_matches(NoneType):
                if i in self.already_set:
                    raise Error(ErrorType.POS_OFFSET_ALREADY_SET, axis=XYZ[i])
                self.already_set.add(i)
                self.set(i, arg.value, offset_type)
        return self

    _abs = partialmethod(_setter, offset_type=CoordinateType.ABSOLUTE)
    _offset = partialmethod(_setter, offset_type=CoordinateType.RELATIVE)
    """.offset(x, y, z) .abs(x, y, z)
    "x", "y" and "z" are either "None" or int literal or float.
    "offset" sets given axes to use relative coordinate,
    while "abs" sets them to use absolute coordinate.
    """

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
