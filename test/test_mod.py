"""
Test module for `acaciamc.tools`.
See "test/module.aca".
"""

from acaciamc.tools import axe, resultlib
from acaciamc.mccmdgen.expression import *

@axe.chop
@axe.arg("x", IntType, "y")
@axe.slash
@axe.arg("g", lambda compiler: axe.Typed(
    DataType.from_entity(compiler.base_template, compiler))
)
@axe.arg("y", axe.Typed(StringType), "x", default=None)
@axe.star
@axe.arg("z", axe.Nullable(axe.LiteralString()), default="aa")
@axe.kwds("k", axe.AnyOf(axe.LiteralInt(), axe.LiteralString()))
def _foo(compiler, **kwds):
    print("foo called:", kwds)
    return resultlib.commands([], compiler)

class _bar(metaclass=axe.OverloadChopped):
    @axe.overload
    @axe.arg("x", IntType)
    @axe.arg("y", axe.LiteralInt())
    def a(cls, compiler, **kwds):
        print("bar.a called:", kwds)
        return resultlib.commands([], compiler)

    @axe.overload
    @axe.arg("x", IntType)
    def b(cls, compiler, **kwds):
        print("bar.b called")
        return cls.a(compiler, y=1, **kwds)

class _extbar(_bar):
    @axe.overload
    def c(cls, compiler, **kwds):
        print("extbar.c called")
        return cls.b(compiler, x=IntLiteral(30, compiler), **kwds)

def acacia_build(compiler):
    return {"foo": BinaryFunction(_foo, compiler),
            "bar": BinaryFunction(_bar, compiler),
            "extbar": BinaryFunction(_extbar, compiler)}
