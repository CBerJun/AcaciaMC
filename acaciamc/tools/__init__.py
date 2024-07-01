"""Acacia tools for creating binary modules."""

__all__ = ["method_of", "cmethod_of", "ImmutableMixin", "transform_immutable"]

from typing import Callable as _Callable, Union as _Union

# `import acaciamc.objects as objects` won't work in 3.6
# because of a Python bug (see https://bugs.python.org/issue23203)
from acaciamc import objects
from acaciamc.mccmdgen import ctexpr, expr


def method_of(obj: "expr.AcaciaExpr", name: str):
    """Return a decorator that defines a method for `obj` with `name`
    whose implementation is decorated function.
    """

    def _decorator(func: _Callable):
        obj.attribute_table.set(name, objects.BinaryFunction(func))
        return func

    return _decorator


def cmethod_of(obj: _Union[expr.AcaciaExpr, ctexpr.CTObj],
               name: str, runtime=True):
    table1 = table2 = None
    if isinstance(obj, expr.AcaciaExpr):
        table1 = obj.attribute_table
    if isinstance(obj, ctexpr.CTObj):
        table2 = obj.attributes

    def _decorator(func):
        if runtime:
            obj = objects.BinaryCTFunction(func)
        else:
            obj = objects.BinaryCTOnlyFunction(func)
        if table1:
            table1.set(name, obj)
        if table2:
            table2.set(name, obj)
        return func

    return _decorator


class ImmutableMixin:
    """An `AcaciaExpr` that can't be changed and only allows
    transformations into another object of same type.
    """

    def copy(self) -> "ImmutableMixin":
        raise NotImplementedError


def transform_immutable(self: ImmutableMixin):
    """Return a decorator for binary function implementations that
    transforms an immutable expression to another one.
    """
    if not isinstance(self, ImmutableMixin):
        raise TypeError("can't transform non-ImmutableMixin")

    def _decorator(func: _Callable):
        def _decorated(*args, **kwds):
            return func(self.copy(), *args, **kwds)

        return _decorated

    return _decorator
