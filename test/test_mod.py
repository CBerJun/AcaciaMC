"""
Test module for `acaciamc.tools`.
See "test/module.aca".
"""

from typing import TYPE_CHECKING
from acaciamc.tools import axe, resultlib
from acaciamc.objects import *

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler

def _build_foo(compiler: "Compiler"):
    @axe.chop
    @axe.arg("x", IntDataType, "y")
    @axe.slash
    @axe.arg("g", EntityDataType)
    @axe.arg("y", axe.Typed(StringDataType), "x", default=None)
    @axe.star
    @axe.arg("z", axe.Nullable(axe.LiteralString()), default="aa")
    @axe.kwds("k", axe.AnyOf(axe.LiteralInt(), axe.LiteralString()))
    def _foo(compiler, **kwds):
        print("foo called:", kwds)
        return resultlib.commands([], compiler)
    return _foo

class _bar(metaclass=axe.OverloadChopped):
    @axe.overload
    @axe.arg("x", IntDataType)
    @axe.arg("y", axe.LiteralInt())
    def a(cls, compiler, **kwds):
        print("bar.a called:", kwds)
        return resultlib.commands([], compiler)

    @axe.overload
    @axe.arg("x", IntDataType)
    def b(cls, compiler, **kwds):
        print("bar.b called")
        return cls.a(compiler, y=1, **kwds)

class _extbar(_bar):
    @axe.overload
    def c(cls, compiler, **kwds):
        print("extbar.c called")
        return cls.b(compiler, x=IntLiteral(30, compiler), **kwds)

def acacia_build(compiler):
    return {"foo": BinaryFunction(_build_foo(compiler), compiler),
            "bar": BinaryFunction(_bar, compiler),
            "extbar": BinaryFunction(_extbar, compiler)}
