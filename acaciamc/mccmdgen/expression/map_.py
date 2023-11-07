"""Compile-time only mapping.
Only a few literal values are supported as keys.
"""

__all__ = ["MapType", "MapDataType", "Map"]

from typing import Dict, Hashable, Iterable
from itertools import repeat

from .base import *
from .types import Type
from .none import NoneLiteral
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
        @method_of(self, "delete")
        @axe.chop
        @axe.arg("key", axe.AnyValue())
        def _delete(compiler, key: AcaciaExpr):
            self.delete(key)
        @method_of(self, "copy")
        @axe.chop
        def _copy(compiler):
            res = Map([], [], self.compiler)
            res.dict = self.dict.copy()
            res.py_key2key = self.py_key2key.copy()
            return res

    def iterate(self) -> ITERLIST_T:
        return list(self.py_key2key.values())

    @axe.chop_getitem
    @axe.arg("key", axe.AnyValue())
    def getitem(self, key: AcaciaExpr) -> AcaciaExpr:
        return self.get(key)

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

    def get(self, key: AcaciaExpr) -> AcaciaExpr:
        py_key = self._get_key(key)
        if py_key in self.dict:
            return self.dict[py_key]
        raise Error(ErrorType.MAP_KEY_NOT_FOUND)

    def delete(self, key: AcaciaExpr):
        py_key = self._get_key(key)
        if py_key in self.dict:
            del self.dict[py_key]
            del self.py_key2key[py_key]
        else:
            raise Error(ErrorType.MAP_KEY_NOT_FOUND)
