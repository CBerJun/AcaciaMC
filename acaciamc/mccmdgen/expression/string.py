# Strings of Acacia
from .base import *
from .types import StringType, DataType

__all__ = ['String']

class String(AcaciaExpr):
    def __init__(self, value: str, compiler):
        super().__init__(
            DataType.from_type_cls(StringType, compiler), compiler
        )
        self.value = value
    
    def __add__(self, other):
        # connect strings
        # other:String
        return String(
            value = self.value + other.value, compiler = self.compiler
        )
