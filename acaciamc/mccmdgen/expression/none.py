# None definition for Acacia
from .base import *
from .types import BuiltinNoneType

__all__ = ['NoneVar', 'NoneCallResult', 'NoneLiteral', 'result_none']

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

def result_none(dependencies: list, compiler):
    # We define `NoneVar` to align to other `VarValue`s like `IntVar`,
    # so this factory is only used as an API for modules
    return NoneCallResult(dependencies, NoneVar(compiler), compiler)

# Used only by `None` keyword
class NoneLiteral(AcaciaExpr):
    # Represents a literal None
    def __init__(self, compiler):
        super().__init__(compiler.types[BuiltinNoneType], compiler)
    
    def export(self, var):
        return []
