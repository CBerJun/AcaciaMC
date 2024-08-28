__all__ = ['CTObj', 'CTDataType', 'CTObjPtr', 'CTCallable', 'CTExpr']

from abc import ABCMeta, abstractmethod
from typing import (
    TYPE_CHECKING, Union, List, Dict, Hashable, Iterable, Optional
)

from acaciamc.error import traced_call
from acaciamc.localization import localize
from acaciamc.mccmdgen.symbol import SymbolTable
from acaciamc.mccmdgen.utils import InvalidOpError

if TYPE_CHECKING:
    from acaciamc.ast import Operator
    from acaciamc.error import SourceLocation
    from acaciamc.compiler import Compiler
    from acaciamc.mccmdgen.expr import ConstExpr


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
        raise InvalidOpError

    def cimplicitcast(self, type_: "CTDataType") -> "CTExpr":
        raise InvalidOpError

    def cadd(self, other: "CTObj") -> "CTExpr":
        raise InvalidOpError

    def csub(self, other: "CTObj") -> "CTExpr":
        raise InvalidOpError

    def cmul(self, other: "CTObj") -> "CTExpr":
        raise InvalidOpError

    def cdiv(self, other: "CTObj") -> "CTExpr":
        raise InvalidOpError

    def cmod(self, other: "CTObj") -> "CTExpr":
        raise InvalidOpError

    def cradd(self, other: "CTObj") -> "CTExpr":
        raise InvalidOpError

    def crsub(self, other: "CTObj") -> "CTExpr":
        raise InvalidOpError

    def crmul(self, other: "CTObj") -> "CTExpr":
        raise InvalidOpError

    def crdiv(self, other: "CTObj") -> "CTExpr":
        raise InvalidOpError

    def crmod(self, other: "CTObj") -> "CTExpr":
        raise InvalidOpError

    def cunarypos(self) -> "CTExpr":
        raise InvalidOpError

    def cunaryneg(self) -> "CTExpr":
        raise InvalidOpError

    def cunarynot(self) -> "CTExpr":
        raise InvalidOpError

    def ccompare(self, op: "Operator", other: "CTObj") -> bool:
        raise InvalidOpError

    def cdatatype_hook(self) -> CTDataType:
        raise InvalidOpError

    def cstringify(self) -> str:
        raise InvalidOpError

    def citerate(self) -> List["CTExpr"]:
        raise InvalidOpError

    def chash(self) -> Hashable:
        raise InvalidOpError


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
        self.func_repr = localize("objects.function.unknown")

    @abstractmethod
    def ccall(self, args: List["CTObj"], kwds: Dict[str, "CTObj"],
              compiler: "Compiler") -> CTExpr:
        pass

    def ccall_withframe(
            self, args: List["CTObj"], kwds: Dict[str, "CTObj"],
            compiler, location: Optional["SourceLocation"] = None
    ) -> CTExpr:
        return traced_call(
            self.ccall, location, self.source, self.func_repr,
            args, kwds, compiler
        )
