"""Values of "type" type in Acacia.
e.g. "int" is a "type".
"""

__all__ = ['TypeDataType', 'Type']

from typing import TYPE_CHECKING
from abc import ABCMeta, abstractmethod

from .base import *
from .none import NoneDataType, ctdt_none
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
        """Calling a type is to create an instance of this type.
        Two things are done:
        1. call `self.__new__` and get `instance`
        2. call `instance.__init__` if exists.
        """
        # Call `__new__`
        new = self.attribute_table.lookup('__new__')
        if new is None:
            raise Error(ErrorType.CANT_CREATE_INSTANCE,
                        type_=str(self.datatype_hook()))
        if not isinstance(new, AcaciaCallable):
            raise TypeError("__new__ of Type objects must be a callable"
                            " expression")
        instance, cmds = new.call(args, keywords)
        # Call initializer of instance if exists
        initializer = instance.attribute_table.lookup('__init__')
        if initializer is not None:
            if not isinstance(initializer, AcaciaCallable):
                raise TypeError("__init__ of Type objects must be a callable"
                                " expression")
            ret, _cmds = initializer.call(args, keywords)
            if not ret.data_type.matches_cls(NoneDataType):
                raise TypeError("__init__ of Type objects return %r instead "
                                "of None" % str(ret.data_type))
            cmds.extend(_cmds)
        return instance, cmds

    def ccall(self, args, keywords):
        new = self.attributes.clookup('__new__')
        if new is None:
            raise Error(ErrorType.CANT_CREATE_INSTANCE,
                        type_=self.cdata_type.name)
        if not isinstance(new, CTCallable):
            raise TypeError("__new__ of Type objects must be a callable"
                            " expression")
        instance = new.ccall(args, keywords)
        initializer = instance.attributes.clookup('__init__')
        if initializer is not None:
            if not isinstance(initializer, CTCallable):
                raise TypeError("__init__ of Type objects must be a callable"
                                " expression")
            ret = initializer.ccall(args, keywords)
            if not ctdt_none.is_typeof(ret):
                raise TypeError("non-None return from __init__")
        return instance

    @abstractmethod
    def datatype_hook(self) -> "DataType":
        pass

    @abstractmethod
    def cdatatype_hook(self) -> "CTDataType":
        pass
