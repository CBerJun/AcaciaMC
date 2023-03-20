# Classes about SymbolTable in Acacia

__all__ = ['SymbolTable', 'ScopedSymbolTable', 'AttributeTable']

class SymbolTable:
    # A SymbolTable knows the relationship between an identifier in
    # Acacia and its value (AcaciaExpr)
    def __init__(self):
        # _table:dict{str:AcaciaExpr} store the symbol relationship
        self._table = {}
    
    def __iter__(self):
        return iter(self._table.items())
    
    def set(self, name: str, value):
        # Change value at `name` to `value`
        # if name does not exists, create it
        self._table[name] = value
    
    def lookup(self, name: str):
        # lookup a name; if not found, return None
        return self._table.get(name)

class ScopedSymbolTable(SymbolTable):
    # A ScopedSymbolTable is created for a new scope
    # (e.g. function definition, etc.)
    # it has an outer scope (which is also a ScopedSymbolTable)
    # where we would find symbol when we are not able to find
    # it in self
    def __init__(self, outer: SymbolTable = None,
                 builtins: SymbolTable = None):
        super().__init__()
        assert isinstance(outer, ScopedSymbolTable) or outer is None
        self.outer = outer
        self.builtins = builtins
    
    def __iter__(self):
        def _iterator():
            yield from super()
            if self.outer:
                yield from self.outer
        return _iterator()
    
    def lookup(self, name: str, use_builtins=True):
        res = super().lookup(name)
        if res is not None:
            return res
        if use_builtins and self.builtins:
            res = self.builtins.lookup(name)
            if res is not None:
                return res
        if self.outer:
            return self.outer.lookup(name, use_builtins=False)

class AttributeTable(SymbolTable):
    # An AttributeTable is created for an object to store its attributes
    @classmethod
    def from_other(cls, table: SymbolTable):
        # convert other SymbolTable to AttributeTable
        if isinstance(table, cls):
            return table
        res = cls()
        res._table = table._table.copy()
        return res
