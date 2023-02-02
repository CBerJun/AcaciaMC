# None definition for Acacia
from .base import *
from .types import BuiltinNoneType

__all__ = ['None_']

# `None_` is a placeholder mainly used for binary functions.
# When a binary function does not give a result expression, but it really
# wants to write commands to file, `None_` accept these commands.
# Also, if a binary function allows the user to ommit some arguments,
# it can set `None_` to the default value of these args.

class None_(AcaciaExpr):
    def __init__(self, dependencies: list, compiler):
        super().__init__(compiler.types[BuiltinNoneType], compiler)
        self.dependencies = dependencies
    
    def export_novalue(self):
        return list(self.dependencies)
