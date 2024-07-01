"""
Compile-time only mapping objects.
Only a few literal values are supported as keys.
"""

__all__ = ["MapType", "MapDataType", "Map", "CTConstMap", "CTMap"]

from itertools import repeat
from typing import Dict, Hashable, Iterable, Optional, Tuple, List

from acaciamc.error import *
from acaciamc.mccmdgen.ctexpr import CTObj, CTDataType, CTObjPtr, CTExpr
from acaciamc.mccmdgen.datatype import DefaultDataType
from acaciamc.mccmdgen.expr import *
from acaciamc.mccmdgen.utils import InvalidOpError
from acaciamc.tools import axe, cmethod_of
from .boolean import BoolLiteral
from .integer import IntLiteral
from .list_ import AcaciaList, CTList, list2ct
from .none import NoneLiteral
from .types import Type


class MapDataType(DefaultDataType):
    name = "const_map"


ctdt_constmap = CTDataType("const_map")
ctdt_map = CTDataType("map", (ctdt_constmap,))


class MapType(Type):
    def do_init(self):
        @cmethod_of(self, "__new__")
        @axe.chop
        @axe.arg("iter1", axe.CTIterator())
        @axe.arg("iter2", axe.CTIterator())
        def _new(compiler, iter1: List[CTObj], iter2: List[CTObj]):
            return CTMap(iter1, iter2)

        @cmethod_of(self, "from_keys")
        @axe.chop
        @axe.arg("x", axe.CTIterator())
        @axe.slash
        @axe.arg("fill", axe.Constant(), default=NoneLiteral())
        def _from_keys(compiler, x: List[CTObj], fill: CTObj):
            return CTMap(x, repeat(fill))

    def datatype_hook(self):
        return MapDataType()

    def cdatatype_hook(self):
        return ctdt_constmap


class Map(ConstExpr):
    def __init__(self, keys: Iterable[ConstExpr],
                 values: Iterable[ConstExpr]):
        super().__init__(MapDataType())
        self.data: Dict[Hashable, Tuple[ConstExpr, ConstExpr]] = {}
        for key, value in zip(keys, values):
            self.set(key, value)

        @cmethod_of(self, "__getitem__")
        @axe.chop
        @axe.arg("key", axe.AnyValue())
        def _getitem(compiler, key: AcaciaExpr) -> ConstExpr:
            res = self.get(key)
            if res is None:
                raise Error(ErrorType.MAP_KEY_NOT_FOUND)
            return res

        @cmethod_of(self, "copy")
        @axe.chop
        def _copy(compiler):
            res = Map((), ())
            res.data = self.data.copy()
            return res

        @cmethod_of(self, "keys")
        @axe.chop
        def _keys(compiler):
            return AcaciaList(self.iterate())

        @cmethod_of(self, "values")
        @axe.chop
        def _values(compiler):
            return AcaciaList(self.values())

        @cmethod_of(self, "has")
        @axe.chop
        @axe.arg("key", axe.AnyValue())
        def _has(compiler, key: AcaciaExpr):
            return BoolLiteral(self._get_key(key) in self.data)

        @cmethod_of(self, "size")
        @axe.chop
        def _size(compiler):
            return IntLiteral(len(self.data))

        @cmethod_of(self, "get")
        @axe.chop
        @axe.arg("key", axe.AnyValue())
        @axe.arg("default", axe.AnyValue(), default=NoneLiteral())
        def _get(compiler, key: AcaciaExpr, default: AcaciaExpr):
            res = self.get(key)
            if res is None:
                res = default
            return res

    def iterate(self) -> List[ConstExpr]:
        return [k for k, _ in self.data.values()]

    def values(self) -> List[ConstExpr]:
        return [v for _, v in self.data.values()]

    def _get_key(self, key: AcaciaExpr):
        try:
            hash_ = key.hash()
        except InvalidOpError:
            raise Error(ErrorType.INVALID_MAP_KEY)
        else:
            return (type(key.data_type), hash_)

    def set(self, key: AcaciaExpr, value: ConstExpr):
        py_key = self._get_key(key)
        self.data[py_key] = (key, value)

    def get(self, key: AcaciaExpr) -> Optional[ConstExpr]:
        py_key = self._get_key(key)
        if py_key in self.data:
            _, v = self.data[py_key]
            return v
        return None

    def pop(self, key: AcaciaExpr) -> Optional[ConstExpr]:
        py_key = self._get_key(key)
        _, v = self.data.pop(py_key, (None, None))
        return v

    def items(self) -> Iterable[Tuple[ConstExpr, ConstExpr]]:
        return self.data.values()

    def to_ctexpr(self):
        return CTMap(list2ct(self.iterate()),
                     list2ct(self.values()))


class CTConstMap(CTObj):
    cdata_type = ctdt_constmap

    def __init__(self, keys: Iterable["CTExpr"],
                 values: Iterable["CTExpr"]):
        super().__init__()
        self.data: Dict[Hashable, Tuple[CTObj, CTObjPtr]] = {}
        for key, value in zip(keys, values):
            self.set(key, value)

        @cmethod_of(self, "__ct_getitem__")
        @axe.chop
        @axe.arg("key", axe.Constant())
        def _getitem(compiler, key: CTObj):
            res = self.get(key)
            if res is None:
                raise Error(ErrorType.MAP_KEY_NOT_FOUND)
            return abs(res)

        @cmethod_of(self, "copy")
        @axe.chop
        def _copy(compiler):
            return CTMap(self.citerate(), self.values())

        @cmethod_of(self, "keys")
        @axe.chop
        def _keys(compiler):
            return CTList(self.citerate())

        @cmethod_of(self, "values")
        @axe.chop
        def _values(compiler):
            return CTList(self.values())

        @cmethod_of(self, "get")
        @axe.chop
        @axe.arg("key", axe.Constant())
        @axe.arg("default", axe.Constant(), default=NoneLiteral())
        def _get(compiler, key: CTObj, default: CTObj):
            res = self.get(key)
            if res is None:
                res = default
            return abs(res)

        @cmethod_of(self, "has")
        @axe.chop
        @axe.arg("key", axe.Constant())
        def _has(compiler, key: CTObj):
            return BoolLiteral(self.get_key(key) in self.data)

        @cmethod_of(self, "size")
        @axe.chop
        def _size(compiler):
            return IntLiteral(len(self.data))

    def items(self) -> Iterable[Tuple[CTObj, CTObjPtr]]:
        return self.data.values()

    def citerate(self) -> List[CTObj]:
        return [k for k, _ in self.data.values()]

    def values(self) -> List["CTExpr"]:
        return [v for _, v in self.data.values()]

    @staticmethod
    def get_key(key: "CTExpr"):
        try:
            return abs(key).chash()
        except InvalidOpError:
            raise Error(ErrorType.INVALID_MAP_KEY)

    def set(self, key: "CTExpr", value: "CTExpr"):
        key = abs(key)
        value = abs(value)
        py_key = self.get_key(key)
        if py_key in self.data:
            _, ptr = self.data[py_key]
            ptr.set(value)
        else:
            self.data[py_key] = (key, CTObjPtr(value))

    def get(self, key: "CTExpr") -> Optional[CTObjPtr]:
        py_key = self.get_key(key)
        if py_key in self.data:
            _, ptr = self.data[py_key]
            return ptr
        return None

    def to_rt(self):
        return Map((k.to_rt() for k in self.citerate()),
                   (abs(v).to_rt() for v in self.values()))


class CTMap(CTConstMap):
    cdata_type = ctdt_map

    def __init__(self, keys: Iterable["CTExpr"],
                 values: Iterable["CTExpr"]):
        super().__init__(keys, values)

        @cmethod_of(self, "__ct_getitem__", runtime=False)
        @axe.chop
        @axe.arg("key", axe.Constant())
        def _getitem(compiler, key: "CTExpr"):
            res = self.get(key)
            if res is None:
                raise Error(ErrorType.MAP_KEY_NOT_FOUND)
            return res

        @cmethod_of(self, "update", runtime=False)
        @axe.chop
        @axe.arg("other", axe.MapOf(axe.Constant(), axe.Constant()))
        def _update(compiler, other: Dict[CTObj, CTObj]):
            for k, v in other.items():
                self.set(k, v)

        @cmethod_of(self, "pop", runtime=False)
        @axe.chop
        @axe.arg("key", axe.Constant())
        @axe.arg("default", axe.Constant(), default=None)
        def _pop(compiler, key: CTObj, default: Optional[CTObj]):
            res = self.pop(key)
            if res is None:
                if default is None:
                    raise Error(ErrorType.MAP_KEY_NOT_FOUND)
                else:
                    res = abs(default)
            return res

        @cmethod_of(self, "set_default", runtime=False)
        @axe.chop
        @axe.arg("key", axe.Constant())
        @axe.arg("default", axe.Constant(), default=NoneLiteral())
        def _set_default(compiler, key: CTObj, default: CTObj):
            res = self.get(key)
            if res is None:
                self.set(key, default)
                res = default
            return abs(res)

        @cmethod_of(self, "clear", runtime=False)
        @axe.chop
        def _clear(compiler):
            self.data.clear()

    def pop(self, key: "CTExpr") -> Optional[CTObj]:
        py_key = self.get_key(key)
        if py_key in self.data:
            _, ptr = self.data.pop(py_key)
            return abs(ptr)
        return None
