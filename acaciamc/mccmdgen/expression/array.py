"""
Compile-time only array.

Purpose of array and the for-in structure are both to generate
repetitive commands. Acacia's for-in is a "compile-time loop" that
instructs the compiler to generate commands for each iteration.
Therefore, many of the functions about arrays only accepts literal
expressions that can be calculated in compile time.
"""

__all__ = ["ArrayType", "ArrayDataType", "Array"]

from typing import List, Union
from itertools import repeat, chain

from .base import *
from .types import Type
from .integer import IntDataType, IntLiteral
from acaciamc.tools import axe, method_of
from acaciamc.error import *
from acaciamc.mccmdgen.datatype import DefaultDataType

class ArrayDataType(DefaultDataType):
    name = "array"

class ArrayType(Type):
    def do_init(self):
        @method_of(self, "range")
        class _range(metaclass=axe.OverloadChopped):
            @classmethod
            def _impl(cls, compiler, *args: int):
                items = [IntLiteral(i, compiler) for i in range(*args)]
                return Array(items, compiler)

            @axe.overload
            @axe.arg("stop", axe.LiteralInt())
            def stop_only(cls, compiler, stop: int):
                return cls._impl(compiler, stop)

            @axe.overload
            @axe.arg("start", axe.LiteralInt())
            @axe.arg("stop", axe.LiteralInt())
            def start_stop(cls, compiler, start: int, stop: int):
                return cls._impl(compiler, start, stop)

            @axe.overload
            @axe.arg("start", axe.LiteralInt())
            @axe.arg("stop", axe.LiteralInt())
            @axe.arg("step", axe.LiteralInt())
            def full(cls, compiler, start: int, stop: int, step: int):
                return cls._impl(compiler, start, stop, step)
        @method_of(self, "__new__")
        @axe.chop
        @axe.arg("x", axe.Iterator())
        @axe.slash
        def _new(compiler, x: ITERLIST_T):
            return Array(x, compiler)
        @method_of(self, "repeat")
        @axe.chop
        @axe.arg("object", axe.AnyValue(), rename="obj")
        @axe.arg("times", axe.LiteralInt())
        def _repeat(compiler, obj: AcaciaExpr, times: int):
            return Array(list(repeat(obj, times)), compiler)
        @method_of(self, "geometric")
        @axe.chop
        @axe.arg("start", axe.LiteralInt())
        @axe.arg("ratio", axe.LiteralInt())
        @axe.arg("times", axe.LiteralInt())
        def _geometric(compiler, start: int, ratio: int, times: int):
            cur = start
            res = []
            for _ in range(times):
                res.append(IntLiteral(cur, compiler))
                cur *= ratio
            return Array(res, compiler)

    def datatype_hook(self):
        return ArrayDataType()

class Array(AcaciaExpr, ImmutableMixin):
    def __init__(self, items: List[AcaciaExpr], compiler):
        super().__init__(ArrayDataType(), compiler)
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
        @method_of(self, "chain")
        @axe.chop
        @axe.star_arg("value", axe.Iterator())
        @transform_immutable(self)
        def _chain(self: Array, compiler, value: List[ITERLIST_T]):
            self.items.extend(chain.from_iterable(value))
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
        @method_of(self, "slice")
        class _slice(metaclass=axe.OverloadChopped):
            @classmethod
            def _impl(cls, compiler, *args: Union[int, None]):
                return Array(self.items[slice(*args)], compiler)

            @axe.overload
            @axe.arg("stop", axe.LiteralInt())
            def stop_only(cls, compiler, stop: int):
                return cls._impl(compiler, stop)

            @axe.overload
            @axe.arg("start", axe.Nullable(axe.LiteralInt()))
            @axe.arg("stop", axe.Nullable(axe.LiteralInt()))
            def start_stop(cls, compiler, start, stop):
                return cls._impl(compiler, start, stop)

            @axe.overload
            @axe.arg("start", axe.Nullable(axe.LiteralInt()))
            @axe.arg("stop", axe.Nullable(axe.LiteralInt()))
            @axe.arg("step", axe.LiteralInt())
            def full(cls, compiler, start, stop, step: int):
                return cls._impl(compiler, start, stop, step)
        @method_of(self, "cycle")
        @axe.chop
        @axe.arg("times", axe.RangedLiteralInt(0, None))
        def _cycle(compiler, times: int):
            return Array(self.items * times, compiler)

    def copy(self) -> "Array":
        return Array(self.items.copy(), self.compiler)

    def iterate(self) -> ITERLIST_T:
        return self.items

    def map_hash(self):
        return tuple(x.map_hash() for x in self.items)

    def __add__(self, other):
        if isinstance(other, Array):
            return Array(self.items + other.items, self.compiler)
        return NotImplemented

    def __radd__(self, other):
        return self.__add__(other)

    def __mul__(self, other: AcaciaExpr):
        if isinstance(other, IntLiteral):
            return Array(self.items * other.value, self.compiler)
        if other.data_type.matches_cls(IntDataType):
            raise Error(ErrorType.ARRAY_MULTIMES_NON_LITERAL)
        return NotImplemented
