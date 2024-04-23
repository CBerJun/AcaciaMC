"""Generic in Acacia."""

__all__ = ["GenericDataType", "BinaryGeneric"]

from acaciamc.mccmdgen.datatype import DefaultDataType
from acaciamc.ctexec.expr import CTDataType
from .base import *

class GenericDataType(DefaultDataType):
    name = 'generic'

ctdt_generic = CTDataType("generic")

class BinaryGeneric(ConstExprCombined):
    cdata_type = ctdt_generic

    def __init__(self, compiler):
        super().__init__(GenericDataType(compiler), compiler)
