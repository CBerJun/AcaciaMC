# Classes about SymbolTable in Acacia

__all__ = ['SymbolTable', 'ScopedSymbolTable', 'AttributeTable']

class SymbolTable:
    # A SymbolTable knows the relationship between an identifier in
    # Acacia and its value (AcaciaExpr)
    def __init__(self):
        # _table:dict{str:AcaciaExpr} store the symbol relationship
        self._table = {}
    
    def create(self, name: str, value):
        # value:AcaciaExpr
        if name in self._table:
            raise ValueError('name "%s" already exists' % name)
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
    def __init__(self, outer: SymbolTable = None):
        super().__init__()
        self.outer = outer
    
    def lookup(self, name: str):
        res = super().lookup(name)
        if res is None and self.outer is not None:
            return self.outer.lookup(name)
        return res

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
