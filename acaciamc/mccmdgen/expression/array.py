"""Compile-time only array."""

__all__ = ["ArrayType", "Array"]

from typing import List

from .base import *
from .types import DataType, Type
from acaciamc.tools import axe, method_of
from acaciamc.error import *

class ArrayType(Type):
    name = "array"

class Array(AcaciaExpr, ImmutableMixin):
    def __init__(self, items: List[AcaciaExpr], compiler):
        super().__init__(DataType.from_type_cls(ArrayType, compiler), compiler)
        self.items = items
        self.length = len(items)
        def _validate_index(self: Array, index: int):
            if not -self.length <= index < self.length:
                raise Error(ErrorType.ARRAY_INDEX_OUT_OF_BOUNDS,
                            length=self.length, index=index)
        @method_of(self, "get")
        @axe.chop
        @axe.arg("index", axe.LiteralInt())
        def _get(compiler, index: int):
            _validate_index(self, index)
            return self.items[index]
        @method_of(self, "set")
        @axe.chop
        @axe.arg("index", axe.LiteralInt())
        @axe.arg("value", axe.AnyValue())
        @transform_immutable(self)
        def _set(self: Array, compiler, index: int, value: AcaciaExpr):
            _validate_index(self, index)
            self.items[index] = value
            return self
        @method_of(self, "extend")
        @axe.chop
        @axe.arg("value", axe.Iterator())
        @axe.slash
        @transform_immutable(self)
        def _extend(self: Array, compiler, value: ITERLIST_T):
            self.items.extend(value)
            return self
        @method_of(self, "append")
        @axe.chop
        @axe.arg("value", axe.AnyValue())
        @axe.slash
        @transform_immutable(self)
        def _append(self: Array, compiler, value: AcaciaExpr):
            self.items.append(value)
            return self
        @method_of(self, "insert")
        @axe.chop
        @axe.arg("index", axe.LiteralInt())
        @axe.arg("value", axe.AnyValue())
        @axe.slash
        @transform_immutable(self)
        def _insert(self: Array, compiler, index: int, value: AcaciaExpr):
            _validate_index(self, index)
            self.items.insert(index, value)
            return self
        @method_of(self, "reverse")
        @axe.chop
        @transform_immutable(self)
        def _reverse(self: Array, compiler):
            self.items.reverse()
            return self
        @method_of(self, "pop")
        @axe.chop
        @axe.arg("index", axe.LiteralInt())
        @transform_immutable(self)
        def _pop(self: Array, compiler, index: int):
            self.items.pop(index)
            return self

    def copy(self) -> "Array":
        return Array(self.items.copy(), self.compiler)

    def iterate(self) -> ITERLIST_T:
        return self.items
