"""Builtin support for rotations.
NOTE When generating /execute context for rotations, we do NOT
overwrite executing position, so "facing <position>" is not
implemented. Workaround: summon an entity and teleport it to
facing position. Then use "Rot.face_entity".
"""

__all__ = ["Rotation"]

from typing import List
from functools import partialmethod

from .base import *
from .types import DataType, RotType, FloatType, NoneType, IntType
from .float_ import Float
from .callable import BinaryFunction
from .none import NoneLiteral
from .integer import IntLiteral

class Rotation(AcaciaExpr):
    def __init__(self, compiler):
        super().__init__(DataType.from_type_cls(RotType, compiler), compiler)
        self.context: List[str] = []
        self.attribute_table.set(
            "abs", BinaryFunction(self._abs, self.compiler))
        self.attribute_table.set(
            "offset", BinaryFunction(self._offset, self.compiler))

    def _setter(self, func: BinaryFunction, type_prefix: str):
        args_vh: List[AcaciaExpr] = []
        for name in ("vertical", "horizontal"):
            arg = func.arg_optional(
                name, NoneLiteral(self.compiler),
                (FloatType, NoneType, IntType)
            )
            if arg.data_type.raw_matches(IntType):
                if not isinstance(arg, IntLiteral):
                    func.arg_error(name, "integer must be literal")
                arg = Float.from_int(arg)
            args_vh.append(arg)
        func.assert_no_arg()
        vh: List[str] = []
        for arg in args_vh:
            if arg.data_type.raw_matches(NoneType):
                vh.append("~")
            else:
                vh.append(type_prefix + str(arg))
        self.context.append("rotated " + " ".join(vh))
        return self

    _abs = partialmethod(_setter, type_prefix="")
    _offset = partialmethod(_setter, type_prefix="~")
    """.abs(vertical, horizontal) .offset(vertical, horizontal)
    "vertical" & "horizontal" are either "None" or int literal or
    float, representing xrot and yrot values. "abs" directly sets
    rotation and "offset" rotates relatively.
    """
