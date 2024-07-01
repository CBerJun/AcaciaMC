"""
Test module for `acaciamc.tools`.
See "test/module.aca".
"""

from acaciamc.objects import *


@axe.chop
@axe.arg("x", IntDataType, "y")
@axe.slash
@axe.arg("g", EGroupDataType, axe.POSITIONAL)
@axe.arg("y", axe.Typed(StringDataType), "x", default=None)
@axe.star
@axe.arg("z", axe.Nullable(axe.LiteralString()), default="aa")
@axe.kwds("k", axe.AnyOf(axe.LiteralInt(), axe.LiteralString()))
def _foo(compiler, positional_group, **kwds):
    print(f"foo called with {kwds!r} and entity group {positional_group!r}")


class _bar(metaclass=axe.OverloadChopped):
    @axe.overload
    @axe.arg("x", IntDataType)
    @axe.arg("y", axe.LiteralInt())
    def a(cls, compiler, **kwds):
        print("bar.a called:", kwds)

    @axe.overload
    @axe.arg("x", IntDataType)
    def b(cls, compiler, **kwds):
        print("bar.b called")
        return cls.a(compiler, y=1, **kwds)


class _extbar(_bar):
    @axe.overload
    def c(cls, compiler, **kwds):
        print("extbar.c called")
        return cls.b(compiler, x=IntLiteral(30), **kwds)


def acacia_build(compiler):
    return {
        "foo": BinaryFunction(_foo),
        "bar": BinaryFunction(_bar),
        "extbar": BinaryFunction(_extbar)
    }
