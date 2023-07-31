"""
iterlib - Create iterable objects for a for-in structure.

Purpose of this module and the for-in structure are both to generate
repetitive commands. Acacia's for-in is a "compile-time loop" that
instructs the compiler to generate commands for each iteration.
Therefore, many of the functions in this module only accepts literal
expressions that can be calculated in compile time.
"""

from typing import TYPE_CHECKING, List, Union
from itertools import chain, repeat

from acaciamc.mccmdgen.expression import *
from acaciamc.tools import axe

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler

class IterDummyType(Type):
    name = "IterDummy"

class IterDummy(AcaciaExpr):
    """Dummy expression. The only usage is to do iterations."""
    def __init__(self, pool: ITERLIST_T, compiler: "Compiler"):
        super().__init__(
            DataType.from_type_cls(IterDummyType, compiler), compiler
        )
        self.pool = pool

    def iterate(self) -> ITERLIST_T:
        return self.pool.copy()

class _range(metaclass=axe.OverloadChopped):
    @classmethod
    def _impl(cls, compiler, *args: int):
        pool = [IntLiteral(i, compiler) for i in range(*args)]
        return IterDummy(pool, compiler)

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

@axe.chop
@axe.arg("x", axe.Iterator())
@axe.slash
def _reversed(compiler, x: ITERLIST_T):
    """reversed(x, /) -> Reversed iterable."""
    x.reverse()
    return IterDummy(x, compiler)

@axe.chop
@axe.arg("object", axe.AnyValue(), rename="obj")
@axe.arg("times", axe.LiteralInt())
def _repeat(compiler, obj: AcaciaExpr, times: int):
    return IterDummy(list(repeat(obj, times)), compiler)

@axe.chop
@axe.arg("iter", axe.Iterator(), rename="iter_")
@axe.arg("times", axe.LiteralInt())
def _cycle(compiler, iter_: ITERLIST_T, times: int):
    return IterDummy(list(chain.from_iterable(repeat(iter_, times))), compiler)

@axe.chop
@axe.star_arg("items", axe.AnyValue())
def _enum(compiler, items: List[AcaciaExpr]):
    return IterDummy(items, compiler)

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
    return IterDummy(res, compiler)

@axe.chop
@axe.star_arg("iters", axe.Iterator())
def _chain(compiler, iters: List[ITERLIST_T]):
    return IterDummy(list(chain.from_iterable(iters)), compiler)

class _slice(metaclass=axe.OverloadChopped):
    @classmethod
    def _impl(cls, compiler, iter_: ITERLIST_T, *args: Union[int, None]):
        return IterDummy(iter_[slice(*args)], compiler)

    @axe.overload
    @axe.arg("iter", axe.Iterator(), rename="iter_")
    @axe.arg("stop", axe.LiteralInt())
    def stop_only(cls, compiler, iter_: ITERLIST_T, stop: int):
        return cls._impl(compiler, iter_, stop)

    @axe.overload
    @axe.arg("iter", axe.Iterator(), rename="iter_")
    @axe.arg("start", axe.Nullable(axe.LiteralInt()))
    @axe.arg("stop", axe.Nullable(axe.LiteralInt()))
    def start_stop(cls, compiler, iter_: ITERLIST_T, start, stop):
        return cls._impl(compiler, iter_, start, stop)

    @axe.overload
    @axe.arg("iter", axe.Iterator(), rename="iter_")
    @axe.arg("start", axe.Nullable(axe.LiteralInt()))
    @axe.arg("stop", axe.Nullable(axe.LiteralInt()))
    @axe.arg("step", axe.LiteralInt())
    def full(cls, compiler, iter_: ITERLIST_T, start, stop, step: int):
        return cls._impl(compiler, iter_, start, stop, step)

def acacia_build(compiler: "Compiler"):
    compiler.add_type(IterDummyType)
    return {
        "range": BinaryFunction(_range, compiler),
        "reversed": BinaryFunction(_reversed, compiler),
        "repeat": BinaryFunction(_repeat, compiler),
        "cycle": BinaryFunction(_cycle, compiler),
        "enum": BinaryFunction(_enum, compiler),
        "geometric": BinaryFunction(_geometric, compiler),
        "chain": BinaryFunction(_chain, compiler),
        "slice": BinaryFunction(_slice, compiler)
    }
