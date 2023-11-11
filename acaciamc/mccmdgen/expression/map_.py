"""Compile-time only mapping.
Only a few literal values are supported as keys.
"""

__all__ = ["MapType", "MapDataType", "Map"]

from typing import Dict, Hashable, Iterable, Optional
from itertools import repeat

from .base import *
from .types import Type
from .none import NoneLiteral
from .list_ import AcaciaList
from acaciamc.tools import axe, method_of
from acaciamc.error import *
from acaciamc.mccmdgen.datatype import DefaultDataType

class MapDataType(DefaultDataType):
    name = "map"

class MapType(Type):
    def do_init(self):
        @method_of(self, "__new__")
        @axe.chop
        @axe.arg("iter1", axe.Iterator())
        @axe.arg("iter2", axe.Iterator())
        def _new(compiler, iter1: ITERLIST_T, iter2: ITERLIST_T):
            return Map(iter1, iter2, compiler)
        @method_of(self, "from_keys")
        @axe.chop
        @axe.arg("x", axe.Iterator())
        @axe.slash
        @axe.arg("fill", axe.AnyValue(), default=NoneLiteral(self.compiler))
        def _from_keys(compiler, x: ITERLIST_T, fill: AcaciaExpr):
            return Map(x, repeat(fill), compiler)

    def datatype_hook(self):
        return MapDataType()

class Map(SupportsGetItem, SupportsSetItem):
    def __init__(self, keys: Iterable[AcaciaExpr],
                 values: Iterable[AcaciaExpr], compiler):
        super().__init__(MapDataType(), compiler)
        self.dict: Dict[Hashable, AcaciaExpr] = {}
        self.py_key2key: Dict[Hashable, AcaciaExpr] = {}
        for key, value in zip(keys, values):
            self.set(key, value)
        @method_of(self, "update")
        @axe.chop
        @axe.arg("other", MapDataType)
        def _update(compiler, other: Map):
            self.dict.update(other.dict)
            self.py_key2key.update(other.py_key2key)
        @method_of(self, "pop")
        @axe.chop
        @axe.arg("key", axe.AnyValue())
        @axe.arg("default", axe.AnyValue(), default=None)
        def _pop(compiler, key: AcaciaExpr, default: Optional[AcaciaExpr]):
            res = self.pop(key)
            if res is None:
                if default is None:
                    raise Error(ErrorType.MAP_KEY_NOT_FOUND)
                else:
                    res = default
            return res
        @method_of(self, "copy")
        @axe.chop
        def _copy(compiler):
            res = Map([], [], self.compiler)
            res.dict = self.dict.copy()
            res.py_key2key = self.py_key2key.copy()
            return res
        @method_of(self, "clear")
        @axe.chop
        def _clear(compiler):
            self.dict.clear()
            self.py_key2key.clear()
        @method_of(self, "keys")
        @axe.chop
        def _keys(compiler):
            return AcaciaList(self.iterate(), compiler)
        @method_of(self, "values")
        @axe.chop
        def _values(compiler):
            return AcaciaList(list(self.dict.values()), compiler)
        @method_of(self, "get")
        @axe.chop
        @axe.arg("key", axe.AnyValue())
        @axe.arg("default", axe.AnyValue(), default=NoneLiteral(self.compiler))
        def _get(compiler, key: AcaciaExpr, default: AcaciaExpr):
            res = self.get(key)
            if res is None:
                res = default
            return res
        @method_of(self, "set_default")
        @axe.chop
        @axe.arg("key", axe.AnyValue())
        @axe.arg("default", axe.AnyValue(), default=NoneLiteral(self.compiler))
        def _set_default(compiler, key: AcaciaExpr, default: AcaciaExpr):
            res = self.get(key)
            if res is None:
                self.set(key, default)
                res = default
            return res

    def iterate(self) -> ITERLIST_T:
        return list(self.py_key2key.values())

    @axe.chop_getitem
    @axe.arg("key", axe.AnyValue())
    def getitem(self, key: AcaciaExpr) -> AcaciaExpr:
        res = self.get(key)
        if res is None:
            raise Error(ErrorType.MAP_KEY_NOT_FOUND)
        return res

    @axe.chop_setitem(value_type=axe.AnyValue())
    @axe.arg("key", axe.AnyValue())
    def setitem(self, key: AcaciaExpr, value: AcaciaExpr):
        self.set(key, value)

    def _get_key(self, key: AcaciaExpr):
        try:
            hash_ = key.map_hash()
        except NotImplementedError:
            raise Error(ErrorType.INVALID_MAP_KEY)
        else:
            return (type(key), hash_)

    def set(self, key: AcaciaExpr, value: AcaciaExpr):
        py_key = self._get_key(key)
        self.dict[py_key] = value
        self.py_key2key[py_key] = key

    def get(self, key: AcaciaExpr) -> Optional[AcaciaExpr]:
        py_key = self._get_key(key)
        if py_key in self.dict:
            return self.dict[py_key]
        return None

    def pop(self, key: AcaciaExpr) -> Optional[AcaciaExpr]:
        py_key = self._get_key(key)
        if py_key in self.dict:
            del self.py_key2key[py_key]
        return self.dict.pop(py_key, None)
