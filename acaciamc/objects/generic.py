"""Generic in Acacia."""

__all__ = ["GenericDataType", "BinaryGeneric"]

from acaciamc.mccmdgen.ctexpr import CTDataType
from acaciamc.mccmdgen.datatype import DefaultDataType
from acaciamc.mccmdgen.expr import *


class GenericDataType(DefaultDataType):
    name = 'generic'


ctdt_generic = CTDataType("generic")


class BinaryGeneric(ConstExprCombined):
    cdata_type = ctdt_generic

    def __init__(self):
        super().__init__(GenericDataType())
