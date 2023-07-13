"""Builtin support for rotations.
NOTE When generating /execute context for rotations, we do NOT
overwrite executing position, so "facing <position>" is not
implemented. Workaround: summon an entity and teleport it to
facing position. Then use "Rot.face_entity".
"""

__all__ = ["Rotation"]

from typing import List

from acaciamc.tools import axe
from .base import *
from .types import DataType, RotType
from .callable import BinaryFunction

class Rotation(AcaciaExpr):
    def __init__(self, compiler):
        super().__init__(DataType.from_type_cls(RotType, compiler), compiler)
        self.context: List[str] = []

        _abs = self._create_setter("")
        _offset = self._create_setter("~")
        """.abs(vertical, horizontal) .offset(vertical, horizontal)
        "vertical" & "horizontal" are either "None" or int literal or
        float, representing xrot and yrot values. "abs" directly sets
        rotation and "offset" rotates relatively.
        """
        self.attribute_table.set("abs", BinaryFunction(_abs, self.compiler))
        self.attribute_table.set(
            "offset", BinaryFunction(_offset, self.compiler))

    def _create_setter(self, type_prefix: str):
        @axe.chop
        @axe.arg("vertical", axe.Nullable(axe.LiteralFloat()), default=None)
        @axe.arg("horizontal", axe.Nullable(axe.LiteralFloat()), default=None)
        def _setter(compiler, vertical, horizontal):
            vh: List[str] = []
            for arg in (vertical, horizontal):
                if arg is None:
                    vh.append("~")
                else:
                    vh.append(type_prefix + str(arg))
            self.context.append("rotated " + " ".join(vh))
            return self
        return _setter
