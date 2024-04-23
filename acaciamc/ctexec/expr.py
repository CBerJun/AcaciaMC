__all__ = ['CTObj', 'CTDataType', 'CTObjPtr', 'CTCallable', 'CTExpr']

from typing import (
    TYPE_CHECKING, Union, List, Dict, Hashable, Iterable, Optional
)
from abc import ABCMeta, abstractmethod

from acaciamc.mccmdgen.symbol import SymbolTable
from acaciamc.error import traced_call

if TYPE_CHECKING:
    from acaciamc.ast import Operator
    from acaciamc.error import SourceLocation
    from acaciamc.mccmdgen.expression.base import ConstExpr

class CTDataType:
    def __init__(self, name: str, bases: Iterable["CTDataType"] = ()):
        self.name = name
        self.bases = tuple(bases)

    def is_typeof(self, other: "CTExpr") -> bool:
        return self.is_baseof(abs(other).cdata_type)

    def is_baseof(self, other: "CTDataType") -> bool:
        if self is other:
            return True
        for base in other.bases:
            if self.is_baseof(base):
                return True
        return False

class CTObj:
    cdata_type: CTDataType

    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)
        self.attributes = SymbolTable()

    def __abs__(self):
        return self

    def to_rt(self) -> "ConstExpr":
        raise TypeError

    def cadd(self, other: "CTObj") -> "CTExpr":
        raise TypeError
    def csub(self, other: "CTObj") -> "CTExpr":
        raise TypeError
    def cmul(self, other: "CTObj") -> "CTExpr":
        raise TypeError
    def cdiv(self, other: "CTObj") -> "CTExpr":
        raise TypeError
    def cmod(self, other: "CTObj") -> "CTExpr":
        raise TypeError

    def cradd(self, other: "CTObj") -> "CTExpr":
        raise TypeError
    def crsub(self, other: "CTObj") -> "CTExpr":
        raise TypeError
    def crmul(self, other: "CTObj") -> "CTExpr":
        raise TypeError
    def crdiv(self, other: "CTObj") -> "CTExpr":
        raise TypeError
    def crmod(self, other: "CTObj") -> "CTExpr":
        raise TypeError

    def cunarypos(self) -> "CTExpr":
        raise TypeError
    def cunaryneg(self) -> "CTExpr":
        raise TypeError
    def cunarynot(self) -> "CTExpr":
        raise TypeError

    def ccompare(self, op: "Operator", other: "CTObj") -> bool:
        raise TypeError

    def cdatatype_hook(self) -> CTDataType:
        raise TypeError

    def cstringify(self) -> str:
        raise TypeError

    def citerate(self) -> List["CTExpr"]:
        raise TypeError

    def chash(self) -> Hashable:
        raise NotImplementedError

class CTObjPtr:
    def __init__(self, value: CTObj):
        self.set(value)

    def __abs__(self):
        return self.v

    def set(self, value: CTObj):
        self.v = value

CTExpr = Union[CTObj, CTObjPtr]

class CTCallable(CTObj, metaclass=ABCMeta):
    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)
        self.source: Optional["SourceLocation"] = None
        self.func_repr = "<unknown>"

    @abstractmethod
    def ccall(self, args: List["CTObj"], kwds: Dict[str, "CTObj"]) -> CTExpr:
        pass

    def ccall_withframe(self, args: List["CTObj"], kwds: Dict[str, "CTObj"],
                        location: Optional["SourceLocation"] = None) -> CTExpr:
        return traced_call(
            self.ccall, location, self.source, self.func_repr,
            args, kwds
        )
