"""Acacia tools for creating binary modules."""

__all__ = ["method_of", "cfunction", "cmethod_of"]

from typing import Callable as _Callable, Union as _Union

# `import acaciamc.mccmdgen.expression as _acacia` won't work in 3.6
# because of a Python bug (see https://bugs.python.org/issue23203)
from acaciamc.mccmdgen import expression as _acacia
from acaciamc.ctexec import expr as _acaciact

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

def cmethod_of(expr: _Union[_acacia.AcaciaExpr, _acaciact.CTObj],
               name: str, compiler=None, runtime=True):
    if compiler is None:
        assert isinstance(expr, _acacia.AcaciaExpr)
        compiler = expr.compiler
    table1 = table2 = None
    if isinstance(expr, _acacia.AcaciaExpr):
        table1 = expr.attribute_table
    if isinstance(expr, _acaciact.CTObj):
        table2 = expr.attributes
    def _decorator(func):
        if runtime:
            obj = _acacia.BinaryCTFunction(func, compiler)
        else:
            obj = _acacia.BinaryCTOnlyFunction(func, compiler)
        if table1:
            table1.set(name, obj)
        if table2:
            table2.set(name, obj)
        return func
    return _decorator
