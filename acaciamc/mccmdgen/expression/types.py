"""Values of "type" type in Acacia.
e.g. "int" is a "type".
"""

__all__ = ['TypeDataType', 'Type']

from typing import TYPE_CHECKING
from abc import ABCMeta, abstractmethod

from .base import *
from acaciamc.error import *
from acaciamc.mccmdgen.datatype import DefaultDataType
from acaciamc.ctexec.expr import CTDataType, CTCallable

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from acaciamc.mccmdgen.datatype import DataType

class TypeDataType(DefaultDataType):
    name = "type"

ctdt_type = CTDataType("type")

class Type(ConstExprCombined, AcaciaCallable, CTCallable, metaclass=ABCMeta):
    """Base class for type of a variable that represents a type.
    (e.g. type of builtin "int" is `IntType`).
    """
    cdata_type = ctdt_type

    def __init__(self, compiler: "Compiler"):
        super().__init__(TypeDataType(compiler), compiler)
        self.func_repr = str(self.datatype_hook())
        self.do_init()

    def do_init(self):
        """Initialzer for `Type`s. This exists due to historical reason."""
        pass

    def call(self, args, keywords):
        """
        Calling a type is to create an instance of this type,
        i.e. calling `__new__`.
        """
        new = self.attribute_table.lookup('__new__')
        if new is None or not isinstance(new, AcaciaCallable):
            raise Error(ErrorType.CANT_CREATE_INSTANCE,
                        type_=str(self.datatype_hook()))
        return new.call(args, keywords)

    def ccall(self, args, keywords):
        new = self.attributes.clookup('__new__')
        if new is None or not isinstance(new, CTCallable):
            raise Error(ErrorType.CANT_CREATE_INSTANCE,
                        type_=self.cdatatype_hook().name)
        return new.ccall(args, keywords)

    @abstractmethod
    def datatype_hook(self) -> "DataType":
        pass

    @abstractmethod
    def cdatatype_hook(self) -> "CTDataType":
        pass
