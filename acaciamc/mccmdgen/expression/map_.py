"""Compile-time only mapping.
Only a few literal values are supported as keys.
"""

__all__ = ["MapType", "MapDataType", "Map"]

from typing import Dict, Hashable, Iterable, Optional, Tuple
from itertools import repeat

from .base import *
from .types import Type
from .none import NoneLiteral
from .list_ import AcaciaList
from .boolean import BoolLiteral
from .integer import IntLiteral
from acaciamc.tools import axe, cmethod_of
from acaciamc.error import *
from acaciamc.mccmdgen.datatype import DefaultDataType

class MapDataType(DefaultDataType):
    name = "map"

class MapType(Type):
    def do_init(self):
        @cmethod_of(self, "__new__")
        @axe.chop
        @axe.arg("iter1", axe.Iterator())
        @axe.arg("iter2", axe.Iterator())
        def _new(compiler, iter1: ITERLIST_T, iter2: ITERLIST_T):
            return Map(iter1, iter2, compiler)
        @cmethod_of(self, "from_keys")
        @axe.chop
        @axe.arg("x", axe.Iterator())
        @axe.slash
        @axe.arg("fill", axe.AnyValue(), default=NoneLiteral(self.compiler))
        def _from_keys(compiler, x: ITERLIST_T, fill: AcaciaExpr):
            return Map(x, repeat(fill), compiler)

    def datatype_hook(self):
        return MapDataType(self.compiler)

class Map(ConstExpr):
    def __init__(self, keys: Iterable[ConstExpr],
                 values: Iterable[ConstExpr], compiler):
        super().__init__(MapDataType(compiler), compiler)
        self.data: Dict[Hashable, Tuple[ConstExpr, ConstExpr]] = {}
        for key, value in zip(keys, values):
            self.set(key, value)
        @cmethod_of(self, "__getitem__")
        @axe.chop
        @axe.arg("key", axe.AnyValue())
        def getitem(compiler, key: AcaciaExpr) -> ConstExpr:
            res = self.get(key)
            if res is None:
                raise Error(ErrorType.MAP_KEY_NOT_FOUND)
            return res
        @cmethod_of(self, "copy")
        @axe.chop
        def _copy(compiler):
            res = Map([], [], compiler)
            res.data = self.data.copy()
            return res
        @cmethod_of(self, "keys")
        @axe.chop
        def _keys(compiler):
            return AcaciaList(self.iterate(), compiler)
        @cmethod_of(self, "values")
        @axe.chop
        def _values(compiler):
            return AcaciaList([v for _, v in self.data.values()], compiler)
        @cmethod_of(self, "get")
        @axe.chop
        @axe.arg("key", axe.AnyValue())
        @axe.arg("default", axe.AnyValue(), default=NoneLiteral(self.compiler))
        def _get(compiler, key: AcaciaExpr, default: AcaciaExpr):
            res = self.get(key)
            if res is None:
                res = default
            return res
        @cmethod_of(self, "has")
        @axe.chop
        @axe.arg("key", axe.AnyValue())
        def _has(compiler, key: AcaciaExpr):
            return BoolLiteral(self._get_key(key) in self.data, compiler)
        @cmethod_of(self, "size")
        @axe.chop
        def _size(compiler):
            return IntLiteral(len(self.data), compiler)
        @cmethod_of(self, "update", runtime=False)
        @axe.chop
        @axe.arg("other", MapDataType)
        def _update(compiler, other: Map):
            self.data.update(other.data)
        @cmethod_of(self, "pop", runtime=False)
        @axe.chop
        @axe.arg("key", axe.AnyValue())
        @axe.arg("default", axe.AnyValue(), default=None)
        def _pop(compiler, key: ConstExpr, default: Optional[ConstExpr]):
            res = self.pop(key)
            if res is None:
                if default is None:
                    raise Error(ErrorType.MAP_KEY_NOT_FOUND)
                else:
                    res = default
            return res
        @cmethod_of(self, "set_default", runtime=False)
        @axe.chop
        @axe.arg("key", axe.AnyValue())
        @axe.arg("default", axe.AnyValue(), default=NoneLiteral(self.compiler))
        def _set_default(compiler, key: ConstExpr, default: ConstExpr):
            res = self.get(key)
            if res is None:
                self.set(key, default)
                res = default
            return res
        @cmethod_of(self, "clear", runtime=False)
        @axe.chop
        def _clear(compiler):
            self.data.clear()
        @cmethod_of(self, "__setitem__", runtime=False)
        @axe.chop
        @axe.arg("key", axe.AnyValue())
        @axe.arg("value", axe.AnyValue())
        def _setitem(compiler, key: ConstExpr, value: ConstExpr):
            self.set(key, value)

    def iterate(self) -> ITERLIST_T:
        return [k for k, _ in self.data.values()]

    def _get_key(self, key: AcaciaExpr):
        try:
            hash_ = key.map_hash()
        except NotImplementedError:
            raise Error(ErrorType.INVALID_MAP_KEY)
        else:
            return (type(key.data_type), hash_)

    def set(self, key: ConstExpr, value: ConstExpr):
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
