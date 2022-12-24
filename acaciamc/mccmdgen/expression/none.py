# None definition for Acacia
from .base import *
from .types import BuiltinNoneType

__all__ = ['NoneVar', 'NoneCallResult']

# None is used when function returns nothing
class NoneVar(VarValue):
    def __init__(self, compiler):
        super().__init__(compiler.types[BuiltinNoneType], compiler)
    
    def export(self, var):
        # This does nothing but won't raise NotImplementedError
        return []

class NoneCallResult(CallResult):
    def __init__(self, dependencies: list, result_var: NoneVar, compiler):
        super().__init__(
            dependencies, result_var,
            compiler.types[BuiltinNoneType], compiler
        )
