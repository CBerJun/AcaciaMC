"""Generic in Acacia."""

__all__ = ["GenericDataType", "BinaryGeneric"]

from acaciamc.mccmdgen.datatype import DefaultDataType
from .base import *

class GenericDataType(DefaultDataType):
    name = 'generic'

class BinaryGeneric(ConstExpr):
    def __init__(self, compiler):
        super().__init__(GenericDataType(compiler), compiler)
