"""
Compile-time only list container.

Purpose of list and the for-in structure are both to generate
repetitive commands. Acacia's for-in is a "compile-time loop" that
instructs the compiler to generate commands for each iteration.
Therefore, many of the functions about lists only accepts literal
expressions that can be calculated in compile time.
"""

__all__ = ["ListType", "ListDataType", "AcaciaList", "CTConstList", "CTList"]

from typing import TYPE_CHECKING, List, Union, Iterable
from itertools import repeat

from .types import Type
from .integer import IntDataType, IntLiteral
from acaciamc.tools import axe, cmethod_of
from acaciamc.error import *
from acaciamc.mccmdgen.expr import *
from acaciamc.mccmdgen.datatype import DefaultDataType
from acaciamc.mccmdgen.ctexpr import CTObj, CTObjPtr, CTDataType

if TYPE_CHECKING:
    from acaciamc.mccmdgen.ctexpr import CTExpr

class ListDataType(DefaultDataType):
    name = "const_list"

ctdt_constlist = CTDataType("const_list")
ctdt_list = CTDataType("list", (ctdt_constlist,))

class ListType(Type):
    def do_init(self):
        @cmethod_of(self, "range")
        class _range(metaclass=axe.OverloadChopped):
            @classmethod
            def _impl(cls, compiler, *args: int):
                items = [IntLiteral(i, compiler) for i in range(*args)]
                return AcaciaList(items, compiler)

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
        @cmethod_of(self, "__new__")
        @axe.chop
        @axe.arg("x", axe.Iterator())
        @axe.slash
        def _new(compiler, x: ITERLIST_T):
            return AcaciaList(x, compiler)
        @cmethod_of(self, "repeat")
        @axe.chop
        @axe.arg("object", axe.AnyValue(), rename="obj")
        @axe.arg("times", axe.LiteralInt())
        def _repeat(compiler, obj: AcaciaExpr, times: int):
            return AcaciaList(repeat(obj, times), compiler)
        @cmethod_of(self, "geometric")
        @axe.chop
        @axe.arg("start", axe.LiteralInt())
        @axe.arg("ratio", axe.LiteralInt())
        @axe.arg("length", axe.LiteralInt())
        def _geometric(compiler, start: int, ratio: int, length: int):
            cur = start
            res = []
            for _ in range(length):
                res.append(IntLiteral(cur, compiler))
                cur *= ratio
            return AcaciaList(res, compiler)

    def datatype_hook(self):
        return ListDataType(self.compiler)

    def cdatatype_hook(self):
        return ctdt_constlist

def list2ct(x: Iterable[ConstExpr]) -> List[CTObj]:
    return [i.to_ctexpr() for i in x]

class AcaciaList(ConstExpr):
    def __init__(self, items: Iterable[ConstExpr], compiler):
        super().__init__(ListDataType(compiler), compiler)
        self.items: List[ConstExpr] = list(items)

        @cmethod_of(self, "__getitem__")
        @axe.chop
        @axe.arg("index", axe.LiteralInt())
        def _getitem(compiler, index: int):
            self._validate_index(index)
            return self.items[index]
        @cmethod_of(self, "copy")
        @axe.chop
        def _copy(compiler):
            return AcaciaList(self.items, self.compiler)
        @cmethod_of(self, "slice")
        class _slice(metaclass=axe.OverloadChopped):
            @classmethod
            def _impl(cls, compiler, *args: Union[int, None]):
                return AcaciaList(self.items[slice(*args)], compiler)

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
        @cmethod_of(self, "cycle")
        @axe.chop
        @axe.arg("times", axe.RangedLiteralInt(0, None))
        def _cycle(compiler, times: int):
            return AcaciaList(self.items * times, compiler)
        @cmethod_of(self, "size")
        @axe.chop
        def _size(compiler):
            return IntLiteral(len(self.items), compiler)

    def _validate_index(self, index: int):
        length = len(self.items)
        if not -length <= index < length:
            raise Error(ErrorType.LIST_INDEX_OUT_OF_BOUNDS,
                        length=length, index=index)

    def iterate(self) -> ITERLIST_T:
        return self.items

    def hash(self):
        return tuple(x.hash() for x in self.items)

    def add(self, other):
        if isinstance(other, AcaciaList):
            return AcaciaList(self.items + other.items, self.compiler)
        raise TypeError

    def mul(self, other: AcaciaExpr):
        if isinstance(other, IntLiteral):
            return AcaciaList(self.items * other.value, self.compiler)
        if other.data_type.matches_cls(IntDataType):
            raise Error(ErrorType.LIST_MULTIMES_NON_LITERAL)
        raise TypeError

    def to_ctexpr(self):
        return CTConstList(list2ct(self.items), self.compiler)

class CTConstList(CTObj):
    cdata_type = ctdt_constlist

    def __init__(self, items: Iterable["CTExpr"], compiler):
        super().__init__()
        self.ptrs = list(map(self._new_element, items))
        self.compiler = compiler

        @cmethod_of(self, "__ct_getitem__", compiler)
        @axe.chop
        @axe.arg("index", axe.LiteralInt())
        def _getitem(compiler, index: int):
            self._validate_index(index)
            return abs(self.ptrs[index])
        @cmethod_of(self, "copy", compiler)
        @axe.chop
        def _copy(compiler):
            return CTList(self.ptrs, compiler)
        @cmethod_of(self, "slice", compiler)
        class _slice(metaclass=axe.OverloadChopped):
            @classmethod
            def _impl(cls, *args: Union[int, None]):
                return CTList(self.ptrs[slice(*args)], self.compiler)

            @axe.overload
            @axe.arg("stop", axe.LiteralInt())
            def stop_only(cls, compiler, stop: int):
                return cls._impl(stop)

            @axe.overload
            @axe.arg("start", axe.Nullable(axe.LiteralInt()))
            @axe.arg("stop", axe.Nullable(axe.LiteralInt()))
            def start_stop(cls, compiler, start, stop):
                return cls._impl(start, stop)

            @axe.overload
            @axe.arg("start", axe.Nullable(axe.LiteralInt()))
            @axe.arg("stop", axe.Nullable(axe.LiteralInt()))
            @axe.arg("step", axe.LiteralInt())
            def full(cls, compiler, start, stop, step: int):
                return cls._impl(start, stop, step)
        @cmethod_of(self, "cycle", compiler)
        @axe.chop
        @axe.arg("times", axe.RangedLiteralInt(0, None))
        def _cycle(compiler, times: int):
            return CTList(self.ptrs * times, compiler)
        @cmethod_of(self, "size", compiler)
        @axe.chop
        def _size(compiler):
            return IntLiteral(len(self.ptrs), compiler)

    def _new_element(self, element: "CTExpr") -> CTObjPtr:
        return CTObjPtr(abs(element))

    def _validate_index(self, index: int):
        length = len(self.ptrs)
        if not -length <= index < length:
            raise Error(ErrorType.LIST_INDEX_OUT_OF_BOUNDS,
                        length=length, index=index)

    def citerate(self):
        return self.ptrs

    def chash(self):
        return tuple(abs(x).chash() for x in self.ptrs)

    def to_rt(self):
        return AcaciaList([abs(x).to_rt() for x in self.ptrs], self.compiler)

class CTList(CTConstList):
    cdata_type = ctdt_list

    def __init__(self, items: Iterable["CTExpr"], compiler):
        super().__init__(items, compiler)

        # Methods that modify the list
        @cmethod_of(self, "__ct_getitem__", compiler, runtime=False)
        @axe.chop
        @axe.arg("index", axe.LiteralInt())
        def _getitem(compiler, index: int):
            self._validate_index(index)
            return self.ptrs[index]
        @cmethod_of(self, "extend", compiler, runtime=False)
        @axe.chop
        @axe.arg("values", axe.CTIterator())
        @axe.slash
        def _extend(compiler, values: List["CTExpr"]):
            self.ptrs.extend(map(self._new_element, values))
        @cmethod_of(self, "append", compiler, runtime=False)
        @axe.chop
        @axe.arg("value", axe.Constant())
        @axe.slash
        def _append(compiler, value: CTObj):
            self.ptrs.append(self._new_element(value))
        @cmethod_of(self, "insert", compiler, runtime=False)
        @axe.chop
        @axe.arg("index", axe.LiteralInt())
        @axe.arg("value", axe.Constant())
        @axe.slash
        def _insert(compiler, index: int, value: CTObj):
            self._validate_index(index)
            self.ptrs.insert(index, self._new_element(value))
        @cmethod_of(self, "reverse", compiler, runtime=False)
        @axe.chop
        def _reverse(compiler):
            self.ptrs.reverse()
        @cmethod_of(self, "pop", compiler, runtime=False)
        @axe.chop
        @axe.arg("index", axe.LiteralInt())
        def _pop(compiler, index: int):
            self._validate_index(index)
            return self.ptrs.pop(index)
