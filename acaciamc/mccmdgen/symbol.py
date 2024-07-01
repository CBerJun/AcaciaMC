"""Acacia symbol table."""

__all__ = ['CTRTConversionError', 'SymbolTable']

from typing import TYPE_CHECKING, Optional, Dict, Set, Union, Iterable

from acaciamc.mccmdgen import expr
from acaciamc.mccmdgen.utils import InvalidOpError

if TYPE_CHECKING:
    from acaciamc.mccmdgen.ctexpr import CTExpr
    from acaciamc.mccmdgen.expr import AcaciaExpr


class CTRTConversionError(Exception):
    def __init__(self, obj: Union["AcaciaExpr", "CTExpr"]):
        super().__init__(obj)
        self.expr = obj


class SymbolTable:
    def __init__(self, outer: Optional["SymbolTable"] = None,
                 builtins: Optional["SymbolTable"] = None):
        """
        Create a new empty symbol table.
        `outer` is looked up if a name is not found in this table.
        `builtins` is looked up finally if a name is not found in this
        table and all the outer ones. It is expected that `builtins` is
        the same for all instances of `SymbolTable`.
        """
        self.outer = outer
        self.builtins = builtins
        self.no_export: Set[str] = set()
        self._table: Dict[str, Union["AcaciaExpr", "CTExpr"]] = {}

    def set(self, name: str, value: Union["AcaciaExpr", "CTExpr"]):
        """Change value at `name` to `value`.
        If name does not exists, create it."""
        self._table[name] = value

    def delete(self, name: str):
        """Delete `name`."""
        del self._table[name]

    def update(self, d: Dict[str, Union["AcaciaExpr", "CTExpr"]]):
        """Update symbol table with `d`."""
        self._table.update(d)

    def lookup(self, name: str, use_builtins=True, use_outer=True):
        """Look up a name; if not found, return None."""
        if name in self._table:
            res = self._table[name]
            if isinstance(res, expr.AcaciaExpr):
                return res
            try:
                return abs(res).to_rt()
            except InvalidOpError:
                raise CTRTConversionError(abs(res))
        if use_outer and self.outer:
            res = self.outer.lookup(name, use_builtins=False)
            if res is not None:
                return res
        if use_builtins and self.builtins:
            res = self.builtins.lookup(name)
            if res is not None:
                return res
        return None

    def clookup(self, name: str, use_builtins=True, use_outer=True):
        if name in self._table:
            res = self._table[name]
            if isinstance(res, expr.ConstExpr):
                return res.to_ctexpr()
            elif isinstance(res, expr.AcaciaExpr):
                raise CTRTConversionError(res)
            return res
        if use_outer and self.outer:
            res = self.outer.clookup(name, use_builtins=False)
            if res is not None:
                return res
        if use_builtins and self.builtins:
            res = self.builtins.clookup(name)
            if res is not None:
                return res
        return None

    def all_names(self) -> Iterable[str]:
        return self._table.keys()

    def get_raw(self, name: str) -> Optional[Union["AcaciaExpr", "CTExpr"]]:
        return self._table.get(name)
