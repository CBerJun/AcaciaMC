"""Acacia tools for creating binary modules."""

__all__ = ["method_of", "cfunction", "cmethod_of"]

from typing import Callable as _Callable

# `import acaciamc.mccmdgen.expression as _acacia` won't work in 3.6
# because of a Python bug (see https://bugs.python.org/issue23203)
from acaciamc.mccmdgen import expression as _acacia

def method_of(expr: "_acacia.AcaciaExpr", name: str):
    """Return a decorator that defines a method for `expr` with `name`
    whose implementation is decorated function.
    """
    def _decorator(func: _Callable):
        expr.attribute_table.set(
            name, _acacia.BinaryFunction(func, expr.compiler)
        )
        return func
    return _decorator

def cfunction(func: _Callable, compiler, runtime=True):
    if runtime:
        return _acacia.BinaryMaybeCTFunction(func, func, compiler)
    return _acacia.BinaryCTFunction(func, compiler)

def cmethod_of(expr: "_acacia.AcaciaExpr", name: str, runtime=True):
    def _decorator(func: _Callable):
        expr.attribute_table.set(name, cfunction(func, expr.compiler, runtime))
        return func
    return _decorator
