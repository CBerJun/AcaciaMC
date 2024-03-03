"""Acacia symbol table."""

from typing import Optional, Dict, Any, Set, Iterator, Tuple

__all__ = ['SymbolTable', 'ScopedSymbolTable', 'AttributeTable']

class SymbolTable:
    """A SymbolTable knows the relationship between an identifier in
    Acacia and its value (`AcaciaExpr`).
    """
    def __init__(self):
        self._table = {}
        self.ct_assignable = []

    def __iter__(self) -> Iterator[Tuple[str, Any]]:
        return iter(self._table.items())

    def set(self, name: str, value):
        """Change value at `name` to `value`.
        If name does not exists, create it."""
        self._table[name] = value

    def delete(self, name: str):
        """Delete `name`."""
        del self._table[name]

    def update(self, d: Dict[str, Any]):
        """Update symbol table with `d`."""
        self._table.update(d)

    def lookup(self, name: str):
        """Look up a name; if not found, return None."""
        return self._table.get(name)

    def is_defined(self, name: str):
        """Return whether the name is defined in this table."""
        return name in self._table

    @classmethod
    def from_other(cls, table: "SymbolTable"):
        """Construct from another `SymbolTable`."""
        res = cls()
        res._table = table._table.copy()
        res.ct_assignable = table.ct_assignable.copy()
        return res

class ScopedSymbolTable(SymbolTable):
    """A `ScopedSymbolTable` is created for a new scope.
    (e.g. function definition, etc.)
    It has an outer scope (which is also a `ScopedSymbolTable`)
    where we would find symbol when we are not able to find
    it in `self`.
    """
    def __init__(self, outer: Optional[SymbolTable] = None,
                 builtins: Optional[SymbolTable] = None):
        super().__init__()
        assert isinstance(outer, ScopedSymbolTable) or outer is None
        self.outer = outer
        self.builtins = builtins
        self.no_export: Set[str] = set()

    def __iter__(self):
        yield from super().__iter__()
        if self.outer:
            yield from self.outer

    def lookup(self, name: str, use_builtins=True, use_outer=True):
        res = super().lookup(name)
        if res is not None:
            return res
        if use_builtins and self.builtins:
            res = self.builtins.lookup(name)
            if res is not None:
                return res
        if use_outer and self.outer:
            return self.outer.lookup(name, use_builtins=False)
        return None

class AttributeTable(SymbolTable):
    """An `AttributeTable` is created for an Acacia object to store
    its attributes.
    """
    pass
