# None definition for Acacia
from .base import *
from .types import BuiltinNoneType

__all__ = ['NoneVar', 'NoneLiteral', 'result_cmds']

# None is used when function returns nothing
class NoneVar(VarValue):
    def __init__(self, compiler):
        super().__init__(compiler.types[BuiltinNoneType], compiler)
    
    def export(self, var):
        # This does nothing but won't raise NotImplementedError
        return []

def result_cmds(dependencies: list, compiler):
    # API for `BinaryFunction`s, used to return None and just run
    # some commands.
    return NoneVar(compiler), dependencies

# Used only by `None` keyword
class NoneLiteral(AcaciaExpr):
    # Represents a literal None
    def __init__(self, compiler):
        super().__init__(compiler.types[BuiltinNoneType], compiler)
    
    def export(self, var):
        return []
