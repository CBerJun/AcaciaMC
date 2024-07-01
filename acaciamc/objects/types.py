"""Values of "type" type in Acacia.
e.g. "int" is a "type".
"""

__all__ = ['TypeDataType', 'Type']

from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from acaciamc.error import *
from acaciamc.mccmdgen.ctexpr import CTDataType, CTCallable
from acaciamc.mccmdgen.datatype import DefaultDataType
from acaciamc.mccmdgen.expr import *

if TYPE_CHECKING:
    from acaciamc.mccmdgen.datatype import DataType


class TypeDataType(DefaultDataType):
    name = "type"


ctdt_type = CTDataType("type")


class Type(ConstExprCombined, AcaciaCallable, CTCallable, metaclass=ABCMeta):
    """Base class for type of a variable that represents a type.
    (e.g. type of builtin "int" is `IntType`).
    """
    cdata_type = ctdt_type

    def __init__(self):
        super().__init__(TypeDataType())
        self.func_repr = str(self.datatype_hook())
        self.do_init()

    def do_init(self):
        """Initialzer for `Type`s. This exists due to historical reason."""
        pass

    def call(self, args, keywords, compiler):
        """
        Calling a type is to create an instance of this type,
        i.e. calling `__new__`.
        """
        new = self.attribute_table.lookup('__new__')
        if new is None or not isinstance(new, AcaciaCallable):
            raise Error(ErrorType.CANT_CREATE_INSTANCE,
                        type_=str(self.datatype_hook()))
        return new.call(args, keywords, compiler)

    def ccall(self, args, keywords, compiler):
        new = self.attributes.clookup('__new__')
        if new is None or not isinstance(new, CTCallable):
            raise Error(ErrorType.CANT_CREATE_INSTANCE,
                        type_=self.cdatatype_hook().name)
        return new.ccall(args, keywords, compiler)

    @abstractmethod
    def datatype_hook(self) -> "DataType":
        pass

    @abstractmethod
    def cdatatype_hook(self) -> "CTDataType":
        pass
